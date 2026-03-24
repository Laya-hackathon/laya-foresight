"""
Laya Healthcare — Supabase Database Setup
Run this once to create all tables, load all data, create indexes and views.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

# ── Load connection string from .env ─────────────────────────────────────────
def load_env():
    with open("../.env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

load_env()
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

print("=" * 62)
print("  LAYA HEALTHCARE — SUPABASE DATABASE SETUP")
print("=" * 62)

# ── Connect ───────────────────────────────────────────────────────────────────
print("\nConnecting to Supabase...")
engine = create_engine(DATABASE_URL, echo=False)
with engine.connect() as conn:
    result = conn.execute(text("SELECT version()")).fetchone()
    print(f"  ✅  Connected — {result[0][:50]}")

# ── Helper ────────────────────────────────────────────────────────────────────
def run(sql):
    with engine.begin() as conn:
        conn.execute(text(sql))

def query(sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).fetchone()[0]

def bool_int(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].map(
                {True:1, False:0, 'True':1, 'False':0, 1:1, 0:0}
            ).fillna(0).astype(int)
    return df

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — DROP existing tables cleanly (safe to re-run)
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 1 — Dropping existing tables (if any)")

drops = [
    "DROP VIEW IF EXISTS v_high_risk_open CASCADE",
    "DROP VIEW IF EXISTS v_agent_dashboard CASCADE",
    "DROP VIEW IF EXISTS v_test CASCADE",
    "DROP VIEW IF EXISTS v_train CASCADE",
    "DROP VIEW IF EXISTS v_ml_features CASCADE",
    "DROP VIEW IF EXISTS v_claim_full CASCADE",
    "DROP TABLE IF EXISTS intervention_outcomes CASCADE",
    "DROP TABLE IF EXISTS agent_interactions CASCADE",
    "DROP TABLE IF EXISTS model_predictions CASCADE",
    "DROP TABLE IF EXISTS feature_snapshots CASCADE",
    "DROP TABLE IF EXISTS support_calls CASCADE",
    "DROP TABLE IF EXISTS app_logs CASCADE",
    "DROP TABLE IF EXISTS claim_status_history CASCADE",
    "DROP TABLE IF EXISTS claims CASCADE",
    "DROP TABLE IF EXISTS treatment_master CASCADE",
    "DROP TABLE IF EXISTS users CASCADE",
]
for sql in drops:
    run(sql)
print("  ✅  Clean slate — all old tables and views dropped")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — CREATE TABLES
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 2 — Creating tables")

run("""
CREATE TABLE users (
    user_id                      TEXT         PRIMARY KEY,
    age_group                    TEXT         NOT NULL,
    region                       TEXT         NOT NULL,
    plan_type                    TEXT         NOT NULL,
    membership_tenure_years      REAL         NOT NULL,
    past_claim_count             INTEGER      NOT NULL,
    past_escalation_count        INTEGER      NOT NULL,
    behavior_archetype           TEXT         NOT NULL,
    preferred_submission_channel TEXT         NOT NULL,
    irish_language_preference    INTEGER      NOT NULL,
    full_name                    TEXT,
    email                        TEXT,
    phone_number                 TEXT
)
""")
print("  ✅  users")

run("""
CREATE TABLE treatment_master (
    treatment_type          TEXT    PRIMARY KEY,
    avg_claim_amount        REAL    NOT NULL,
    avg_processing_days     INTEGER NOT NULL,
    expected_doc_count      INTEGER NOT NULL,
    resubmission_rate       REAL    NOT NULL,
    sla_days                INTEGER NOT NULL
)
""")
print("  ✅  treatment_master")

run("""
CREATE TABLE claims (
    claim_id                TEXT    PRIMARY KEY,
    user_id                 TEXT    NOT NULL REFERENCES users(user_id),
    treatment_type          TEXT    NOT NULL,
    claim_amount            REAL    NOT NULL,
    submission_timestamp    TEXT    NOT NULL,
    submission_channel      TEXT    NOT NULL,
    missing_documents_flag  INTEGER NOT NULL,
    adjudicator_flag        INTEGER NOT NULL,
    claim_rejected_flag     INTEGER NOT NULL,
    resubmission_flag       INTEGER NOT NULL,
    original_claim_id       TEXT    REFERENCES claims(claim_id)
)
""")
print("  ✅  claims")

run("""
CREATE TABLE claim_status_history (
    status_id               TEXT    PRIMARY KEY,
    claim_id                TEXT    NOT NULL REFERENCES claims(claim_id),
    status                  TEXT    NOT NULL,
    status_timestamp        TEXT    NOT NULL,
    sla_breach_at_snapshot  INTEGER NOT NULL
)
""")
print("  ✅  claim_status_history")

run("""
CREATE TABLE app_logs (
    log_id                       TEXT    PRIMARY KEY,
    user_id                      TEXT    NOT NULL REFERENCES users(user_id),
    claim_id                     TEXT    NOT NULL REFERENCES claims(claim_id),
    timestamp                    TEXT    NOT NULL,
    event_type                   TEXT    NOT NULL,
    session_duration             REAL,
    push_notification_opt_in     INTEGER,
    in_app_chat_initiated        INTEGER
)
""")
print("  ✅  app_logs")

run("""
CREATE TABLE support_calls (
    call_id         TEXT    PRIMARY KEY,
    claim_id        TEXT    NOT NULL REFERENCES claims(claim_id),
    call_timestamp  TEXT    NOT NULL,
    call_reason     TEXT    NOT NULL,
    call_channel    TEXT    NOT NULL
)
""")
print("  ✅  support_calls")

run("""
CREATE TABLE feature_snapshots (
    snapshot_id                   SERIAL  PRIMARY KEY,
    claim_id                      TEXT    NOT NULL REFERENCES claims(claim_id),
    user_id                       TEXT    NOT NULL REFERENCES users(user_id),
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
    label_escalation_48h          INTEGER     NOT NULL,
    label_claim_escalation        INTEGER     NOT NULL  
)
""")
print("  ✅  feature_snapshots")

# ── Tables for the full ML pipeline ──────────────────────────────────────────
run("""
CREATE TABLE model_predictions (
    prediction_id     SERIAL      PRIMARY KEY,
    snapshot_id       INTEGER     REFERENCES feature_snapshots(snapshot_id),
    claim_id          TEXT        REFERENCES claims(claim_id),
    user_id           TEXT        REFERENCES users(user_id),
    predicted_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    escalation_score  REAL        NOT NULL,
    risk_level        TEXT        NOT NULL,
    model_version     TEXT        NOT NULL,
    top_feature_1     TEXT,
    top_feature_2     TEXT,
    top_feature_3     TEXT
)
""")
print("  ✅  model_predictions  (model training colleague writes here)")

run("""
CREATE TABLE agent_interactions (
    interaction_id    SERIAL      PRIMARY KEY,
    prediction_id     INTEGER     REFERENCES model_predictions(prediction_id),
    claim_id          TEXT        REFERENCES claims(claim_id),
    user_id           TEXT        REFERENCES users(user_id),
    triggered_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    intervention_type TEXT        NOT NULL,
    agent_message     TEXT,
    user_response     TEXT,
    resolved          BOOLEAN     DEFAULT FALSE,
    resolution_notes  TEXT
)
""")
print("  ✅  agent_interactions  (agentic AI colleague writes here)")

run("""
CREATE TABLE intervention_outcomes (
    outcome_id        SERIAL      PRIMARY KEY,
    interaction_id    INTEGER     REFERENCES agent_interactions(interaction_id),
    user_id           TEXT        REFERENCES users(user_id),
    claim_id          TEXT        REFERENCES claims(claim_id),
    did_call_anyway   BOOLEAN,
    call_avoided      BOOLEAN,
    feedback_score    INTEGER,
    recorded_at       TIMESTAMP   NOT NULL DEFAULT NOW()
)
""")
print("  ✅  intervention_outcomes  (tracks whether interventions worked)")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 3 — Loading CSV data")

CSV_FILES = [
    ("users",               "users.csv",
     ["irish_language_preference"]),

    ("treatment_master",    "treatment_master.csv",
     []),

    ("claims",              "claims.csv",
     ["missing_documents_flag", "adjudicator_flag",
      "claim_rejected_flag", "resubmission_flag"]),

    ("claim_status_history","claim_status_history.csv",
     ["sla_breach_at_snapshot"]),

    ("app_logs",            "app_logs.csv",
     ["push_notification_opt_in", "in_app_chat_initiated"]),

    ("support_calls",       "support_calls.csv",
     []),

    ("feature_snapshots",   "feature_snapshots.csv",
    ["missing_documents_flag", "adjudicator_flag",
    "claim_rejected_flag", "resubmission_flag",
    "sla_breach_flag", "high_value_claim_flag",
    "label_escalation_48h", "label_claim_escalation"]),
]

total_rows = 0
for table, csv_file, bcols in CSV_FILES:
    print(f"  Loading {csv_file}...", end=" ", flush=True)
    df = pd.read_csv(f"../data/{csv_file}")
    df = bool_int(df, bcols)

    # feature_snapshots has an auto-generated snapshot_id — drop it if present
    if table == "feature_snapshots" and "snapshot_id" in df.columns:
        df = df.drop(columns=["snapshot_id"])

    df.to_sql(table, engine, if_exists="append", index=False, method="multi",
              chunksize=500)
    n = query(f"SELECT COUNT(*) FROM {table}")
    total_rows += n
    print(f"✅  {n:,} rows")

print(f"\n  Total rows loaded: {total_rows:,}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — INDEXES
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 4 — Creating indexes")

indexes = [
    ("idx_claims_user",      "claims(user_id)"),
    ("idx_status_claim",     "claim_status_history(claim_id)"),
    ("idx_logs_claim",       "app_logs(claim_id)"),
    ("idx_logs_user",        "app_logs(user_id)"),
    ("idx_logs_ts",          "app_logs(timestamp)"),
    ("idx_calls_claim",      "support_calls(claim_id)"),
    ("idx_calls_ts",         "support_calls(call_timestamp)"),
    ("idx_snaps_claim",      "feature_snapshots(claim_id)"),
    ("idx_snaps_user",       "feature_snapshots(user_id)"),
    ("idx_snaps_date",       "feature_snapshots(snapshot_date)"),
    ("idx_snaps_label",      "feature_snapshots(label_escalation_48h)"),
    ("idx_snaps_treatment",  "feature_snapshots(treatment_type)"),
    ("idx_users_archetype",  "users(behavior_archetype)"),
    ("idx_users_plan",       "users(plan_type)"),
    ("idx_claims_sub_ts",    "claims(submission_timestamp)"),
    ("idx_preds_claim",      "model_predictions(claim_id)"),
    ("idx_preds_user",       "model_predictions(user_id)"),
    ("idx_preds_risk",       "model_predictions(risk_level)"),
    ("idx_preds_ts",         "model_predictions(predicted_at)"),
    ("idx_agent_pred",       "agent_interactions(prediction_id)"),
    ("idx_agent_user",       "agent_interactions(user_id)"),
]

for name, target in indexes:
    run(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")

print(f"  ✅  {len(indexes)} indexes created")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — VIEWS
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 5 — Creating views")

run("""
CREATE VIEW v_claim_full AS
SELECT
    c.claim_id,
    c.user_id,
    u.age_group,
    u.behavior_archetype,
    u.plan_type,
    u.region,
    u.membership_tenure_years,
    c.treatment_type,
    c.claim_amount,
    c.submission_timestamp,
    c.submission_channel,
    c.missing_documents_flag,
    c.adjudicator_flag,
    c.claim_rejected_flag,
    c.resubmission_flag,
    CASE WHEN sc.call_id IS NOT NULL THEN 1 ELSE 0 END AS escalated
