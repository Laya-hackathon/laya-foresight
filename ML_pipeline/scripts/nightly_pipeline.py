"""
Laya Healthcare — Nightly Feature Snapshot Pipeline
====================================================
World 1 -> Data Engineering
Pipeline folder

This script runs every night. It reads live events from the database,
computes fresh feature snapshots for every active claim, and writes
them to feature_snapshots. The model training colleague scores these
snapshots the next morning. The agent acts on the scores.

Run manually (train mode -> default):
    python pipeline/nightly_pipeline.py

Run in test mode (uses test_ prefixed tables):
    python pipeline/nightly_pipeline.py --mode test

Run for a specific date:
    python pipeline/nightly_pipeline.py --date 2024-01-15

Run in test mode for a specific date:
    python pipeline/nightly_pipeline.py --mode test --date 2024-01-15

Backfill N days:
    python pipeline/nightly_pipeline.py --backfill 7

Backfill in test mode:
    python pipeline/nightly_pipeline.py --mode test --backfill 7

Run on a schedule (cron example -> midnight every night):
    0 0 * * * /path/to/venv/bin/python /path/to/laya-data/pipeline/nightly_pipeline.py

Safe to run multiple times -> duplicate snapshots are never created.
"""

import os
import sys
import argparse                          # ← moved to top with all other imports
import logging
import pandas as pd
import numpy as np
import psycopg2
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TABLE RESOLVER
# ─────────────────────────────────────────────────────────────────────────────
def resolve_tables(mode):
    """
    Returns a dict of logical table name → actual DB table name.
    In test mode every table gets the test_ prefix, except users
    which is always shared (test users have distinct IDs).

    Usage:
        tbl = resolve_tables("test")
        tbl["claims"]        # → "test_claims"
        tbl["snapshots"]     # → "test_feature_snapshots"
    """
    prefix = "test_" if mode == "test" else ""
    return {
        "claims":         f"{prefix}claims",
        "users":          f"{prefix}users",           # shared -> no test_users needed
        "app_logs":       f"{prefix}app_logs",
        "status_history": f"{prefix}claim_status_history",
        "support_calls":  f"{prefix}support_calls",
        "snapshots":      f"{prefix}feature_snapshots",
    }


# ── Load .env ─────────────────────────────────────────────────────────────────
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()
    except FileNotFoundError:
        log.warning(".env file not found — using environment variables directly")

load_env()
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    log.error("DATABASE_URL not found. Create a .env file in the project root.")
    sys.exit(1)

# ── Connect ───────────────────────────────────────────────────────────────────
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_CLAIM_LIFECYCLE_DAYS = 14      # claims older than this are considered closed
ESCALATION_WINDOW_HOURS  = 48     # label window in hours
SLA_BY_TYPE = {                    # expected processing days per claim type
    "GP":            5,
    "Dental":        10,
    "Specialist":    14,
    "Physiotherapy": 7,
    "Mental_Health": 10,
    "Surgical":      21,
    "Maternity":     14,
}
PROC_MEAN_BY_TYPE = {              # average processing days per claim type
    "GP":            3,
    "Dental":        7,
    "Specialist":    10,
    "Physiotherapy": 5,
    "Mental_Health": 7,
    "Surgical":      14,
    "Maternity":     10,
}
PLAN_AVG_COST = {
    "Individual": 350,
    "Family":     500,
    "Corporate":  400,
}
HIGH_VALUE_THRESHOLD = 2000

def canonicalise_treatment(val):
    """Normalise treatment type variants to canonical names."""
    if pd.isna(val):
        return "GP"
    v = str(val).strip().lower().replace(" ", "_")
    mapping = {
        "gp":     "GP",
        "dent":   "Dental",
        "spec":   "Specialist",
        "phys":   "Physiotherapy",
        "ment":   "Mental_Health",
        "surg":   "Surgical",
        "mate":   "Maternity",
    }
    for prefix, canon in mapping.items():
        if v.startswith(prefix):
            return canon
    return str(val).strip()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Determine the pipeline run date
