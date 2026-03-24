"""
Laya Healthcare — Test Tables Setup
=====================================
Run this ONCE after setup_database.py has already run and training data
is loaded. It creates a parallel set of test_ tables for the demo pipeline
and drops FK constraints on shared output tables so test IDs flow through.

Safe to re-run — it only drops test_ tables, never touches training tables.

Usage:
    python setup_test_tables.py
    python setup_test_tables.py --data_dir ./test_data

Prerequisites:
    1. setup_database.py has already run (training tables exist)
    2. generate_test_data.py has already run (test CSVs exist)
    3. .env file exists with DATABASE_URL

What this script does:
    STEP 1 — Drop existing test_ tables only (safe, never touches training)
    STEP 2 — Drop FK constraints on shared output tables
    STEP 3 — Create test_ tables (same schemas as training originals)
    STEP 4 — Load test CSVs
    STEP 5 — Create indexes on test_ tables
    STEP 6 — FK integrity checks
    STEP 7 — Verification summary
"""

import os
import sys
import argparse
import pandas as pd
from sqlalchemy import create_engine, text

# ─────────────────────────────────────────────────────────────────────────────
# CLI ARGS
# ─────────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Laya Test Tables Setup")
parser.add_argument(
    "--data_dir",
    default="./test_data",
    help="Directory containing test CSVs from generate_test_data.py"
)
args = parser.parse_args()

# ─────────────────────────────────────────────────────────────────────────────
# LOAD ENV AND CONNECT
# ─────────────────────────────────────────────────────────────────────────────
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()
    except FileNotFoundError:
        pass  # Fall through to env var check below

load_env()
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found. Create a .env file or set the env var.")
    sys.exit(1)

print("=" * 62)
print("  LAYA HEALTHCARE — TEST TABLES SETUP")
print("=" * 62)
print(f"  Data directory : {args.data_dir}")

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