FROM claims c
JOIN users u ON c.user_id = u.user_id
LEFT JOIN (
    SELECT DISTINCT claim_id, MIN(call_id) AS call_id
    FROM support_calls GROUP BY claim_id
) sc ON c.claim_id = sc.claim_id
""")
print("  ✅  v_claim_full          — every claim joined with its user")

run("""
CREATE VIEW v_ml_features AS
SELECT
    fs.snapshot_id,
    fs.claim_id,
    fs.user_id,
    fs.snapshot_date,
    u.behavior_archetype,
    fs.plan_type,
    fs.region,
    fs.claim_amount,
    fs.treatment_type,
    fs.days_since_submission,
    fs.submission_channel,
    fs.delay_gap,
    fs.missing_documents_flag,
    fs.adjudicator_flag,
    fs.claim_rejected_flag,
    fs.resubmission_flag,
    fs.sla_breach_flag,
    fs.login_count_24h,
    fs.login_count_48h,
    fs.status_views_24h,
    fs.document_uploads_48h,
    fs.behavior_acceleration,
    fs.in_app_chat_sessions_48h,
    fs.membership_tenure_years,
    fs.past_claim_count,
    fs.past_escalation_ratio,
    fs.age_group,
    fs.relative_claim_cost,
    fs.high_value_claim_flag,
    fs.time_since_last_status_change,
    fs.num_status_changes,
    fs.days_since_resubmission,
    fs.label_escalation_48h
