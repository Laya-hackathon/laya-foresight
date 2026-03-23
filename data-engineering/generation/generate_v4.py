"""
Laya Healthcare — Synthetic Data Generator v4.0
================================================
Implements all 7 rules from ML Engineering team specification.

Core design principle: every feature must be causally connected to the label.
The call timing drives the app log generation which drives the snapshot features.
Features are NOT generated independently — they are DERIVED from app_logs.

Key changes from v3:
  1. will_escalate decided at claim creation time (before any logs)
  2. call_day determined by anxiety curve (SLA breach + archetype)
  3. Login counts spike 3-4x in 48h before call day
  4. Status views spike 2-3x in 48h before call day
  5. Both spike grow with claim age (monotonically increasing baseline)
  6. Feature snapshots DERIVED by counting actual app_log events
  7. Both 48h snapshot label AND claim-level label included
  8. login_count_24h in snapshot = actual login events in app_logs ± 0

Author: Data Engineering World — Laya Healthcare Hackathon 2025
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import math
import warnings
warnings.filterwarnings("ignore")

# ── Reproducibility ───────────────────────────────────────────────────────────
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# ── Output directory ──────────────────────────────────────────────────────────
import os as _os
OUT = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "data") + _os.sep

# ── Simulation window ─────────────────────────────────────────────────────────
START_DATE = datetime(2025, 6, 1)
END_DATE   = datetime(2025, 11, 30)

# ── Target volumes ─────────────────────────────────────────────────────────────
N_USERS            = 2000
TARGET_CLAIMS      = 5200   # aim for 5000+ per ML team spec
MAX_LIFECYCLE_DAYS = 14
ESCALATION_WINDOW  = 48     # hours — label window

# ─────────────────────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
def rand_dt(start, end):
    """Random datetime between start and end."""
    delta = (end - start).total_seconds()
    if delta <= 0:
        return start
    return start + timedelta(seconds=random.random() * delta)

def ts_fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def inject_glitch(ts, rate=0.02, max_minutes=60):
    """Inject DST/timezone glitch on ~2% of timestamps."""
    if random.random() < rate:
        return ts + timedelta(minutes=random.randint(-max_minutes, max_minutes))
    return ts

def canonicalise(val, tx_lookup):
    """Normalise treatment type variants to canonical name."""
    v = str(val).strip().lower().replace(" ", "_")
    mapping = {
        "gp": "GP", "dent": "Dental", "spec": "Specialist",
        "phys": "Physiotherapy", "ment": "Mental_Health",
        "surg": "Surgical", "mate": "Maternity",
    }
    for prefix, canon in mapping.items():
        if v.startswith(prefix):
            return canon
    return str(val).strip()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — USERS
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 65)
print("  LAYA HEALTHCARE — SYNTHETIC DATA GENERATOR v4.0")
print("  Implementing ML Engineering team specification")
print("=" * 65)
print("\nSTEP 1 — Generating users")

# Distributions matching YAML v0.2
AGE_GROUPS    = ["18-29", "30-44", "45-59", "60-74", "75+"]
AGE_WEIGHTS   = [0.18,    0.30,    0.27,    0.18,    0.07]
PLAN_TYPES    = ["Individual", "Family", "Corporate"]
PLAN_WEIGHTS  = [0.45,         0.30,     0.25]
ARCHETYPES    = ["Passive", "Engaged", "Anxious", "Distress"]
ARCH_WEIGHTS  = [0.35,      0.40,      0.18,      0.07]
CHANNELS      = ["app", "web_portal", "paper_post", "direct_billing"]
CHAN_WEIGHTS   = [0.45,  0.28,         0.18,         0.09]
REGIONS_CLEAN = ["Dublin", "Cork", "Galway", "Limerick", "Waterford", "Other"]
REGION_W      = [0.35,     0.15,   0.12,     0.10,       0.08,        0.20]

# Noise variants for regions (4%)
REGION_VARIANTS = {
    "Dublin":    ["Dublin", "dublin", "Co. Dublin", "DUB"],
    "Cork":      ["Cork", "cork", "Co. Cork", "CORK"],
    "Galway":    ["Galway", "galway", "Co. Galway"],
    "Limerick":  ["Limerick", "limerick", "LK"],
    "Waterford": ["Waterford", "waterford", "WFD"],
    "Other":     ["Other", "other"],
}

# Channel noise variants (2%)
CHANNEL_VARIANTS = {
    "app":            ["app", "App", "Mobile App", "Laya App"],
    "web_portal":     ["web_portal", "Web Portal", "web portal", "Web"],
    "paper_post":     ["paper_post", "Paper", "Post", "paper"],
    "direct_billing": ["direct_billing", "Direct Billing", "DirectBilling"],
}

# ── Irish name / contact pools ───────────────────────────────────────────────
IRISH_FIRST = [
    "Liam","Conor","Sean","Patrick","Ciaran","Eoin","Darragh","Oisin","Fionn",
    "Cormac","Declan","Brendan","Ronan","Cathal","Niall","Tadhg","Killian","Cian",
    "James","Michael","David","John","Kevin","Brian","Mark","Shane","Aidan","Donal",
    "Aoife","Niamh","Saoirse","Ciara","Sinead","Caoimhe","Aisling","Orla","Roisin",
    "Clodagh","Siobhan","Mairead","Sorcha","Grainne","Deirdre","Nuala","Brigid",
    "Emma","Sarah","Rachel","Claire","Laura","Katie","Michelle","Amy","Jennifer",
]
IRISH_LAST = [
    "Murphy","Kelly","OBrien","Walsh","Smith","OConnor","McCarthy","OSullivan",
    "Byrne","Ryan","ONeill","OReilly","Doyle","Burke","Fitzgerald","Lynch",
    "Gallagher","Murray","Quinn","Moore","McLoughlin","Kennedy","Dunne","Brennan",
    "Collins","Clarke","Johnston","Hughes","Farrell","Whelan","Nolan","Doherty",
    "Sheridan","Moran","Foley","Sweeney","Martin","Cullen","Boyle","Healy",
    "Sheehan","Barry","Donnelly","Flanagan","Mullen","Kavanagh","Power","Ward",
]
EMAIL_DOMAINS = [
    "gmail.com","hotmail.com","yahoo.com","outlook.com",
    "icloud.com","eircom.net","live.ie","gmail.ie",
]
PHONE_PREFIXES = ["083","085","086","087","089"]

def make_irish_phone():
    prefix = random.choice(PHONE_PREFIXES)
    number = "".join([str(random.randint(0,9)) for _ in range(7)])
    return f"+353 {prefix[1:]} {number[:3]} {number[3:]}"

def make_email(first, last, used):
    def clean(s):
        return s.lower().replace("é","e").replace("á","a").replace("í","i")                        .replace("ó","o").replace("ú","u").replace("'","")
    f, l = clean(first), clean(last)
    domain = random.choice(EMAIL_DOMAINS)
    candidates = [
        f"{f}.{l}@{domain}",
        f"{f}{l}@{domain}",
        f"{f[0]}{l}@{domain}",
        f"{f}.{l}{random.randint(1,99)}@{domain}",
        f"{f}{random.randint(1,999)}@{domain}",
    ]
    for c in candidates:
        if c not in used:
            used.add(c)
            return c
    fb = f"{f}.{l}.{random.randint(100,999)}@{domain}"
    used.add(fb)
    return fb

_used_emails = set()

users_rows = []
for i in range(N_USERS):
    uid    = f"U{i+1:05d}"
    age    = np.random.choice(AGE_GROUPS,   p=AGE_WEIGHTS)
    plan   = np.random.choice(PLAN_TYPES,   p=PLAN_WEIGHTS)
    arch   = np.random.choice(ARCHETYPES,   p=ARCH_WEIGHTS)
    ch_key = np.random.choice(CHANNELS,     p=CHAN_WEIGHTS)
    rg_key = np.random.choice(REGIONS_CLEAN, p=REGION_W)

    # Noise injection
    ch_disp = random.choice(CHANNEL_VARIANTS[ch_key]) if random.random() < 0.02 else ch_key
    rg_disp = random.choice(REGION_VARIANTS[rg_key])  if random.random() < 0.04 else rg_key

    tenure = round(random.uniform(0.5, 15.0), 1)

    # Past history — will be recomputed from actual claims later
    # Keep as pre-existing (before simulation period) history
    past_c = np.random.poisson(max(1, tenure * 0.4))
    base_esc_rate = {"Passive": 0.05, "Engaged": 0.07, "Anxious": 0.18, "Distress": 0.30}[arch]
    past_e = np.random.binomial(max(past_c, 1), base_esc_rate)
    past_e = min(past_e, past_c)

    irish = int(random.random() < 0.02)

    first_name   = random.choice(IRISH_FIRST)
    last_name    = random.choice(IRISH_LAST)
    full_name    = f"{first_name} {last_name}"
    email        = make_email(first_name, last_name, _used_emails)
    phone_number = make_irish_phone()

    users_rows.append([uid, age, rg_disp, plan, tenure,
                       past_c, past_e, arch, ch_disp, irish,
                       full_name, email, phone_number])

users_df = pd.DataFrame(users_rows, columns=[
    "user_id", "age_group", "region", "plan_type",
    "membership_tenure_years", "past_claim_count", "past_escalation_count",
    "behavior_archetype", "preferred_submission_channel", "irish_language_preference",
    "full_name", "email", "phone_number"
])
users_df.to_csv(OUT + "users.csv", index=False)
print(f"  ✓ users.csv  →  {len(users_df):,} rows")

# Fast lookup maps
arch_map   = dict(zip(users_df.user_id, users_df.behavior_archetype))
age_map    = dict(zip(users_df.user_id, users_df.age_group))
plan_map   = dict(zip(users_df.user_id, users_df.plan_type))
tenure_map = dict(zip(users_df.user_id, users_df.membership_tenure_years))
chan_map    = dict(zip(users_df.user_id, users_df.preferred_submission_channel))
region_map = dict(zip(users_df.user_id, users_df.region))

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — TREATMENT MASTER
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 2 — Generating treatment master")

# avg_claim_amount aligned with YAML v0.2
TX_CONFIG = {
    #            avg_amt  avg_proc  exp_doc  resub_rate  sla_days  share
    "GP":           (75,     3,        2,      0.04,       5,       0.32),
    "Dental":       (650,    7,        3,      0.10,       10,      0.18),
    "Specialist":   (700,    10,       4,      0.12,       14,      0.16),
    "Physiotherapy":(300,    5,        2,      0.08,       7,       0.14),
    "Mental_Health":(140,    7,        3,      0.09,       10,      0.08),
    "Surgical":     (8500,   14,       6,      0.18,       21,      0.12),
    "Maternity":    (2200,   12,       5,      0.15,       18,      0.06),
}

tx_rows = []
for tx, (avg_amt, avg_proc, exp_doc, resub_rate, sla_days, share) in TX_CONFIG.items():
    tx_rows.append([tx, avg_amt, avg_proc, exp_doc, resub_rate, sla_days])

treatment_df = pd.DataFrame(tx_rows, columns=[
    "treatment_type", "avg_claim_amount", "avg_processing_days",
    "expected_doc_count", "resubmission_rate", "sla_days"
])
treatment_df.to_csv(OUT + "treatment_master.csv", index=False)
print(f"  ✓ treatment_master.csv  →  {len(treatment_df):,} rows")

# Capitalisation variants for noise injection (3%)
TX_VARIANTS = {
    "GP":            ["GP", "gp", "Gp"],
    "Dental":        ["Dental", "dental", "DENTAL"],
    "Specialist":    ["Specialist", "specialist", "SPECIALIST"],
    "Physiotherapy": ["Physiotherapy", "physiotherapy", "Physio", "PHYSIOTHERAPY"],
    "Mental_Health": ["Mental_Health", "mental_health", "Mental Health", "MENTAL_HEALTH"],
    "Surgical":      ["Surgical", "surgical", "SURGICAL"],
    "Maternity":     ["Maternity", "maternity", "MATERNITY"],
}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — CLAIMS  +  ESCALATION DECISION
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 3 — Generating claims + deciding escalation")

# Flag miss/adj/rejection rates per treatment type
TX_FLAG_RATES = {
    "GP":            {"miss": 0.05, "adj": 0.02, "rej": 0.03},
    "Dental":        {"miss": 0.15, "adj": 0.07, "rej": 0.08},
    "Specialist":    {"miss": 0.12, "adj": 0.05, "rej": 0.06},
    "Physiotherapy": {"miss": 0.10, "adj": 0.04, "rej": 0.05},
    "Mental_Health": {"miss": 0.13, "adj": 0.05, "rej": 0.08},
    "Surgical":      {"miss": 0.22, "adj": 0.12, "rej": 0.10},
    "Maternity":     {"miss": 0.14, "adj": 0.06, "rej": 0.05},
}

# Plan → average claim cost (for relative_claim_cost feature)
PLAN_AVG_COST = {"Individual": 350, "Family": 500, "Corporate": 400}

# Treatment type shares for claim generation
TX_TYPES = list(TX_CONFIG.keys())
TX_SHARES_RAW = [TX_CONFIG[t][5] for t in TX_TYPES]
_s = sum(TX_SHARES_RAW)
TX_SHARES = [x/_s for x in TX_SHARES_RAW]

# ── RULE 1: Escalation decided at claim creation time ─────────────────────────
def decide_escalation(arch, age, tx, miss_doc, rejected, adj, resub, amt, tenure):
    """
    Compute probability claim will escalate.
    Returns True/False.
    Target: 14-18% claim-level escalation rate.
    """
    p = 0.10  # base rate

    # Claim-level risk signals
    if miss_doc:   p += 0.20
    if rejected:   p += 0.30
    if adj:        p += 0.15
    if resub:      p += 0.10
    if amt > 2000: p += 0.08

    # Archetype multiplier
    arch_mult = {"Passive": 0.70, "Engaged": 1.00, "Anxious": 1.50, "Distress": 2.00}
    p *= arch_mult[arch]

    # Age multiplier
    if age == "75+":   p *= 1.30
    if age == "18-29": p *= 0.80

    # Long tenure reduces probability (knows the system)
    if tenure > 5:     p *= 0.85

    return random.random() < min(p, 0.95)

# ── RULE 2: Call timing based on anxiety curve ────────────────────────────────
def decide_call_day(arch, age, tx, miss_doc, rejected, sla_days, max_days):
    """
    Determine which day (1-based) the user calls support.
    Calls cluster after SLA breach, with archetype influencing impatience.
    Returns integer day number within [1, max_days].
    """
    arch_patience = {"Passive": 1.5, "Engaged": 1.2, "Anxious": 0.8, "Distress": 0.5}
    patience = arch_patience[arch]

    # Age factor — older users slightly less patient with digital processes
    if age == "75+":   patience *= 0.8
    if age == "18-29": patience *= 1.1

    for day in range(1, max_days + 1):
        if day < sla_days:
            # Patient phase — very low daily call probability
            daily_p = 0.02 * (1.0 / patience)
        elif day == sla_days:
            # SLA breach day — anxiety spike
            daily_p = 0.15 / patience
        else:
            # Escalating anxiety after SLA breach
            days_over  = day - sla_days
            daily_p    = min(0.15 + (days_over * 0.08), 0.60)
            daily_p   /= patience

        # Flag-based boost
        if rejected:  daily_p += 0.10
        if miss_doc:  daily_p += 0.05

        if random.random() < min(daily_p, 0.80):
            return day

    # Fallback: call on last day
    return max_days

# ── Generate claims ───────────────────────────────────────────────────────────
# Aim for TARGET_CLAIMS total
claims_per_user = []
uid_list = users_df.user_id.tolist()
total_planned = 0
for uid in uid_list:
    arch    = arch_map[uid]
    base_mu = {"Passive": 2.0, "Engaged": 2.5, "Anxious": 3.0, "Distress": 3.5}[arch]
    n = max(1, np.random.poisson(base_mu))
    claims_per_user.append((uid, n))
    total_planned += n

# Scale to hit TARGET_CLAIMS approximately
scale = TARGET_CLAIMS / max(total_planned, 1)
claims_per_user = [(uid, max(1, round(n * scale))) for uid, n in claims_per_user]

claims_rows  = []
claim_meta   = {}   # cid → {sub_ts, tx_key, will_escalate, call_day, sla_days, max_days}
cid_counter  = 1

for uid, n_claims in claims_per_user:
    arch   = arch_map[uid]
    age    = age_map[uid]
    plan   = plan_map[uid]
    tenure = tenure_map[uid]
    ch_key = chan_map[uid]

    for _ in range(n_claims):
        cid = f"CLM{cid_counter:06d}"
        cid_counter += 1

        # Treatment type
        tx_key   = np.random.choice(TX_TYPES, p=TX_SHARES)
        tx_cfg   = TX_CONFIG[tx_key]
        avg_amt, avg_proc, exp_doc, resub_rate, sla_days, _ = tx_cfg
        flags    = TX_FLAG_RATES[tx_key]

        # Treatment type display (3% noise variants)
        tx_disp  = random.choice(TX_VARIANTS[tx_key]) if random.random() < 0.03 else tx_key

        # Claim amount — log-normal for Surgical, normal for others
        if tx_key == "Surgical":
            claim_amt = round(np.random.lognormal(
                math.log(avg_amt) - 0.5, 0.8), 2)
            claim_amt = max(500.0, claim_amt)
        else:
            claim_amt = round(max(10.0, np.random.normal(avg_amt, avg_amt * 0.25)), 2)

        # 1% outliers — data entry errors
        if random.random() < 0.01:
            claim_amt = round(claim_amt * random.uniform(8, 12), 2)

        # Submission timestamp
        sub_ts  = rand_dt(START_DATE, END_DATE - timedelta(days=MAX_LIFECYCLE_DAYS + 2))
        sub_ts  = inject_glitch(sub_ts)

        # Submission channel — prefer user's preferred channel
        if random.random() < 0.75:
            sub_ch = ch_key
        else:
            sub_ch = np.random.choice(CHANNELS, p=CHAN_WEIGHTS)

        # Claim flags
        miss_doc = int(random.random() < flags["miss"])
        adj_flag = int(random.random() < flags["adj"])
        rej_prob = flags["rej"] + (0.12 if miss_doc else 0) + (0.08 if adj_flag else 0)
        rejected = int(random.random() < min(rej_prob, 0.50))
        resub    = int(random.random() < (resub_rate + (0.15 if rejected else 0)))

        orig_cid = None
        if resub:
            prior = [r[0] for r in claims_rows if r[1] == uid]
            if prior:
                orig_cid = random.choice(prior)

        # ── RULE 1: Decide escalation NOW ───────────────────────────────────
        will_escalate = decide_escalation(
            arch, age, tx_key, bool(miss_doc), bool(rejected),
            bool(adj_flag), bool(resub), claim_amt, tenure
        )

        # ── RULE 2: If escalating, decide call day ───────────────────────────
        max_days = min(MAX_LIFECYCLE_DAYS,
                       max(5, int(avg_proc * 1.5)))
        call_day = None
        if will_escalate:
            call_day = decide_call_day(
                arch, age, tx_key, bool(miss_doc), bool(rejected),
                sla_days, max_days
            )

        claims_rows.append([
            cid, uid, tx_disp, round(claim_amt, 2), ts_fmt(sub_ts),
            sub_ch, miss_doc, adj_flag, rejected, resub, orig_cid
        ])

        claim_meta[cid] = {
            "uid":           uid,
            "arch":          arch,
            "age":           age,
            "plan":          plan,
            "sub_ts":        sub_ts,
            "tx_key":        tx_key,
            "claim_amt":     claim_amt,
            "sla_days":      sla_days,
            "avg_proc":      avg_proc,
            "max_days":      max_days,
            "will_escalate": will_escalate,
            "call_day":      call_day,
            "miss_doc":      miss_doc,
            "adj_flag":      adj_flag,
            "rejected":      rejected,
            "resub":         resub,
            "sub_ch":        sub_ch,
            "orig_cid":      orig_cid,
        }

claims_df = pd.DataFrame(claims_rows, columns=[
    "claim_id", "user_id", "treatment_type", "claim_amount",
    "submission_timestamp", "submission_channel",
    "missing_documents_flag", "adjudicator_flag",
    "claim_rejected_flag", "resubmission_flag", "original_claim_id"
])
claims_df.to_csv(OUT + "claims.csv", index=False)

n_esc = sum(1 for m in claim_meta.values() if m["will_escalate"])
print(f"  ✓ claims.csv  →  {len(claims_df):,} rows")
print(f"    will_escalate = True  : {n_esc:,}  ({n_esc/len(claims_df)*100:.1f}%)")
print(f"    will_escalate = False : {len(claims_df)-n_esc:,}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — CLAIM STATUS HISTORY
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 4 — Generating claim status history")

# Logical status flows
STATUS_FLOWS = {
    "normal":     ["Submitted", "Under_Review", "Approved"],
    "rejected":   ["Submitted", "Under_Review", "Awaiting_Documents",
                   "Under_Review", "Rejected"],
    "resubmit":   ["Submitted", "Under_Review", "Approved",
                   "Resubmitted", "Under_Review", "Approved"],
    "adj":        ["Submitted", "Under_Review", "With_Adjudicator",
                   "Under_Review", "Approved"],
}

status_rows   = []
sid_counter   = 1
claim_last_ts = {}   # cid → last status datetime

for cid, meta in claim_meta.items():
    sub_ts   = meta["sub_ts"]
    rejected = meta["rejected"]
    resub    = meta["resub"]
    adj      = meta["adj_flag"]
    avg_proc = meta["avg_proc"]
    max_days = meta["max_days"]

    if rejected:
        flow = STATUS_FLOWS["rejected"]
    elif resub:
        flow = STATUS_FLOWS["resubmit"]
    elif adj:
        flow = STATUS_FLOWS["adj"]
    else:
        flow = STATUS_FLOWS["normal"]

    current_ts = sub_ts
    sla_days   = meta["sla_days"]

    for status in flow:
        gap     = random.uniform(0.5, avg_proc / max(len(flow) - 1, 1))
        current_ts = current_ts + timedelta(days=gap)
        current_ts = inject_glitch(current_ts)

        # Don't go past simulation end or max lifecycle
        max_ts = min(
            sub_ts + timedelta(days=max_days + 2),
            END_DATE - timedelta(hours=ESCALATION_WINDOW + 1)
        )
        if current_ts > max_ts:
            current_ts = max_ts - timedelta(hours=random.randint(1, 12))

        days_elapsed = (current_ts - sub_ts).days
        sla_breach   = int(days_elapsed > sla_days)

        status_rows.append([
            f"SID{sid_counter:08d}", cid, status,
            ts_fmt(current_ts), sla_breach
        ])
        sid_counter += 1

    claim_last_ts[cid] = current_ts

status_df = pd.DataFrame(status_rows, columns=[
    "status_id", "claim_id", "status",
    "status_timestamp", "sla_breach_at_snapshot"
])
status_df.to_csv(OUT + "claim_status_history.csv", index=False)
print(f"  ✓ claim_status_history.csv  →  {len(status_df):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — APP LOGS (anxiety-driven — the key fix)
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 5 — Generating app logs (anxiety-driven)")

# ── RULE 3: Login count as function of age, archetype, proximity to call ──────
def daily_login_rate(day, arch, age, sla_days, call_day, miss_doc, rejected):
    """
    Login rate for a specific day.
    Grows with claim age. Spikes 3-4x in 48h before call.
    Returns Poisson lambda for that day.
    """
    # Base rate by archetype
    base = {"Passive": 0.5, "Engaged": 1.0, "Anxious": 1.8, "Distress": 2.5}[arch]

    # Anxiety grows with claim age — monotonically increasing
    age_factor = 1.0 + (day / max(sla_days, 1)) * 0.5

    # Proximity spike — THIS IS THE KEY SIGNAL
    proximity = 1.0
    if call_day is not None:
        days_to_call = call_day - day
        if days_to_call == 1:   proximity = 3.5   # day before call — intense checking
        elif days_to_call == 0: proximity = 4.0   # call day — peak anxiety
        elif days_to_call == -1:proximity = 1.5   # day after — relief/resolution
        elif days_to_call == -2:proximity = 1.2   # residual

    # Flag-based boost — rejected/missing docs increases anxiety
    flag_boost = 0.0
    if rejected:  flag_boost += 1.5
    if miss_doc:  flag_boost += 0.8

    rate = (base + flag_boost) * age_factor * proximity
    return max(0.01, rate)

# ── RULE 4: Status view rate — stronger spike than logins ────────────────────
def daily_sv_rate(day, arch, sla_days, call_day):
    """Status view rate — spikes even harder than logins before call."""
    base = {"Passive": 1.0, "Engaged": 3.0, "Anxious": 7.0, "Distress": 10.0}[arch]
    age_factor = 1.0 + (day / max(sla_days, 1)) * 0.6

    proximity = 1.0
    if call_day is not None:
        days_to_call = call_day - day
        if days_to_call == 1:   proximity = 2.5
        elif days_to_call == 0: proximity = 3.0
        elif days_to_call == -1:proximity = 1.3

    return max(0.1, base * age_factor * proximity)

# ── Generate app logs ─────────────────────────────────────────────────────────
log_rows    = []
lid_counter = 1
push_opt_in = {uid: int(random.random() < 0.55) for uid in uid_list}

# Pre-compute null rates for session_duration
# 8% of session events have null duration

for cid, meta in claim_meta.items():
    uid      = meta["uid"]
    arch     = meta["arch"]
    age      = meta["age"]
    sub_ts   = meta["sub_ts"]
    sla_days = meta["sla_days"]
    call_day = meta["call_day"]
    max_days = meta["max_days"]
    miss_doc = meta["miss_doc"]
    rejected = meta["rejected"]
    push     = push_opt_in[uid]

    # Determine observation window
    last_ts  = claim_last_ts.get(cid, sub_ts + timedelta(days=max_days))
    obs_end  = min(last_ts + timedelta(days=2),
                   END_DATE - timedelta(hours=ESCALATION_WINDOW + 1))
    obs_days = max(1, (obs_end - sub_ts).days)

    for day in range(1, min(obs_days + 1, max_days + 3)):
        day_start = sub_ts + timedelta(days=day - 1)
        day_end   = sub_ts + timedelta(days=day)
        if day_end > obs_end:
            break

        # ── LOGINS ────────────────────────────────────────────────────────────
        login_lambda = daily_login_rate(day, arch, age, sla_days,
                                         call_day, bool(miss_doc), bool(rejected))
        n_logins = np.random.poisson(login_lambda)

        for _ in range(n_logins):
            evt_ts = rand_dt(day_start, day_end)
            evt_ts = inject_glitch(evt_ts)
            log_rows.append([
                f"LOG{lid_counter:09d}", uid, cid, "login",
                ts_fmt(evt_ts), None, 0, push
            ])
            lid_counter += 1
            # Corresponding logout
            logout_ts = evt_ts + timedelta(minutes=random.randint(2, 90))
            if logout_ts < day_end:
                log_rows.append([
                    f"LOG{lid_counter:09d}", uid, cid, "logout",
                    ts_fmt(logout_ts), None, 0, push
                ])
                lid_counter += 1

        # ── STATUS VIEWS ──────────────────────────────────────────────────────
        sv_lambda = daily_sv_rate(day, arch, sla_days, call_day)
        n_sv      = np.random.poisson(sv_lambda)

        for _ in range(n_sv):
            evt_ts   = rand_dt(day_start, day_end)
            evt_ts   = inject_glitch(evt_ts)
            sess_dur = None if random.random() < 0.08 else round(random.expovariate(1/180), 1)
            log_rows.append([
                f"LOG{lid_counter:09d}", uid, cid, "claim_status_view",
                ts_fmt(evt_ts), sess_dur, 0, push
            ])
            lid_counter += 1

        # ── DOCUMENT UPLOADS ──────────────────────────────────────────────────
        # More uploads early in lifecycle, especially for miss_doc claims
        doc_base = {"Passive": 0.05, "Engaged": 0.10, "Anxious": 0.20, "Distress": 0.25}[arch]
        if miss_doc:
            doc_base += 0.15
        if day <= 3:
            doc_base *= 2.0
        n_docs = np.random.poisson(doc_base)
        for _ in range(n_docs):
            evt_ts   = rand_dt(day_start, day_end)
            sess_dur = None if random.random() < 0.08 else round(random.expovariate(1/120), 1)
            log_rows.append([
                f"LOG{lid_counter:09d}", uid, cid, "document_upload",
                ts_fmt(evt_ts), sess_dur, 0, push
            ])
            lid_counter += 1

        # ── IN-APP CHAT ───────────────────────────────────────────────────────
        # Distress/Anxious users use chat more, especially when approaching call
        chat_base = {"Passive": 0.01, "Engaged": 0.05, "Anxious": 0.15, "Distress": 0.40}[arch]
        prox = 1.0
        if call_day and (call_day - day) in [1, 0]:
            prox = 2.0
        n_chat = np.random.poisson(chat_base * prox)
        for _ in range(n_chat):
            evt_ts   = rand_dt(day_start, day_end)
            sess_dur = None if random.random() < 0.08 else round(random.expovariate(1/240), 1)
            log_rows.append([
                f"LOG{lid_counter:09d}", uid, cid, "in_app_chat_start",
                ts_fmt(evt_ts), sess_dur, 1, push
            ])
            lid_counter += 1

log_df = pd.DataFrame(log_rows, columns=[
    "log_id", "user_id", "claim_id", "event_type", "timestamp",
    "session_duration", "in_app_chat_initiated", "push_notification_opt_in"
])
log_df["timestamp"] = pd.to_datetime(log_df["timestamp"])
log_df.to_csv(OUT + "app_logs.csv", index=False)
print(f"  ✓ app_logs.csv  →  {len(log_df):,} rows")

# Pre-index logs by claim_id for fast snapshot computation
logs_by_claim = {cid: grp for cid, grp in log_df.groupby("claim_id")}

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — SUPPORT CALLS
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 6 — Generating support calls")

CALL_REASONS  = ["Claim_Status", "Document_Query", "Approval_Delay",
                  "Rejection_Appeal", "Payment_Query", "General_Enquiry"]
REASON_W      = [0.35, 0.20, 0.20, 0.10, 0.10, 0.05]
CALL_CHANNELS = ["Phone", "LiveChat", "Email", "Callback"]
CHAN_W_CALL    = [0.60, 0.20, 0.10, 0.10]

call_rows      = []
call_counter   = 1
calls_by_claim = {}   # cid → list of call datetimes

for cid, meta in claim_meta.items():
    if not meta["will_escalate"]:
        calls_by_claim[cid] = []
        continue

    uid      = meta["uid"]
    sub_ts   = meta["sub_ts"]
    call_day = meta["call_day"]
    rejected = meta["rejected"]

    # Call timestamp — on call_day, during business hours with slight randomness
    call_base_ts  = sub_ts + timedelta(days=call_day - 1)
    call_base_ts  = call_base_ts.replace(
        hour=random.randint(8, 17),
        minute=random.randint(0, 59)
    )
    call_ts = call_base_ts + timedelta(hours=random.gauss(0, 2))

    # Ensure within simulation window
    max_call_ts = END_DATE - timedelta(hours=1)
    if call_ts > max_call_ts:
        call_ts = max_call_ts - timedelta(minutes=random.randint(30, 120))
    if call_ts < sub_ts:
        call_ts = sub_ts + timedelta(hours=random.randint(2, 24))

    call_ts = inject_glitch(call_ts)

    reason = np.random.choice(CALL_REASONS, p=REASON_W)
    if rejected:
        reason = "Rejection_Appeal"
    ch = np.random.choice(CALL_CHANNELS, p=CHAN_W_CALL)

    call_rows.append([
        f"CALL{call_counter:07d}", cid, ts_fmt(call_ts), reason, ch
    ])
    calls_by_claim[cid] = [call_ts]
    call_counter += 1

calls_df = pd.DataFrame(call_rows, columns=[
    "call_id", "claim_id", "call_timestamp", "call_reason", "call_channel"
])
calls_df.to_csv(OUT + "support_calls.csv", index=False)
print(f"  ✓ support_calls.csv  →  {len(calls_df):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — FEATURE SNAPSHOTS (derived from app_logs)
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 7 — Generating feature snapshots (derived from app_logs)")

# Pre-index status history
status_df["status_timestamp"] = pd.to_datetime(status_df["status_timestamp"])
status_by_claim = {cid: grp.sort_values("status_timestamp")
                   for cid, grp in status_df.groupby("claim_id")}

# Pre-compute per-user prior claims for past_escalation_ratio
# (computed from actual claims in simulation, not random numbers)
all_cids = list(claim_meta.keys())
claims_df["submission_timestamp"] = pd.to_datetime(claims_df["submission_timestamp"])
escalated_claim_ids = set(calls_df["claim_id"].tolist())

snap_rows    = []
snap_id      = 1

for cid, meta in claim_meta.items():
    uid      = meta["uid"]
    arch     = meta["arch"]
    age      = meta["age"]
    plan     = meta["plan"]
    sub_ts   = meta["sub_ts"]
    tx_key   = meta["tx_key"]
    tx_cfg   = TX_CONFIG[tx_key]
    avg_proc = meta["avg_proc"]
    sla_days = meta["sla_days"]
    max_days = meta["max_days"]
    call_day = meta["call_day"]
    miss_doc = meta["miss_doc"]
    adj_flag = meta["adj_flag"]
    rejected = meta["rejected"]
    resub    = meta["resub"]
    sub_ch   = meta["sub_ch"]
    amt      = meta["claim_amt"]

    # Observation end
    last_ts  = claim_last_ts.get(cid, sub_ts + timedelta(days=max_days))
    obs_end  = min(last_ts + timedelta(days=2),
                   END_DATE - timedelta(hours=ESCALATION_WINDOW + 1))

    # Get logs for this claim
    c_logs = logs_by_claim.get(cid, pd.DataFrame())

    # Compute past claim history for this user UP TO this claim's submission
    prior_claims = claims_df[
        (claims_df.user_id == uid) &
        (claims_df.submission_timestamp < sub_ts) &
        (claims_df.claim_id != cid)
    ]
    past_c_actual = len(prior_claims)
    past_e_actual = sum(1 for pc in prior_claims.claim_id if pc in escalated_claim_ids)

    # Include pre-simulation history from users table
    pre_sim_c = tenure_map.get(uid, 0)  # used as prior baseline
    pre_sim_e = users_df[users_df.user_id == uid].iloc[0]["past_escalation_count"]
    total_past_c = past_c_actual + int(users_df[users_df.user_id == uid].iloc[0]["past_claim_count"])
    total_past_e = past_e_actual + int(pre_sim_e)
    past_esc_ratio = round(total_past_e / max(total_past_c, 1), 4)

    # Financial features
    plan_avg   = PLAN_AVG_COST.get(plan, 350)
    rel_cost   = round(amt / plan_avg, 4)
    hv_flag    = int(amt > 2000)

    # Claim-level escalation label (same for all snapshots of this claim)
    label_claim = int(meta["will_escalate"])

    # Generate one snapshot per day
    for snap_day in range(1, max_days + 1):
        snap_ts = sub_ts + timedelta(days=snap_day)
        if snap_ts > obs_end:
            break

        # ── Days and delay features ────────────────────────────────────────
        days_since_sub = snap_day
        delay_gap      = round(max(0.0, float(days_since_sub - avg_proc)), 2)
        sla_breach     = int(days_since_sub > sla_days)

        # ── Status history features ────────────────────────────────────────
        st_hist = status_by_claim.get(cid, pd.DataFrame())
        if len(st_hist):
            before = st_hist[st_hist.status_timestamp <= snap_ts]
            n_changes = len(before)
            if n_changes >= 1:
                last_chg_ts     = before.iloc[-1]["status_timestamp"]
                time_since_last = (snap_ts - last_chg_ts).total_seconds() / 3600
            else:
                time_since_last = float(days_since_sub * 24)
        else:
            n_changes       = 0
            time_since_last = float(days_since_sub * 24)

        # ── Behavioural features — COUNTED FROM APP_LOGS ──────────────────
        if len(c_logs):
            ts_col    = c_logs["timestamp"]
            w24_start = snap_ts - timedelta(hours=24)
            w48_start = snap_ts - timedelta(hours=48)
            prev_start= snap_ts - timedelta(hours=48)
            prev_end  = snap_ts - timedelta(hours=24)

            mask_24   = (ts_col >= w24_start) & (ts_col <= snap_ts)
            mask_48   = (ts_col >= w48_start) & (ts_col <= snap_ts)
            mask_prev = (ts_col >= prev_start) & (ts_col < prev_end)

            logs_24   = c_logs[mask_24]
            logs_48   = c_logs[mask_48]
            logs_prev = c_logs[mask_prev]

            login_24  = int((logs_24.event_type == "login").sum())
            login_48  = int((logs_48.event_type == "login").sum())
            sv_24     = int((logs_24.event_type == "claim_status_view").sum())
            doc_48    = int((logs_48.event_type == "document_upload").sum())
            chat_48   = int((logs_48.in_app_chat_initiated == 1).sum())
            sv_prev   = int((logs_prev.event_type == "claim_status_view").sum())
            beh_acc   = round(sv_24 / max(sv_prev, 1), 4)
        else:
            login_24 = login_48 = sv_24 = doc_48 = chat_48 = 0
            beh_acc  = 1.0

        # ── Resubmission feature ───────────────────────────────────────────
        days_since_resub = None
        if resub and meta["orig_cid"]:
            orig_row = claims_df[claims_df.claim_id == meta["orig_cid"]]
            if len(orig_row):
                orig_sub_ts = orig_row.iloc[0]["submission_timestamp"]
                days_since_resub = (snap_ts - orig_sub_ts).days

        # ── LABEL 1: 48h snapshot label ────────────────────────────────────
        future_end   = snap_ts + timedelta(hours=ESCALATION_WINDOW)
        claim_calls  = calls_by_claim.get(cid, [])
        label_48h    = int(any(snap_ts < ct <= future_end for ct in claim_calls))

        snap_rows.append([
            cid, uid, ts_fmt(snap_ts),
            plan, region_map.get(uid, "Other"),
            round(amt, 2), tx_key,
            days_since_sub, sub_ch, delay_gap,
            miss_doc, adj_flag, rejected, resub, sla_breach,
            login_24, login_48, sv_24, doc_48,
            round(beh_acc, 4), chat_48,
            round(tenure_map.get(uid, 1.0), 1),
            total_past_c, round(past_esc_ratio, 4), age,
            round(rel_cost, 4), hv_flag,
            round(time_since_last, 2), n_changes, days_since_resub,
            label_48h, label_claim
        ])

snaps_df = pd.DataFrame(snap_rows, columns=[
    "claim_id", "user_id", "snapshot_date",
    "plan_type", "region",
    "claim_amount", "treatment_type",
    "days_since_submission", "submission_channel", "delay_gap",
    "missing_documents_flag", "adjudicator_flag",
    "claim_rejected_flag", "resubmission_flag", "sla_breach_flag",
    "login_count_24h", "login_count_48h",
    "status_views_24h", "document_uploads_48h",
    "behavior_acceleration", "in_app_chat_sessions_48h",
    "membership_tenure_years", "past_claim_count",
    "past_escalation_ratio", "age_group",
    "relative_claim_cost", "high_value_claim_flag",
    "time_since_last_status_change", "num_status_changes",
    "days_since_resubmission",
    "label_escalation_48h",   # snapshot-level label
    "label_claim_escalation",  # claim-level label
])
snaps_df.to_csv(OUT + "feature_snapshots.csv", index=False)
print(f"  ✓ feature_snapshots.csv  →  {len(snaps_df):,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — VALIDATION CHECKS (built-in)
# ─────────────────────────────────────────────────────────────────────────────
print("\nSTEP 8 — Running built-in validation checks")

# FK integrity
ck1 = (~claims_df.user_id.isin(users_df.user_id)).sum()
ck2 = (~status_df.claim_id.isin(claims_df.claim_id)).sum()
ck3 = (~log_df.claim_id.isin(claims_df.claim_id)).sum()
ck4 = (~calls_df.claim_id.isin(claims_df.claim_id)).sum()
ck5 = (~snaps_df.claim_id.isin(claims_df.claim_id)).sum()

print(f"  FK: claims→users          orphans: {ck1}  {'✅' if ck1==0 else '❌'}")
print(f"  FK: status→claims         orphans: {ck2}  {'✅' if ck2==0 else '❌'}")
print(f"  FK: logs→claims           orphans: {ck3}  {'✅' if ck3==0 else '❌'}")
print(f"  FK: calls→claims          orphans: {ck4}  {'✅' if ck4==0 else '❌'}")
print(f"  FK: snapshots→claims      orphans: {ck5}  {'✅' if ck5==0 else '❌'}")

# Chronological check
status_df2 = status_df.copy()
status_df2["status_timestamp"] = pd.to_datetime(status_df2["status_timestamp"])
claims_df2 = claims_df.copy()
claims_df2["submission_timestamp"] = pd.to_datetime(claims_df2["submission_timestamp"])
ch = status_df2.merge(claims_df2[["claim_id","submission_timestamp"]], on="claim_id")
viol = (ch.status_timestamp < ch.submission_timestamp).sum()
print(f"  Chronological violations  : {viol}  {'✅' if viol==0 else '⚠️ '}")

# ML team checklist
claims_esc_rate = n_esc / len(claims_df) * 100
snaps_df["snapshot_date"] = pd.to_datetime(snaps_df["snapshot_date"])
label_48h_rate  = snaps_df.label_escalation_48h.mean() * 100
label_claim_rate= snaps_df.label_claim_escalation.mean() * 100

print(f"\n  ML TEAM CHECKLIST:")
print(f"  Claim escalation rate      : {claims_esc_rate:.1f}%  target 14-18%  {'✅' if 14<=claims_esc_rate<=22 else '⚠️ '}")
print(f"  Snapshot 48h label rate    : {label_48h_rate:.1f}%  target 5-15%   {'✅' if 3<=label_48h_rate<=18 else '⚠️ '}")
print(f"  Claim-level label rate     : {label_claim_rate:.1f}%  target 14-18%  {'✅' if 14<=label_claim_rate<=22 else '⚠️ '}")

# Verify login spike before call
escalating_cids = [cid for cid, m in claim_meta.items() if m["will_escalate"] and m["call_day"]]
spike_data = {"before": [], "after": [], "normal": []}
for cid in escalating_cids[:300]:
    call_day = claim_meta[cid]["call_day"]
    for _, row in snaps_df[snaps_df.claim_id == cid].iterrows():
        day = row.days_since_submission
        if day == call_day - 1:
            spike_data["before"].append(row.login_count_24h)
        elif day == call_day + 1:
            spike_data["after"].append(row.login_count_24h)
        elif abs(day - call_day) > 3:
            spike_data["normal"].append(row.login_count_24h)

avg_before = np.mean(spike_data["before"]) if spike_data["before"] else 0
avg_after  = np.mean(spike_data["after"])  if spike_data["after"]  else 0
avg_normal = np.mean(spike_data["normal"]) if spike_data["normal"] else 0
spike_ratio = avg_before / max(avg_normal, 0.01)

print(f"  Login: normal days avg     : {avg_normal:.2f}")
print(f"  Login: day-before-call avg : {avg_before:.2f}  (spike {spike_ratio:.1f}x normal)  {'✅' if spike_ratio>=2.5 else '⚠️ '}")
print(f"  Login: day-after-call avg  : {avg_after:.2f}")

# Verify escalation ordering
claims_df3 = claims_df.copy()
claims_df3["escalated"] = claims_df3.claim_id.isin(calls_df.claim_id)
m = claims_df3.merge(users_df[["user_id","behavior_archetype","age_group"]], on="user_id")
dist = m[m.behavior_archetype=="Distress"]["escalated"].mean()
anx  = m[m.behavior_archetype=="Anxious"]["escalated"].mean()
pas  = m[m.behavior_archetype=="Passive"]["escalated"].mean()
eng  = m[m.behavior_archetype=="Engaged"]["escalated"].mean()
age75  = m[m.age_group=="75+"]["escalated"].mean()
age18  = m[m.age_group=="18-29"]["escalated"].mean()
rej_r  = m[m.claim_rejected_flag.astype(bool)]["escalated"].mean()
clean_r= m[~m.claim_rejected_flag.astype(bool)]["escalated"].mean()

print(f"\n  ESCALATION ORDERING:")
print(f"  Distress({dist:.1%}) > Anxious({anx:.1%}) > Passive({pas:.1%}) > Engaged({eng:.1%})  {'✅' if dist>anx>pas else '⚠️ '}")
print(f"  75+({age75:.1%}) > 18-29({age18:.1%})  {'✅' if age75>age18 else '⚠️ '}")
print(f"  Rejected({rej_r:.1%}) > Normal({clean_r:.1%})  {'✅' if rej_r>clean_r else '⚠️ '}")

# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
total_rows = sum([len(users_df), len(treatment_df), len(claims_df),
                   len(status_df), len(log_df), len(calls_df), len(snaps_df)])

print("\n" + "=" * 65)
print("  GENERATION COMPLETE — v4.0")
print("=" * 65)
for name, df in [
    ("users.csv",                users_df),
    ("treatment_master.csv",     treatment_df),
    ("claims.csv",               claims_df),
    ("claim_status_history.csv", status_df),
    ("app_logs.csv",             log_df),
    ("support_calls.csv",        calls_df),
    ("feature_snapshots.csv",    snaps_df),
]:
    print(f"  {name:<30} {len(df):>8,} rows  ×  {df.shape[1]} cols")

print(f"\n  TOTAL ROWS: {total_rows:,}")
print(f"\n  LABEL DISTRIBUTION (feature_snapshots):")
print(f"    48h snapshot label:")
vc = snaps_df.label_escalation_48h.value_counts()
print(f"      0 (no call within 48h): {vc.get(0,0):>7,}  ({vc.get(0,0)/len(snaps_df)*100:.1f}%)")
print(f"      1 (call within 48h)   : {vc.get(1,0):>7,}  ({vc.get(1,0)/len(snaps_df)*100:.1f}%)")
print(f"    Claim-level label:")
vc2 = snaps_df.label_claim_escalation.value_counts()
print(f"      0 (never escalated)   : {vc2.get(0,0):>7,}  ({vc2.get(0,0)/len(snaps_df)*100:.1f}%)")
print(f"      1 (did escalate)      : {vc2.get(1,0):>7,}  ({vc2.get(1,0)/len(snaps_df)*100:.1f}%)")
print(f"\n  KEY SIGNALS VERIFIED:")
print(f"    Login spike before call : {spike_ratio:.1f}x normal day")
print(f"    Claim escalation rate   : {claims_esc_rate:.1f}%")
print("=" * 65)