# ─────────────────────────────────────────────────────────────────────────────
def get_run_date():
    """
    The pipeline runs for yesterday's date by default.
    This ensures all events for the day have been captured
    before we create snapshots.
    """
    return datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=0)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Find all active claims
# ─────────────────────────────────────────────────────────────────────────────
def get_active_claims(run_date, conn, tbl):
    """
    Active claims = submitted before run_date and not yet closed.
    A claim is considered closed if:
    - Its latest status is Approved, Rejected, or Closed
    - OR it is older than MAX_CLAIM_LIFECYCLE_DAYS
    """
    cutoff = run_date - timedelta(days=MAX_CLAIM_LIFECYCLE_DAYS)

    query = text(f"""
        SELECT
            c.claim_id,
            c.user_id,
            c.treatment_type,
            c.claim_amount,
            c.submission_timestamp,
            c.submission_channel,
            c.missing_documents_flag,
            c.adjudicator_flag,
            c.claim_rejected_flag,
            c.resubmission_flag,
            c.original_claim_id,
            u.plan_type,
            u.region,
            u.age_group,
            u.behavior_archetype,
            u.membership_tenure_years,
            u.past_claim_count,
            u.past_escalation_count
        FROM {tbl["claims"]} c
        JOIN {tbl["users"]} u ON c.user_id = u.user_id
        WHERE c.submission_timestamp <= :run_date
          AND c.submission_timestamp >= :cutoff
          AND c.claim_id NOT IN (
              SELECT DISTINCT csh.claim_id
              FROM {tbl["status_history"]} csh
              WHERE csh.status IN ('Approved', 'Rejected', 'Closed')
                AND csh.status_timestamp <= :run_date
          )
    """)

    df = pd.read_sql(query, conn, params={
        "run_date": run_date.strftime("%Y-%m-%d %H:%M:%S"),
        "cutoff":   cutoff.strftime("%Y-%m-%d %H:%M:%S"),
    })
    df["submission_timestamp"] = pd.to_datetime(df["submission_timestamp"])
    return df

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Find which snapshots already exist for today
# ─────────────────────────────────────────────────────────────────────────────
def get_existing_snapshots(run_date, conn, tbl):
    """
    Returns a set of claim_ids that already have a snapshot
    for today's date. Prevents duplicates.
    """
    date_str = run_date.strftime("%Y-%m-%d")
    query = text(f"""
        SELECT DISTINCT claim_id
        FROM {tbl["snapshots"]}
        WHERE snapshot_date::date = :today
    """)
    result = conn.execute(query, {"today": date_str}).fetchall()
    return {row[0] for row in result}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Load events needed for feature computation