FROM feature_snapshots fs
JOIN users u ON fs.user_id = u.user_id
""")
print("  ✅  v_ml_features         — full feature matrix (model training use this)")

run("""
CREATE VIEW v_train AS
SELECT * FROM v_ml_features
WHERE snapshot_date < '2025-10-01'
""")
print("  ✅  v_train               — Jun-Sep snapshots (training set)")

run("""
CREATE VIEW v_test AS
SELECT * FROM v_ml_features
WHERE snapshot_date >= '2025-10-01'
""")
print("  ✅  v_test                — Oct-Nov snapshots (test set)")

run("""
CREATE VIEW v_agent_dashboard AS
SELECT
    u.user_id,
    u.age_group,
    u.behavior_archetype,
    u.plan_type,
    u.region,
    COUNT(DISTINCT c.claim_id)                                          AS total_claims,
    COUNT(DISTINCT sc.call_id)                                          AS total_calls,
    ROUND(COUNT(DISTINCT sc.call_id)::NUMERIC /
          NULLIF(COUNT(DISTINCT c.claim_id), 0), 3)                     AS escalation_rate,
    MAX(c.submission_timestamp)                                         AS latest_claim_date,
    MAX(sc.call_timestamp)                                              AS latest_call_date
FROM users u
LEFT JOIN claims c ON u.user_id = c.user_id
LEFT JOIN support_calls sc ON c.claim_id = sc.claim_id
GROUP BY u.user_id, u.age_group, u.behavior_archetype,
         u.plan_type, u.region