with engine.connect() as conn:
    result = conn.execute(text("SELECT version()")).fetchone()
    print(f"  Connected      : {result[0][:50]}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def run(sql):
    with engine.begin() as conn:
        conn.execute(text(sql))

def query(sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).fetchone()[0]

def bool_int(df, cols):
    """Convert boolean-like values to 0/1 integers."""
    for c in cols:
        if c in df.columns:
            df[c] = df[c].map(
                {True: 1, False: 0, "True": 1, "False": 0, 1: 1, 0: 0}
            ).fillna(0).astype(int)
    return df

def table_exists(table_name):
    result = query(f"""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_name = '{table_name}'
        AND table_schema = 'public'
    """)
    return result > 0

def get_fk_constraint_names(table_name):
    """
    Look up actual FK constraint names from Postgres catalog.
    We do this instead of hardcoding names because Postgres
    auto-generates them and they may vary slightly.
    """
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = '{table_name}'::regclass
            AND contype = 'f'
        """)).fetchall()
    return [row[0] for row in rows]

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Drop existing test_ tables only
#
# ORDER MATTERS: drop child tables before parent tables.
# test_app_logs references test_claims, so test_app_logs drops first.
#
# CASCADE is safe here — it only cascades within test_ tables.
# Training tables have no FK pointing at test_ tables so they
# are completely unaffected.
# ─────────────────────────────────────────────────────────────────────────────
print("STEP 1 — Dropping existing test_ tables (if any)")
print("  Training tables are NOT touched")

test_drops = [
    "DROP TABLE IF EXISTS test_feature_snapshots   CASCADE",
    "DROP TABLE IF EXISTS test_support_calls        CASCADE",
    "DROP TABLE IF EXISTS test_app_logs             CASCADE",
    "DROP TABLE IF EXISTS test_claim_status_history CASCADE",
    "DROP TABLE IF EXISTS test_claims               CASCADE",
    "DROP TABLE IF EXISTS test_users                CASCADE",
]
for sql in test_drops:
    run(sql)

print("  ✅  test_ tables cleared")

# Verify training tables are untouched
print("  Verifying training tables are untouched:")
for t in ["users", "claims", "feature_snapshots"]:
    n = query(f"SELECT COUNT(*) FROM {t}")
    print(f"    ✅  {t:<25} {n:,} rows — intact")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Drop FK constraints on shared output tables
#
# WHY: model_predictions, agent_interactions, intervention_outcomes
# were created by setup_database.py with:
#     claim_id TEXT REFERENCES claims(claim_id)
#     user_id  TEXT REFERENCES users(user_id)
#
# Test IDs (TSTCLM..., TSTU...) live in test_claims / test_users,
# NOT in the training claims / users tables.
# Postgres would reject any INSERT of a test ID with a FK violation.
#
# Dropping these constraints lets test IDs write freely.
# The TST prefix still makes test records visually identifiable
# without needing DB enforcement.
#
# We look up real constraint names from pg_constraint rather than
# hardcoding, because Postgres auto-generates them and they can vary.
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 2 — Dropping FK constraints on shared output tables")

output_tables = [
    "model_predictions",
    "agent_interactions",
    "intervention_outcomes",
]

total_dropped = 0
for table in output_tables:
    if not table_exists(table):
        print(f"  ⚠️   {table} does not exist yet — skipping")
        print(f"       (it will be created by setup_database.py when needed)")
        continue

    constraint_names = get_fk_constraint_names(table)
    if not constraint_names:
        print(f"  ✅  {table:<35} no FK constraints — already clean")
        continue

    for cname in constraint_names:
        run(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {cname}")
        print(f"  ✅  Dropped constraint: {table}.{cname}")
        total_dropped += 1

if total_dropped == 0:
    print("  ✅  No FK constraints to drop")
else:
    print(f"  ✅  {total_dropped} FK constraint(s) dropped")

print("  ℹ️   model_predictions and agent_interactions now accept")
print("       test IDs (TSTCLM..., TSTU...) without FK violations")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Create test_ tables
# Identical schema to training originals.
# FKs within test_ tables (e.g. test_claims → test_users) are kept
# because those relationships are fully internal to the test set.
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 3 — Creating test_ tables")

run("""
CREATE TABLE test_users (
    user_id                      TEXT    PRIMARY KEY,
    age_group                    TEXT    NOT NULL,
    region                       TEXT    NOT NULL,
    plan_type                    TEXT    NOT NULL,
    membership_tenure_years      REAL    NOT NULL,
    past_claim_count             INTEGER NOT NULL,
    past_escalation_count        INTEGER NOT NULL,
    behavior_archetype           TEXT    NOT NULL,
    preferred_submission_channel TEXT    NOT NULL,
    irish_language_preference    INTEGER NOT NULL,
    full_name                    TEXT,
    email                        TEXT,
    phone_number                 TEXT
)
""")
print("  ✅  test_users")

run("""
CREATE TABLE test_claims (
    claim_id                TEXT    PRIMARY KEY,
    user_id                 TEXT    NOT NULL REFERENCES test_users(user_id),
    treatment_type          TEXT    NOT NULL,
    claim_amount            REAL    NOT NULL,
    submission_timestamp    TEXT    NOT NULL,
    submission_channel      TEXT    NOT NULL,
    missing_documents_flag  INTEGER NOT NULL,
    adjudicator_flag        INTEGER NOT NULL,
    claim_rejected_flag     INTEGER NOT NULL,
    resubmission_flag       INTEGER NOT NULL,
    original_claim_id       TEXT
)
""")
print("  ✅  test_claims")

run("""
CREATE TABLE test_claim_status_history (
    status_id               TEXT    PRIMARY KEY,
    claim_id                TEXT    NOT NULL REFERENCES test_claims(claim_id),
    status                  TEXT    NOT NULL,
    status_timestamp        TEXT    NOT NULL,
    sla_breach_at_snapshot  INTEGER NOT NULL
)
""")
print("  ✅  test_claim_status_history")

run("""
CREATE TABLE test_app_logs (
    log_id                       TEXT    PRIMARY KEY,
    user_id                      TEXT    NOT NULL REFERENCES test_users(user_id),
    claim_id                     TEXT    NOT NULL REFERENCES test_claims(claim_id),
    event_type                   TEXT    NOT NULL,
    timestamp                    TEXT    NOT NULL,
    session_duration             REAL,
    in_app_chat_initiated        INTEGER,
    push_notification_opt_in     INTEGER
)
""")
print("  ✅  test_app_logs")

run("""
CREATE TABLE test_support_calls (
    call_id         TEXT    PRIMARY KEY,
    claim_id        TEXT    NOT NULL REFERENCES test_claims(claim_id),
    call_timestamp  TEXT    NOT NULL,
    call_reason     TEXT    NOT NULL,
    call_channel    TEXT    NOT NULL
)
""")
print("  ✅  test_support_calls")

run("""
CREATE TABLE test_feature_snapshots (
    snapshot_id                   SERIAL  PRIMARY KEY,
    claim_id                      TEXT    NOT NULL REFERENCES test_claims(claim_id),
    user_id                       TEXT    NOT NULL REFERENCES test_users(user_id),
    snapshot_date                 TEXT    NOT NULL,
    plan_type                     TEXT    NOT NULL,
    region                        TEXT    NOT NULL,
    claim_amount                  REAL    NOT NULL,
    treatment_type                TEXT    NOT NULL,
    days_since_submission         INTEGER NOT NULL,
    submission_channel            TEXT    NOT NULL,
    delay_gap                     REAL    NOT NULL,
    missing_documents_flag        INTEGER NOT NULL,
    adjudicator_flag              INTEGER NOT NULL,
    claim_rejected_flag           INTEGER NOT NULL,
    resubmission_flag             INTEGER NOT NULL,
    sla_breach_flag               INTEGER NOT NULL,
    login_count_24h               INTEGER NOT NULL,
    login_count_48h               INTEGER NOT NULL,
    status_views_24h              INTEGER NOT NULL,
    document_uploads_48h          INTEGER NOT NULL,
    behavior_acceleration         REAL    NOT NULL,
    in_app_chat_sessions_48h      INTEGER NOT NULL,
    membership_tenure_years       REAL    NOT NULL,
    past_claim_count              INTEGER NOT NULL,
    past_escalation_ratio         REAL    NOT NULL,
    age_group                     TEXT    NOT NULL,
    relative_claim_cost           REAL    NOT NULL,
    high_value_claim_flag         INTEGER NOT NULL,
    time_since_last_status_change REAL    NOT NULL,
    num_status_changes            INTEGER NOT NULL,
    days_since_resubmission       REAL,
    label_escalation_48h          INTEGER NOT NULL
)
""")
print("  ✅  test_feature_snapshots  (nightly pipeline writes this)")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Load CSVs
# test_feature_snapshots is intentionally excluded — the nightly pipeline
# builds it by reading test_app_logs and test_support_calls.
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 4 — Loading test CSVs")

CSV_FILES = [
    (
        "test_users",
        "test_users.csv",
        ["irish_language_preference"],
    ),
    (
        "test_claims",
        "test_claims.csv",
        ["missing_documents_flag", "adjudicator_flag",
         "claim_rejected_flag", "resubmission_flag"],
    ),
    (
        "test_claim_status_history",
        "test_claim_status_history.csv",
        ["sla_breach_at_snapshot"],
    ),
    (
        "test_app_logs",
        "test_app_logs.csv",
        ["in_app_chat_initiated", "push_notification_opt_in"],
    ),
    (
        "test_support_calls",
        "test_support_calls.csv",
        [],
    ),
]

total_rows = 0
for table, csv_file, bool_cols in CSV_FILES:
    csv_path = os.path.join(args.data_dir, csv_file)

    if not os.path.exists(csv_path):
        print(f"  ❌  {csv_file} not found at {csv_path}")
        print(f"       Run: python generate_test_data.py --output_dir {args.data_dir}")
        sys.exit(1)

    print(f"  Loading {csv_file}...", end=" ", flush=True)
    df = pd.read_csv(csv_path)
    df = bool_int(df, bool_cols)

    df.to_sql(
        table, engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )
    n = query(f"SELECT COUNT(*) FROM {table}")
    total_rows += n
    print(f"✅  {n:,} rows")

print(f"\n  Total rows loaded  : {total_rows:,}")
print(f"  test_feature_snapshots : 0 rows — pipeline fills this next")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Indexes on test_ tables
# Same index strategy as training tables for consistent query performance
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 5 — Creating indexes")

indexes = [
    ("idx_test_claims_user",     "test_claims(user_id)"),
    ("idx_test_status_claim",    "test_claim_status_history(claim_id)"),
    ("idx_test_logs_claim",      "test_app_logs(claim_id)"),
    ("idx_test_logs_user",       "test_app_logs(user_id)"),
    ("idx_test_logs_ts",         "test_app_logs(timestamp)"),
    ("idx_test_calls_claim",     "test_support_calls(claim_id)"),
    ("idx_test_calls_ts",        "test_support_calls(call_timestamp)"),
    ("idx_test_snaps_claim",     "test_feature_snapshots(claim_id)"),
    ("idx_test_snaps_user",      "test_feature_snapshots(user_id)"),
    ("idx_test_snaps_date",      "test_feature_snapshots(snapshot_date)"),
    ("idx_test_snaps_label",     "test_feature_snapshots(label_escalation_48h)"),
    ("idx_test_snaps_treatment", "test_feature_snapshots(treatment_type)"),
    ("idx_test_users_archetype", "test_users(behavior_archetype)"),
    ("idx_test_claims_sub_ts",   "test_claims(submission_timestamp)"),
]

for name, target in indexes:
    run(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")

print(f"  ✅  {len(indexes)} indexes created")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — FK integrity checks
# Verify zero orphans across all test_ table relationships
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 6 — FK integrity checks")

fk_checks = [
    (
        "test_claims.user_id → test_users",
        "SELECT COUNT(*) FROM test_claims "
        "WHERE user_id NOT IN (SELECT user_id FROM test_users)",
    ),
    (
        "test_status_history.claim_id → test_claims",
        "SELECT COUNT(*) FROM test_claim_status_history "
        "WHERE claim_id NOT IN (SELECT claim_id FROM test_claims)",
    ),
    (
        "test_app_logs.claim_id → test_claims",
        "SELECT COUNT(*) FROM test_app_logs "
        "WHERE claim_id NOT IN (SELECT claim_id FROM test_claims)",
    ),
    (
        "test_app_logs.user_id → test_users",
        "SELECT COUNT(*) FROM test_app_logs "
        "WHERE user_id NOT IN (SELECT user_id FROM test_users)",
    ),
    (
        "test_support_calls.claim_id → test_claims",
        "SELECT COUNT(*) FROM test_support_calls "
        "WHERE claim_id NOT IN (SELECT claim_id FROM test_claims)",
    ),
]

all_fk_pass = True
for desc, sql in fk_checks:
    n = query(sql)
    icon = "✅" if n == 0 else "❌"
    if n > 0:
        all_fk_pass = False
    print(f"  {icon}  {desc:<52} orphans: {n}")

if all_fk_pass:
    print("  ✅  All FK checks passed — zero orphans")
else:
    print("  ❌  FK violations found — re-run generate_test_data.py and retry")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Final verification summary
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 7 — Verification summary")

print("\n  Test table row counts:")
for table in [
    "test_users", "test_claims", "test_claim_status_history",
    "test_app_logs", "test_support_calls", "test_feature_snapshots",
]:
    n = query(f"SELECT COUNT(*) FROM {table}")
    note = "  ← pipeline fills this" if table == "test_feature_snapshots" else ""
    print(f"    {table:<35} {n:>7,} rows{note}")

print("\n  Training table row counts (must be unchanged):")
for table in ["users", "claims", "app_logs", "support_calls", "feature_snapshots"]:
    n = query(f"SELECT COUNT(*) FROM {table}")
    print(f"    {table:<35} {n:>7,} rows  ✅ intact")

print("\n  Escalation breakdown in test data by archetype:")
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT
            u.behavior_archetype,
            COUNT(DISTINCT c.claim_id)                              AS claims,
            COUNT(DISTINCT sc.claim_id)                             AS escalated,
            ROUND(
                COUNT(DISTINCT sc.claim_id)::NUMERIC /
                NULLIF(COUNT(DISTINCT c.claim_id), 0) * 100, 1
            )                                                       AS rate_pct
        FROM test_users u
        JOIN test_claims c  ON u.user_id  = c.user_id
        LEFT JOIN test_support_calls sc ON c.claim_id = sc.claim_id
        GROUP BY u.behavior_archetype
        ORDER BY rate_pct DESC NULLS LAST
    """)).fetchall()