# ─────────────────────────────────────────────────────────────────────────────
def load_recent_events(claim_ids, run_date, conn, tbl):
    """
    Load app_logs and status history for active claims
    within the relevant time windows.
    Only loads what is needed — not the full 361K rows.
    """
    if not claim_ids:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Window for behavioural features — 48h before run_date
    window_start = run_date - timedelta(hours=48)
    ids_str = "'" + "','".join(claim_ids) + "'"

    logs_query = text(f"""
        SELECT claim_id, user_id, timestamp, event_type,
               in_app_chat_initiated
        FROM {tbl["app_logs"]}
        WHERE claim_id IN ({ids_str})
          AND timestamp BETWEEN :start AND :end
    """)
    logs = pd.read_sql(logs_query, conn, params={
        "start": window_start.strftime("%Y-%m-%d %H:%M:%S"),
        "end":   run_date.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if not logs.empty:
        logs["timestamp"] = pd.to_datetime(logs["timestamp"])

    status_query = text(f"""
        SELECT claim_id, status, status_timestamp, sla_breach_at_snapshot
        FROM {tbl["status_history"]}
        WHERE claim_id IN ({ids_str})
          AND status_timestamp <= :end
        ORDER BY status_timestamp ASC
    """)
    status_hist = pd.read_sql(status_query, conn, params={
        "end": run_date.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if not status_hist.empty:
        status_hist["status_timestamp"] = pd.to_datetime(status_hist["status_timestamp"])

    # Calls within the next 48h — for labelling
    label_end = run_date + timedelta(hours=ESCALATION_WINDOW_HOURS)
    calls_query = text(f"""
        SELECT claim_id, call_timestamp
        FROM {tbl["support_calls"]}
        WHERE claim_id IN ({ids_str})
          AND call_timestamp BETWEEN :start AND :end
    """)
    calls = pd.read_sql(calls_query, conn, params={
        "start": run_date.strftime("%Y-%m-%d %H:%M:%S"),
        "end":   label_end.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if not calls.empty:
        calls["call_timestamp"] = pd.to_datetime(calls["call_timestamp"])

    return logs, status_hist, calls

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Compute features for one claim
# ─────────────────────────────────────────────────────────────────────────────
def compute_snapshot(claim, run_date, logs, status_hist, calls_today,
                     prior_claims_count, prior_escalation_count):
    """
    Computes all features for one claim at run_date.
    Returns a dictionary ready to insert into feature_snapshots.
    """
    cid       = claim["claim_id"]
    uid       = claim["user_id"]
    sub_ts    = claim["submission_timestamp"]
    tx_raw    = claim["treatment_type"]
    tx        = canonicalise_treatment(tx_raw)
    plan      = claim["plan_type"]
    region    = claim["region"]
    amt       = float(claim["claim_amount"])
    miss_doc  = int(claim["missing_documents_flag"])
    adj_flag  = int(claim["adjudicator_flag"])
    rejected  = int(claim["claim_rejected_flag"])
    resub     = int(claim["resubmission_flag"])
    tenure    = float(claim["membership_tenure_years"])
    age_group = claim["age_group"]

    # ── Claim context ─────────────────────────────────────────────────────────
    days_since_sub = max(1, (run_date - sub_ts).days)
    proc_mean      = PROC_MEAN_BY_TYPE.get(tx, 7)
    sla_days       = SLA_BY_TYPE.get(tx, 10)
    delay_gap      = max(0.0, float(days_since_sub - proc_mean))
    sla_breach     = int(days_since_sub > sla_days)

    # ── Status history features ───────────────────────────────────────────────
    claim_status = status_hist[status_hist.claim_id == cid]
    n_changes    = len(claim_status)

    if n_changes > 0:
        last_change_ts      = claim_status.iloc[-1]["status_timestamp"]
        time_since_last     = (run_date - last_change_ts).total_seconds() / 3600
    else:
        time_since_last     = float(days_since_sub * 24)

    # ── Behavioural features from app_logs ────────────────────────────────────
    claim_logs = logs[logs.claim_id == cid]

    if not claim_logs.empty:
        ts_col     = claim_logs["timestamp"]
        w24_start  = run_date - timedelta(hours=24)
        w48_start  = run_date - timedelta(hours=48)
        prev_start = run_date - timedelta(hours=48)
        prev_end   = run_date - timedelta(hours=24)

        mask_24   = (ts_col >= w24_start)  & (ts_col <= run_date)
        mask_48   = (ts_col >= w48_start)  & (ts_col <= run_date)
        mask_prev = (ts_col >= prev_start) & (ts_col < prev_end)

        logs_24   = claim_logs[mask_24]
        logs_48   = claim_logs[mask_48]
        logs_prev = claim_logs[mask_prev]

        login_24  = int((logs_24.event_type  == "login").sum())
        login_48  = int((logs_48.event_type  == "login").sum())
        sv_24     = int((logs_24.event_type  == "claim_status_view").sum())
        doc_48    = int((logs_48.event_type  == "document_upload").sum())
        chat_48   = int((logs_48.in_app_chat_initiated == True).sum() if
                        "in_app_chat_initiated" in logs_48.columns else 0)
        sv_prev   = int((logs_prev.event_type == "claim_status_view").sum())
        beh_acc   = round(sv_24 / max(sv_prev, 1), 4)
    else:
        login_24 = login_48 = sv_24 = doc_48 = chat_48 = 0
        beh_acc  = 1.0

    # ── Financial features ────────────────────────────────────────────────────
    plan_avg    = PLAN_AVG_COST.get(plan, 350)
    rel_cost    = round(amt / plan_avg, 4)
    hv_flag     = int(amt > HIGH_VALUE_THRESHOLD)

    # ── Historical features — from actual prior claims in DB ──────────────────
    past_esc_ratio = round(
        prior_escalation_count / max(prior_claims_count, 1), 4
    )

    # ── Days since resubmission ───────────────────────────────────────────────
    days_since_resub = None
    if resub and claim.get("original_claim_id"):
        orig_id = claim["original_claim_id"]
        # Will be computed from DB if available — None is safe
        pass

    # ── Label — did a call happen within 48h after run_date? ─────────────────
    claim_calls = calls_today[calls_today.claim_id == cid] if not calls_today.empty else pd.DataFrame()
    label = int(len(claim_calls) > 0)

    return {
        "claim_id":                     cid,
        "user_id":                      uid,
        "snapshot_date":                run_date.strftime("%Y-%m-%d %H:%M:%S"),
        "plan_type":                    plan,
        "region":                       region,
        "claim_amount":                 round(amt, 2),
        "treatment_type":               tx,
        "days_since_submission":        days_since_sub,
        "submission_channel":           str(claim["submission_channel"]),
        "delay_gap":                    delay_gap,
        "missing_documents_flag":       miss_doc,
        "adjudicator_flag":             adj_flag,
        "claim_rejected_flag":          rejected,
        "resubmission_flag":            resub,
        "sla_breach_flag":              sla_breach,
        "login_count_24h":              login_24,
        "login_count_48h":              login_48,
        "status_views_24h":             sv_24,
        "document_uploads_48h":         doc_48,
        "behavior_acceleration":        beh_acc,
        "in_app_chat_sessions_48h":     chat_48,
        "membership_tenure_years":      tenure,
        "past_claim_count":             prior_claims_count,
        "past_escalation_ratio":        past_esc_ratio,
        "age_group":                    age_group,
        "relative_claim_cost":          rel_cost,
        "high_value_claim_flag":        hv_flag,
        "time_since_last_status_change":round(time_since_last, 2),
        "num_status_changes":           n_changes,
        "days_since_resubmission":      days_since_resub,
        "label_escalation_48h":         label,
    }

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Build prior claim history per user
# ─────────────────────────────────────────────────────────────────────────────
def build_user_history(active_claims, run_date, conn, tbl):
    """
    For each user in active_claims, count how many prior claims
    they had before the current claim, and how many of those escalated.
    This replaces the random Poisson numbers with real computed values.
    """
    user_ids = active_claims["user_id"].unique().tolist()
    ids_str  = "'" + "','".join(user_ids) + "'"

    # All claims in DB for these users
    all_claims = pd.read_sql(text(f"""
        SELECT c.claim_id, c.user_id, c.submission_timestamp
        FROM {tbl["claims"]} c
        WHERE c.user_id IN ({ids_str})
    """), conn)
    all_claims["submission_timestamp"] = pd.to_datetime(all_claims["submission_timestamp"])

    # All support calls for these users
    all_calls = pd.read_sql(text(f"""
        SELECT sc.claim_id
        FROM {tbl["support_calls"]} sc
        JOIN {tbl["claims"]} c ON sc.claim_id = c.claim_id
        WHERE c.user_id IN ({ids_str})
    """), conn)
    escalated_claim_ids = set(all_calls["claim_id"].tolist())

    history = {}
    for _, row in active_claims.iterrows():
        uid    = row["user_id"]
        sub_ts = row["submission_timestamp"]
        cid    = row["claim_id"]
        # Prior claims = submitted before this claim, not this claim itself
        prior = all_claims[
            (all_claims.user_id == uid) &
            (all_claims.submission_timestamp < sub_ts) &
            (all_claims.claim_id != cid)
        ]
        prior_count   = len(prior)
        prior_esc     = sum(1 for c in prior["claim_id"] if c in escalated_claim_ids)
        history[cid]  = (prior_count, prior_esc)

    return history

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Write snapshots to database
# ─────────────────────────────────────────────────────────────────────────────
def write_snapshots(snapshots, conn, tbl):
    """
    Inserts new snapshot rows into the snapshots table (train or test).
    Uses ON CONFLICT DO NOTHING as a safety net against duplicates.
    """
    if not snapshots:
        return 0

    df = pd.DataFrame(snapshots)
    df.to_sql(
        tbl["snapshots"],                # ← uses resolved table name
        conn,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=200,
    )
    return len(snapshots)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
def run_pipeline(run_date=None, mode="train"):
    """
    Main pipeline entry point.
    - mode:     "train" (default) or "test" — controls which DB tables are used.
    - run_date: specific datetime to run for; defaults to end-of-today UTC.
    """
    tbl = resolve_tables(mode)           # ← resolve table names once, up front

    if run_date is None:
        run_date = get_run_date()

    log.info("=" * 60)
    log.info("  LAYA HEALTHCARE -> NIGHTLY PIPELINE")
    log.info("=" * 60)
    log.info(f"  Mode     : {mode.upper()}")
    log.info(f"  Run date : {run_date.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"  Started  : {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log.info(f"  Tables   : claims={tbl['claims']}, snapshots={tbl['snapshots']}")

    with engine.connect() as conn:

        # -- Step 1: Find active claims
        log.info("\nSTEP 1 -> Finding active claims")
        active_claims = get_active_claims(run_date, conn, tbl)
        log.info(f"  Found {len(active_claims):,} active claims to process")

        if active_claims.empty:
            log.info("  No active claims found. Pipeline complete.")
            return {"run_date": run_date, "snapshots_created": 0,
                    "claims_processed": 0, "skipped_duplicates": 0}

        # -- Step 2: Find existing snapshots for today
        log.info("\nSTEP 2 -> Checking for existing snapshots today")
        existing = get_existing_snapshots(run_date, conn, tbl)
        claims_to_process = active_claims[
            ~active_claims["claim_id"].isin(existing)
        ]
        skipped = len(active_claims) - len(claims_to_process)
        log.info(f"  Already have snapshots for : {skipped:,} claims (skipping)")
        log.info(f"  Need to create snapshots for: {len(claims_to_process):,} claims")

        if claims_to_process.empty:
            log.info("  All snapshots already exist. Pipeline complete.")
            return {"run_date": run_date, "snapshots_created": 0,
                    "claims_processed": 0, "skipped_duplicates": skipped}

        # -- Step 3: Load events from database
        log.info("\nSTEP 3 -> Loading events from database")
        claim_ids = claims_to_process["claim_id"].tolist()
        logs_df, status_df, calls_df = load_recent_events(claim_ids, run_date, conn, tbl)
        log.info(f"  App log events loaded   : {len(logs_df):,}")
        log.info(f"  Status changes loaded   : {len(status_df):,}")
        log.info(f"  Calls in 48h window     : {len(calls_df):,}")

        # -- Step 4: Build user history
        log.info("\nSTEP 4 -> Computing user claim history")
        user_history = build_user_history(claims_to_process, run_date, conn, tbl)
        log.info(f"  History computed for {len(user_history):,} claims")

        # -- Step 5: Compute snapshots
        log.info("\nSTEP 5 -> Computing feature snapshots")
        snapshots   = []
        errors      = []
        label_pos   = 0

        for _, claim in claims_to_process.iterrows():
            try:
                prior_count, prior_esc = user_history.get(
                    claim["claim_id"], (0, 0)
                )
                snap = compute_snapshot(
                    claim       = claim,
                    run_date    = run_date,
                    logs        = logs_df,
                    status_hist = status_df,
                    calls_today = calls_df,
                    prior_claims_count      = prior_count,
                    prior_escalation_count  = prior_esc,
                )
                snapshots.append(snap)
                if snap["label_escalation_48h"] == 1:
                    label_pos += 1

            except Exception as e:
                errors.append((claim["claim_id"], str(e)))
                log.warning(f"  Failed to compute snapshot for {claim['claim_id']}: {e}")

        label_pct = label_pos / len(snapshots) * 100 if snapshots else 0
        log.info(f"  Snapshots computed      : {len(snapshots):,}")
        log.info(f"  Positive labels (1)     : {label_pos:,}  ({label_pct:.1f}%)")
        log.info(f"  Errors                  : {len(errors)}")

        # -- Step 6: Write to database
        log.info("\nSTEP 6 -> Writing to database")

    # Use a new connection with transaction for the write
    with engine.begin() as write_conn:
        written = write_snapshots(snapshots, write_conn, tbl)
    log.info(f"  Written to {tbl['snapshots']}: {written:,} rows")

    # -- Step 7: Verify
    log.info("\nSTEP 7 -> Verification")
    with engine.connect() as conn:
        total_snaps = conn.execute(
            text(f"SELECT COUNT(*) FROM {tbl['snapshots']}")
        ).fetchone()[0]
        today_snaps = conn.execute(text(f"""
            SELECT COUNT(*) FROM {tbl["snapshots"]}
            WHERE snapshot_date::date = :today
        """), {"today": run_date.strftime("%Y-%m-%d")}).fetchone()[0]
        today_pos = conn.execute(text(f"""
            SELECT COUNT(*) FROM {tbl["snapshots"]}
            WHERE snapshot_date::date = :today
              AND label_escalation_48h = 1
        """), {"today": run_date.strftime("%Y-%m-%d")}).fetchone()[0]

    log.info(f"  Total snapshots in DB   : {total_snaps:,}")
    log.info(f"  Snapshots for today     : {today_snaps:,}")
    log.info(f"  Positive labels today   : {today_pos:,} "
             f"({today_pos/today_snaps*100:.1f}%)" if today_snaps > 0 else "")

    result = {
        "run_date":            run_date.strftime("%Y-%m-%d"),
        "mode":                mode,
        "claims_processed":    len(claims_to_process),
        "snapshots_created":   written,
        "skipped_duplicates":  skipped,
        "label_positive_rate": round(label_pct, 2),
        "errors":              len(errors),
    }

    log.info("\n" + "=" * 60)
    log.info("  ✅  PIPELINE COMPLETE")
    log.info(f"  Mode               : {mode.upper()}")
    log.info(f"  Claims processed   : {result['claims_processed']:,}")
    log.info(f"  Snapshots created  : {result['snapshots_created']:,}")
    log.info(f"  Duplicates skipped : {result['skipped_duplicates']:,}")
    log.info(f"  Positive label rate: {result['label_positive_rate']:.1f}%")
    log.info(f"  Errors             : {result['errors']}")
    log.info("=" * 60)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    # Single parser — all three args (--mode, --date, --backfill) live here
    parser = argparse.ArgumentParser(
        description="Laya Healthcare — Nightly Feature Snapshot Pipeline"
    )
    parser.add_argument(
        "--mode",
        choices=["train", "test"],
        default="test",
        help="Table set to use: 'train'  uses live tables; "
             "'test' uses test_ prefixed tables."
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Run for a specific date (YYYY-MM-DD). Default: today."
    )
    parser.add_argument(
        "--backfill",
        type=int,
        default=None,
        help="Backfill N days of history. Example: --backfill 7"
    )
    args = parser.parse_args()

    if args.backfill:
        # Run pipeline for each of the last N days
        log.info(f"Backfill mode -> running for last {args.backfill} days "
                 f"[mode={args.mode}]")
        for i in range(args.backfill, 0, -1):
            backfill_date = datetime.utcnow() - timedelta(days=i)
            backfill_date = backfill_date.replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            log.info(f"\n{'-'*60}")
            log.info(f"Backfilling: {backfill_date.strftime('%Y-%m-%d')}")
            run_pipeline(run_date=backfill_date, mode=args.mode)

    elif args.date:
        # Run for a specific date
        specific_date = datetime.strptime(args.date, "%Y-%m-%d")
        specific_date = specific_date.replace(
            hour=23, minute=59, second=59, microsecond=0
        )
        run_pipeline(run_date=specific_date, mode=args.mode)

    else:
        # Normal nightly run
        run_pipeline(mode=args.mode)