""")
print("  ✅  v_agent_dashboard     — per-user summary for human agents")

run("""
CREATE VIEW v_high_risk_open AS
SELECT
    fs.claim_id,
    fs.user_id,
    u.behavior_archetype,
    u.plan_type,
    fs.treatment_type,
    ROUND(fs.claim_amount::NUMERIC, 2)          AS claim_amount,
    fs.days_since_submission,
    fs.missing_documents_flag,
    fs.claim_rejected_flag,
    ROUND(fs.behavior_acceleration::NUMERIC, 3) AS behavior_acceleration,
    fs.snapshot_date,
    fs.label_escalation_48h
FROM feature_snapshots fs
JOIN users u ON fs.user_id = u.user_id
WHERE fs.label_escalation_48h = 1
ORDER BY fs.behavior_acceleration DESC
""")
print("  ✅  v_high_risk_open      — all high-risk claims (agentic AI polls this)")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — VERIFY
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 6 — Verification")

print("\n  Table row counts:")
for table in ["users", "treatment_master", "claims", "claim_status_history",
              "app_logs", "support_calls", "feature_snapshots",
              "model_predictions", "agent_interactions", "intervention_outcomes"]:
    n = query(f"SELECT COUNT(*) FROM {table}")
    print(f"    {table:<30} {n:>8,} rows")

print("\n  View row counts:")
for view in ["v_claim_full", "v_ml_features", "v_train",
             "v_test", "v_agent_dashboard", "v_high_risk_open"]:
    n = query(f"SELECT COUNT(*) FROM {view}")
    print(f"    {view:<30} {n:>8,} rows")

print("\n  FK integrity checks:")
fk_checks = [
    ("claims.user_id → users",
     "SELECT COUNT(*) FROM claims WHERE user_id NOT IN (SELECT user_id FROM users)"),
    ("status.claim_id → claims",
     "SELECT COUNT(*) FROM claim_status_history WHERE claim_id NOT IN (SELECT claim_id FROM claims)"),
    ("app_logs.claim_id → claims",
     "SELECT COUNT(*) FROM app_logs WHERE claim_id NOT IN (SELECT claim_id FROM claims)"),
    ("support_calls.claim_id → claims",
     "SELECT COUNT(*) FROM support_calls WHERE claim_id NOT IN (SELECT claim_id FROM claims)"),
    ("snapshots.claim_id → claims",
     "SELECT COUNT(*) FROM feature_snapshots WHERE claim_id NOT IN (SELECT claim_id FROM claims)"),
    ("snapshots.user_id → users",
     "SELECT COUNT(*) FROM feature_snapshots WHERE user_id NOT IN (SELECT user_id FROM users)"),
]
all_pass = True
for desc, sql in fk_checks:
    n = query(sql)
    icon = "✅" if n == 0 else "❌"
    if n > 0: all_pass = False
    print(f"    {icon}  {desc:<42} orphans: {n}")

print("\n  Label distribution:")
t = query("SELECT COUNT(*) FROM feature_snapshots")
p = query("SELECT COUNT(*) FROM feature_snapshots WHERE label_escalation_48h = 1")
print(f"    Positive (escalation)     {p:>8,}  ({round(p/t*100,1)}%)")
print(f"    Negative (no escalation)  {t-p:>8,}  ({round((t-p)/t*100,1)}%)")
print(f"    Imbalance ratio           {round((t-p)/p,1)}:1")

print("\n  Escalation rate by archetype:")
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT behavior_archetype,
               COUNT(*) AS claims,
               SUM(escalated) AS escalated,
               ROUND(AVG(escalated::NUMERIC)*100, 1) AS rate_pct
        FROM v_claim_full
        GROUP BY behavior_archetype
        ORDER BY rate_pct DESC
    """)).fetchall()
print(f"    {'Archetype':<12}  {'Claims':>7}  {'Escalated':>9}  {'Rate':>7}")
print("    " + "-" * 40)
for r in rows:
    print(f"    {r[0]:<12}  {r[1]:>7,}  {r[2]:>9,}  {r[3]:>6.1f}%")

print("\n" + "=" * 62)
print("  ✅  DATABASE SETUP COMPLETE")
print("  Your Supabase database is ready.")
print("  Share the .env file with your 5 colleagues.")
print("  Each person connects using the same DATABASE_URL.")
print("=" * 62)

print("""
HOW EACH COLLEAGUE CONNECTS
─────────────────────────────────────────────────────────
import os, pandas as pd
from sqlalchemy import create_engine

with open(".env") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

engine = create_engine(os.environ["DATABASE_URL"])

# EDA colleague
df = pd.read_sql("SELECT * FROM v_claim_full", engine)

# Model training colleague
train = pd.read_sql("SELECT * FROM v_train", engine)
test  = pd.read_sql("SELECT * FROM v_test",  engine)

# Agentic AI colleague
high_risk = pd.read_sql("SELECT * FROM v_high_risk_open", engine)
─────────────────────────────────────────────────────────
""")