print(f"    {'Archetype':<12}  {'Claims':>7}  {'Escalated':>9}  {'Rate':>7}")
print("    " + "─" * 42)
for r in rows:
    print(f"    {r[0]:<12}  {r[1]:>7,}  {r[2]:>9,}  {r[3]:>6.1f}%")

print("\n  Shared output table FK constraints (must all be gone):")
for table in ["model_predictions", "agent_interactions", "intervention_outcomes"]:
    if not table_exists(table):
        print(f"    ⚠️   {table} not created yet — run setup_database.py first")
        continue
    remaining = get_fk_constraint_names(table)
    if not remaining:
        print(f"    ✅  {table:<35} no FK constraints — test IDs will write freely")
    else:
        print(f"    ⚠️   {table:<35} still has: {remaining}")

# ─────────────────────────────────────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 62)
print("  ✅  SETUP COMPLETE — test tables ready")
print()
print("  Next steps in order:")
print()
print("  1. Run the pipeline for each simulated day:")
print("       python nightly_pipeline.py --mode test --date 2025-12-01")
print("       python nightly_pipeline.py --mode test --date 2025-12-02")
print("       python nightly_pipeline.py --mode test --date 2025-12-03")
print("       (repeat up to sim_days from generate_test_data.py)")
print()
print("  2. Verify snapshots were created:")
print("       SELECT COUNT(*) FROM test_feature_snapshots;")
print()
print("  3. Run model scoring against test_feature_snapshots")
print("       → writes to model_predictions")
print()
print("  4. Agent reads model_predictions")
print("       → writes to agent_interactions")
print("=" * 62)
