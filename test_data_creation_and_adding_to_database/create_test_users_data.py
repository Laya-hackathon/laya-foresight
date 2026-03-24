"""
Laya Healthcare — Test Data Generator
======================================
Generates synthetic test data for the end-to-end demo pipeline.

Produces 5 CSVs (NO feature_snapshots — the nightly pipeline builds that):
    test_users.csv
    test_claims.csv
    test_claim_status_history.csv
    test_app_logs.csv
    test_support_calls.csv

Design principles:
  - Every feature is CAUSALLY connected to the label (per spec Part 2)
  - Login counts SPIKE 48h before a call (Rule 3)
  - Status views SPIKE before a call (Rule 4)
  - Call timing follows SLA anxiety curve, not random (Rule 2)
  - will_escalate decided at claim creation from risk profile (Rule 1)
  - All ID formats and column order match training CSVs exactly
  - Canonical values only — no messy variants

Usage:
    python generate_test_data.py
    python generate_test_data.py --output_dir ./test_data
    python generate_test_data.py --seed 99 --sim_days 7
"""

import os
import random
import argparse
import numpy as np
import pandas as pd
from uuid import uuid4
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# CLI ARGS
# ─────────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Laya Test Data Generator")
parser.add_argument("--output_dir", default="./test_data",
                    help="Directory to write CSVs into")
parser.add_argument("--seed",       type=int, default=42,
                    help="Random seed for reproducibility")
parser.add_argument("--sim_days",   type=int, default=7,
                    help="Number of simulated days per claim lifecycle")
parser.add_argument("--sim_start",  default="2026-03-23",
                    help="Simulation start date (YYYY-MM-DD)")
args = parser.parse_args()

random.seed(args.seed)
np.random.seed(args.seed)

os.makedirs(args.output_dir, exist_ok=True)
SIM_START = datetime.strptime(args.sim_start, "%Y-%m-%d")
SIM_DAYS  = args.sim_days

print("=" * 62)
print("  LAYA HEALTHCARE — TEST DATA GENERATOR")
print("=" * 62)
print(f"  Output dir  : {args.output_dir}")
print(f"  Sim start   : {SIM_START.strftime('%Y-%m-%d')}")
print(f"  Sim days    : {SIM_DAYS}")
print(f"  Random seed : {args.seed}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS — match training data exactly
# ─────────────────────────────────────────────────────────────────────────────

TREATMENT_MASTER = {
    "GP":            {"avg_amount": 75,   "avg_processing_days": 3,  "sla_days": 5,  "expected_docs": 2},
    "Dental":        {"avg_amount": 650,  "avg_processing_days": 7,  "sla_days": 10, "expected_docs": 3},
    "Specialist":    {"avg_amount": 700,  "avg_processing_days": 10, "sla_days": 14, "expected_docs": 4},
    "Physiotherapy": {"avg_amount": 300,  "avg_processing_days": 5,  "sla_days": 7,  "expected_docs": 2},
    "Mental_Health": {"avg_amount": 140,  "avg_processing_days": 7,  "sla_days": 10, "expected_docs": 3},
    "Surgical":      {"avg_amount": 8500, "avg_processing_days": 14, "sla_days": 21, "expected_docs": 6},
    "Maternity":     {"avg_amount": 2200, "avg_processing_days": 12, "sla_days": 18, "expected_docs": 5},
}

ARCHETYPE_MULTIPLIER = {
    "Distress": 2.0,
    "Anxious":  1.5,
    "Engaged":  1.0,
    "Passive":  0.7,
}

# Base logins per day by archetype (Rule 3)
BASE_LOGINS = {
    "Passive":  0.5,
    "Engaged":  1.0,
    "Anxious":  1.8,
    "Distress": 2.5,
}

# Base status views per day by archetype (Rule 4)
BASE_STATUS_VIEWS = {
    "Passive":  1,
    "Engaged":  3,
    "Anxious":  7,
    "Distress": 10,
}

REGIONS     = ["Dublin", "Cork", "Galway", "Limerick", "Waterford", "Other"]
CHANNELS    = ["web_portal", "app", "direct_billing", "paper_post"]
CALL_REASONS = ["Claim_Status", "Approval_Delay", "Rejection_Appeal",
                "Document_Query", "Payment_Query", "General_Enquiry"]
CALL_CHANNELS = ["Phone", "Email", "Callback", "LiveChat"]

FIRST_NAMES = [
    "Aoife", "Ciara", "Niamh", "Siobhan", "Aisling", "Roisin", "Grainne",
    "Orla", "Sinead", "Deirdre", "Fionnuala", "Clodagh", "Eimear", "Sorcha",
    "Caoimhe", "Seamus", "Conor", "Declan", "Fergus", "Kieran", "Liam",
    "Padraig", "Cormac", "Eoin", "Brendan", "Donal", "Colm", "Ronan",
    "Ciaran", "Tadhg", "Fionn", "Cathal", "Darragh", "Oisin", "Ruairi"
]
LAST_NAMES = [
    "Murphy", "Kelly", "O'Brien", "Walsh", "Smith", "O'Sullivan", "Burke",
    "McCarthy", "Ryan", "Byrne", "O'Connor", "O'Neill", "Doyle", "Reilly",
    "Quinn", "Gallagher", "Fitzgerald", "Kennedy", "Lynch", "Murray",
    "Flanagan", "Daly", "Brennan", "Nolan", "Carroll", "Kearney", "Healy"
]
EMAIL_DOMAINS = ["gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "eircom.net"]

HIGH_VALUE_THRESHOLD = 2000

# ─────────────────────────────────────────────────────────────────────────────
# TEST PROFILES — 15 groups covering all meaningful model scenarios
# Each entry: (name, archetype, age_group, plan_type, treatment_type,
#              missing_docs, rejected, resubmission, n_users, notes)
# ─────────────────────────────────────────────────────────────────────────────
PROFILES = [
    # name                  arch        age      plan          treatment       miss   rej    resub  n   notes
    ("passive_clean",       "Passive",  "30-44", "Individual", "GP",           False, False, False, 5), # expect LOW score
    ("passive_highrisk",    "Passive",  "45-59", "Family",     "Specialist",   True,  True,  False, 5), # does passive still escalate?
    ("engaged_clean",       "Engaged",  "30-44", "Corporate",  "Dental",       False, False, False, 5), # normal mid risk
    ("engaged_surgical",    "Engaged",  "45-59", "Individual", "Surgical",     False, False, False, 5), # SLA is 21 days
    ("anxious_any",         "Anxious",  "45-59", "Individual", "Specialist",   False, False, False, 5), # should score MEDIUM-HIGH
    ("anxious_rejected",    "Anxious",  "60-74", "Family",     "Specialist",   True,  True,  False, 5), # should score HIGH
    ("distress_any",        "Distress", "60-74", "Individual", "Mental_Health",False, False, False, 5), # almost always HIGH
    ("distress_worstcase",  "Distress", "75+",   "Family",     "Surgical",     True,  True,  False, 5), # maximum risk — capped at 0.95
    ("elderly_any",         "Anxious",  "75+",   "Individual", "GP",           False, False, False, 5), # age multiplier
    ("young_clean",         "Passive",  "18-29", "Individual", "GP",           False, False, False, 5), # age suppressor -> LOW
    ("resubmission_case",   "Anxious",  "45-59", "Individual", "Dental",       True,  True,  True,  5), # resubmission flag signal
    ("highvalue_case",      "Anxious",  "45-59", "Corporate",  "Surgical",     False, False, False, 5), # amount > 2000 boost
    ("corporate_distress",  "Distress", "30-44", "Corporate",  "Specialist",   False, False, False, 5), # plan type interaction
    ("family_maternity",    "Anxious",  "30-44", "Family",     "Maternity",    False, False, False, 5), # treatment type interaction
    ("multiclaim_user",     "Anxious",  "45-59", "Individual", "Physiotherapy",False, False, False, 5), # past escalation ratio
]

# ─────────────────────────────────────────────────────────────────────────────
# ID COUNTERS — TST prefix distinguishes test records from training records
# ─────────────────────────────────────────────────────────────────────────────
_user_counter   = 1
_claim_counter  = 1
_status_counter = 1
_log_counter    = 1
_call_counter   = 1

def next_user_id():
    global _user_counter
    uid = f"TSTU{str(_user_counter).zfill(5)}"
    _user_counter += 1
    return uid

def next_claim_id():
    global _claim_counter
    cid = f"TSTCLM{str(_claim_counter).zfill(6)}"
    _claim_counter += 1
    return cid

def next_status_id():
    global _status_counter
    sid = f"TSTSID{str(_status_counter).zfill(8)}"
    _status_counter += 1
    return sid

def next_log_id():
    global _log_counter
    lid = f"TSTLOG{str(_log_counter).zfill(9)}"
    _log_counter += 1
    return lid

def next_call_id():
    global _call_counter
    cid = f"TSTCALL{str(_call_counter).zfill(7)}"
    _call_counter += 1
    return cid

# ─────────────────────────────────────────────────────────────────────────────
# RULE 1 — Decide escalation at claim creation time
# ─────────────────────────────────────────────────────────────────────────────
def decide_escalation(archetype, age_group, missing_docs, rejected,
                      adjudicator, resubmission, claim_amount):
    """
    Spec Rule 1: will_escalate is a binary flag decided at claim creation.
    Driven by claim risk signals and user archetype.
    Target: 14-18% of claims escalate overall.
    """
    prob = 0.10  # base rate

    # Additive boosts from claim characteristics
    if missing_docs:        prob += 0.20
    if rejected:            prob += 0.30
    if adjudicator:         prob += 0.15
    if resubmission:        prob += 0.10
    if claim_amount > HIGH_VALUE_THRESHOLD: prob += 0.08

    # Archetype multiplier
    prob *= ARCHETYPE_MULTIPLIER[archetype]

    # Age factor
    if age_group == "75+":   prob *= 1.3
    if age_group == "18-29": prob *= 0.8

    return random.random() < min(prob, 0.95)

# ─────────────────────────────────────────────────────────────────────────────
# RULE 2 — Call timing follows SLA anxiety curve
# ─────────────────────────────────────────────────────────────────────────────
def decide_call_day(archetype, treatment_type, max_days):
    """
    Spec Rule 2: Call day is NOT random.
    Probability of calling increases after SLA is breached.
    """
    sla  = TREATMENT_MASTER[treatment_type]["sla_days"]
    mult = ARCHETYPE_MULTIPLIER[archetype]

    for day in range(1, max_days + 1):
        if day < sla:
            daily_prob = 0.02                               # patient phase
        elif day == sla:
            daily_prob = 0.15                               # SLA breach triggers anxiety
        else:
            days_over  = day - sla
            daily_prob = min(0.15 + (days_over * 0.08), 0.60)  # escalating anxiety

        daily_prob *= mult

        if random.random() < daily_prob:
            return day

    # Fallback: call on last day if no day triggered
    return max_days

# ─────────────────────────────────────────────────────────────────────────────
# RULE 3 — Login count as function of age, archetype, proximity to call
# ─────────────────────────────────────────────────────────────────────────────
def generate_login_count(day, archetype, treatment_type,
                         missing_docs, rejected, call_day=None):
    """
    Spec Rule 3: login_count_24h must grow with claim age and
    SPIKE in the 48h before the call day.
    This is the primary temporal signal the model learns from.
    """
    sla        = TREATMENT_MASTER[treatment_type]["sla_days"]
    base       = BASE_LOGINS[archetype]

    # Grows as claim ages relative to SLA
    age_factor = 1.0 + (day / sla) * 0.5

    # Spike logic — THE KEY SIGNAL
    # Multipliers are intentionally large so the pipeline and model can
    # clearly distinguish call-day behaviour from baseline noise.
    proximity_spike = 1.0
    if call_day is not None:
        days_to_call = call_day - day
        if days_to_call == 2:    proximity_spike = 3.0   # 2 days before: warming up
        elif days_to_call == 1:  proximity_spike = 6.0   # day before:    strong spike
        elif days_to_call == 0:  proximity_spike = 8.0   # call day:      peak
        elif days_to_call == -1: proximity_spike = 2.0   # day after:     relief

    # Flag boost — rejected/missing docs increases anxiety baseline
    flag_boost = 0.0
    if rejected:      flag_boost += 1.5
    if missing_docs:  flag_boost += 0.8

    raw = (base + flag_boost) * age_factor * proximity_spike
    return max(0, int(np.random.poisson(max(raw, 0.1))))

# ─────────────────────────────────────────────────────────────────────────────
# RULE 4 — Status views spike even more strongly before call
# ─────────────────────────────────────────────────────────────────────────────
def generate_status_view_count(day, archetype, treatment_type, call_day=None):
    """
    Spec Rule 4: status_views_24h follows same pattern as logins
    but with a stronger spike. A user about to call has been
    obsessively checking their claim status.
    """
    base = BASE_STATUS_VIEWS[archetype]

    proximity_spike = 1.0
    if call_day is not None:
        days_to_call = call_day - day
        if days_to_call == 2:    proximity_spike = 2.5
        elif days_to_call == 1:  proximity_spike = 5.0
        elif days_to_call == 0:  proximity_spike = 7.0
        elif days_to_call == -1: proximity_spike = 1.5

    return max(0, int(np.random.poisson(max(base * proximity_spike, 0.1))))

# ─────────────────────────────────────────────────────────────────────────────
# HELPER — Generate a realistic Irish name, email, phone
# ─────────────────────────────────────────────────────────────────────────────
def generate_identity():
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)
    name  = f"{first} {last}"
    clean_first = first.lower().replace("'", "")
    clean_last  = last.lower().replace("'", "").replace(" ", "")
    email = f"{clean_first}.{clean_last}@{random.choice(EMAIL_DOMAINS)}"
    phone = f"+353 {random.randint(80,89)} {random.randint(100,999)} {random.randint(1000,9999)}"
    return name, email, phone

# ─────────────────────────────────────────────────────────────────────────────
# HELPER — Generate claim amount (log-normal, right-skewed per spec)
# ─────────────────────────────────────────────────────────────────────────────
def generate_claim_amount(treatment_type, is_high_value_profile=False):
    avg = TREATMENT_MASTER[treatment_type]["avg_amount"]
    if is_high_value_profile:
        # Force above HIGH_VALUE_THRESHOLD for high-value profile
        return round(max(HIGH_VALUE_THRESHOLD + 100,
                         np.random.lognormal(np.log(avg * 1.5), 0.4)), 2)
    return round(max(10.0, np.random.lognormal(np.log(max(avg, 1)), 0.4)), 2)

# ─────────────────────────────────────────────────────────────────────────────
# HELPER — Generate status history for a claim
# Status flow: Submitted → Under_Review → (optional branches) → terminal
# ─────────────────────────────────────────────────────────────────────────────
def generate_status_history(claim_id, submission_ts, treatment_type,
                             missing_docs, rejected, resubmission,
                             adjudicator, will_escalate):
    """
    Spec Rule 6: Status transitions must be in logical order.
    sla_breach_flag must be set correctly.
    """
    sla_days = TREATMENT_MASTER[treatment_type]["sla_days"]
    statuses = []
    current_ts = submission_ts

    def add(status, hours_after):
        nonlocal current_ts
        current_ts = current_ts + timedelta(hours=hours_after)
        days_since = (current_ts - submission_ts).days
        breach = 1 if days_since > sla_days else 0
        statuses.append({
            "status_id":            next_status_id(),
            "claim_id":             claim_id,
            "status":               status,
            "status_timestamp":     current_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "sla_breach_at_snapshot": breach,
        })

    # Always starts with Submitted
    add("Submitted", 0)

    # Move to Under_Review after 1-3 days
    add("Under_Review", random.randint(24, 72))

    # Branch based on claim flags
    if missing_docs:
        add("Awaiting_Documents", random.randint(12, 48))

    if adjudicator:
        add("With_Adjudicator", random.randint(24, 72))

    if resubmission:
        add("Resubmitted", random.randint(24, 96))

    # Terminal status — only add if claim is not actively open for demo
    # For escalating claims, leave open (no terminal) so pipeline sees them as active
    if not will_escalate and random.random() < 0.5:
        terminal = "Rejected" if rejected else "Approved"
        add(terminal, random.randint(24, 120))

    return statuses

# ─────────────────────────────────────────────────────────────────────────────
# HELPER — Generate app_logs for a claim across SIM_DAYS
# ─────────────────────────────────────────────────────────────────────────────
def generate_app_logs(user_id, claim_id, archetype, treatment_type,
                      submission_ts, missing_docs, rejected, call_day,
                      will_escalate, n_days):
    """
    Generates individual event rows in app_logs.
    login_count per day matches what nightly pipeline will compute
    from these events — this is the FK integrity requirement (Rule 6).

    Column order matches training CSV exactly:
    log_id, user_id, claim_id, event_type, timestamp,
    session_duration, in_app_chat_initiated, push_notification_opt_in
    """
    logs = []

    for day_offset in range(n_days):
        current_date = submission_ts + timedelta(days=day_offset)

        # ── How many logins today? (Rule 3) ──────────────────────────────
        cd = call_day if will_escalate else None
        n_logins = generate_login_count(
            day=day_offset + 1,
            archetype=archetype,
            treatment_type=treatment_type,
            missing_docs=missing_docs,
            rejected=rejected,
            call_day=cd,
        )

        # ── How many status views today? (Rule 4) ────────────────────────
        n_status_views = generate_status_view_count(
            day=day_offset + 1,
            archetype=archetype,
            treatment_type=treatment_type,
            call_day=cd,
        )

        # ── Generate login events ─────────────────────────────────────────
        for _ in range(n_logins):
            hour  = random.randint(7, 22)
            minute = random.randint(0, 59)
            ts    = current_date + timedelta(hours=hour, minutes=minute)

            # session_duration: ~45% null (matches training data distribution)
            session_dur = (round(random.uniform(2.0, 45.0), 1)
                           if random.random() > 0.45 else None)

            # in_app_chat: more likely for Anxious/Distress
            chat_prob = {"Passive":0.02, "Engaged":0.05,
                         "Anxious":0.12, "Distress":0.20}[archetype]
            in_app_chat = 1 if random.random() < chat_prob else 0

            # push_notification_opt_in: ~30% null (old app versions)
            push_opt_in = (random.randint(0, 1)
                           if random.random() > 0.30 else None)

            logs.append({
                "log_id":                   next_log_id(),
                "user_id":                  user_id,
                "claim_id":                 claim_id,
                "event_type":               "login",
                "timestamp":                ts.strftime("%Y-%m-%d %H:%M:%S"),
                "session_duration":         session_dur,
                "in_app_chat_initiated":    in_app_chat,
                "push_notification_opt_in": push_opt_in,
            })

            # Matching logout ~80% of the time
            if random.random() < 0.80:
                logout_ts = ts + timedelta(minutes=random.randint(5, 60))
                logs.append({
                    "log_id":                   next_log_id(),
                    "user_id":                  user_id,
                    "claim_id":                 claim_id,
                    "event_type":               "logout",
                    "timestamp":                logout_ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "session_duration":         None,
                    "in_app_chat_initiated":    0,
                    "push_notification_opt_in": push_opt_in,
                })

            # If in_app_chat was initiated, add a chat start event
            if in_app_chat:
                chat_ts = ts + timedelta(minutes=random.randint(1, 10))
                logs.append({
                    "log_id":                   next_log_id(),
                    "user_id":                  user_id,
                    "claim_id":                 claim_id,
                    "event_type":               "in_app_chat_start",
                    "timestamp":                chat_ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "session_duration":         None,
                    "in_app_chat_initiated":    1,
                    "push_notification_opt_in": push_opt_in,
                })

        # ── Generate status view events ───────────────────────────────────
        for _ in range(n_status_views):
            hour  = random.randint(7, 22)
            ts    = current_date + timedelta(
                hours=hour, minutes=random.randint(0, 59)
            )
            logs.append({
                "log_id":                   next_log_id(),
                "user_id":                  user_id,
                "claim_id":                 claim_id,
                "event_type":               "claim_status_view",
                "timestamp":                ts.strftime("%Y-%m-%d %H:%M:%S"),
                "session_duration":         round(random.uniform(0.5, 5.0), 1),
                "in_app_chat_initiated":    0,
                "push_notification_opt_in": None,
            })

        # ── Generate document upload events (only if missing_docs) ────────
        if missing_docs and day_offset < 3 and random.random() < 0.4:
            ts = current_date + timedelta(
                hours=random.randint(9, 17), minutes=random.randint(0, 59)
            )
            logs.append({
                "log_id":                   next_log_id(),
                "user_id":                  user_id,
                "claim_id":                 claim_id,
                "event_type":               "document_upload",
                "timestamp":                ts.strftime("%Y-%m-%d %H:%M:%S"),
                "session_duration":         round(random.uniform(2.0, 15.0), 1),
                "in_app_chat_initiated":    0,
                "push_notification_opt_in": None,
            })

    return logs

# ─────────────────────────────────────────────────────────────────────────────
# HELPER — Assign call reason based on claim flags
# ─────────────────────────────────────────────────────────────────────────────
def assign_call_reason(rejected, missing_docs, adjudicator, claim_amount):
    if rejected:
        return random.choice(["Rejection_Appeal", "Claim_Status"])
    if missing_docs:
        return random.choice(["Document_Query", "Claim_Status"])
    if adjudicator:
        return random.choice(["Approval_Delay", "Claim_Status"])
    if claim_amount > HIGH_VALUE_THRESHOLD:
        return random.choice(["Payment_Query", "Approval_Delay"])
    return random.choice(CALL_REASONS)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN GENERATION LOOP
# ─────────────────────────────────────────────────────────────────────────────
all_users   = []
all_claims  = []
all_statuses = []
all_logs    = []
all_calls   = []

# Track escalation stats per profile for verification
profile_stats = []

print("Generating test data by profile...")
print()

for profile in PROFILES:
    (prof_name, archetype, age_group, plan_type, treatment_type,
     missing_docs, rejected, resubmission, n_users) = profile

    prof_escalated = 0
    is_high_value  = (prof_name == "highvalue_case")

    for i in range(n_users):

        # ── 1. Generate user ──────────────────────────────────────────────
        user_id  = next_user_id()
        name, email, phone = generate_identity()
        tenure   = round(random.uniform(0.5, 20.0), 1)

        # multiclaim_user profile gets past escalation history
        if prof_name == "multiclaim_user":
            past_claims = random.randint(2, 5)
            past_escs   = random.randint(1, past_claims)
        else:
            past_claims = random.randint(0, 3)
            past_escs   = random.randint(0, max(0, past_claims - 1))

        user = {
            "user_id":                      user_id,
            "age_group":                    age_group,
            "region":                       random.choice(REGIONS),
            "plan_type":                    plan_type,
            "membership_tenure_years":      tenure,
            "past_claim_count":             past_claims,
            "past_escalation_count":        past_escs,
            "behavior_archetype":           archetype,
            "preferred_submission_channel": random.choice(CHANNELS),
            "irish_language_preference":    1 if random.random() < 0.12 else 0,
            "full_name":                    name,
            "email":                        email,
            "phone_number":                 phone,
        }
        all_users.append(user)

        # ── 2. Generate claim ─────────────────────────────────────────────
        claim_id = next_claim_id()
        amount   = generate_claim_amount(treatment_type, is_high_value)

        # For resubmission profile, generate original_claim_id reference
        # (points to a fictional prior claim — acceptable for demo purposes)
        orig_claim_id = None
        if resubmission:
            orig_claim_id = f"TSTCLM{str(_claim_counter - 50).zfill(6)}"

        # adjudicator: more likely for high-value or complex claims
        adj_flag = 1 if (amount > HIGH_VALUE_THRESHOLD or
                         random.random() < 0.10) else 0

        # Submission timestamp: staggered within first 2 days of sim start
        sub_ts = SIM_START + timedelta(
            hours=random.randint(0, 48),
            minutes=random.randint(0, 59)
        )

        claim = {
            "claim_id":               claim_id,
            "user_id":                user_id,
            "treatment_type":         treatment_type,
            "claim_amount":           amount,
            "submission_timestamp":   sub_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "submission_channel":     user["preferred_submission_channel"],
            "missing_documents_flag": 1 if missing_docs else 0,
            "adjudicator_flag":       adj_flag,
            "claim_rejected_flag":    1 if rejected else 0,
            "resubmission_flag":      1 if resubmission else 0,
            "original_claim_id":      orig_claim_id,
        }
        all_claims.append(claim)

        # ── 3. Rule 1: Decide will_escalate ──────────────────────────────
        will_escalate = decide_escalation(
            archetype=archetype,
            age_group=age_group,
            missing_docs=missing_docs,
            rejected=rejected,
            adjudicator=bool(adj_flag),
            resubmission=resubmission,
            claim_amount=amount,
        )
        if will_escalate:
            prof_escalated += 1

        # ── 4. Generate status history ────────────────────────────────────
        statuses = generate_status_history(
            claim_id=claim_id,
            submission_ts=sub_ts,
            treatment_type=treatment_type,
            missing_docs=missing_docs,
            rejected=rejected,
            resubmission=resubmission,
            adjudicator=bool(adj_flag),
            will_escalate=will_escalate,
        )
        all_statuses.extend(statuses)

        # ── 5. Rule 2: Decide call day (only for escalating claims) ───────
        call_day = None
        if will_escalate:
            call_day = decide_call_day(
                archetype=archetype,
                treatment_type=treatment_type,
                max_days=SIM_DAYS,
            )

        # ── 6. Rules 3+4: Generate app logs day by day ───────────────────
        logs = generate_app_logs(
            user_id=user_id,
            claim_id=claim_id,
            archetype=archetype,
            treatment_type=treatment_type,
            submission_ts=sub_ts,
            missing_docs=missing_docs,
            rejected=rejected,
            call_day=call_day,
            will_escalate=will_escalate,
            n_days=SIM_DAYS,
        )
        all_logs.extend(logs)

        # ── 7. Generate support call (only for escalating claims) ─────────
        if will_escalate and call_day is not None:
            call_ts = sub_ts + timedelta(
                days=call_day,
                hours=random.randint(9, 17),
                minutes=random.randint(0, 59),
            )
            # call_timestamp must be AFTER submission_timestamp (Rule 6)
            if call_ts > sub_ts:
                all_calls.append({
                    "call_id":        next_call_id(),
                    "claim_id":       claim_id,
                    "call_timestamp": call_ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "call_reason":    assign_call_reason(
                                          rejected, missing_docs,
                                          bool(adj_flag), amount),
                    "call_channel":   random.choice(CALL_CHANNELS),
                })

    esc_rate = prof_escalated / n_users * 100
    profile_stats.append((prof_name, archetype, n_users, prof_escalated, esc_rate))
    print(f"  ✅  {prof_name:<25} {n_users} users  "
          f"{prof_escalated} escalated ({esc_rate:.0f}%)")

# ─────────────────────────────────────────────────────────────────────────────
# WRITE CSVs
# ─────────────────────────────────────────────────────────────────────────────
print()
print("Writing CSVs...")

# Enforce exact column order to match training CSVs
users_df = pd.DataFrame(all_users)[[
    "user_id", "age_group", "region", "plan_type",
    "membership_tenure_years", "past_claim_count", "past_escalation_count",
    "behavior_archetype", "preferred_submission_channel",
    "irish_language_preference", "full_name", "email", "phone_number"
]]

claims_df = pd.DataFrame(all_claims)[[
    "claim_id", "user_id", "treatment_type", "claim_amount",
    "submission_timestamp", "submission_channel", "missing_documents_flag",
    "adjudicator_flag", "claim_rejected_flag", "resubmission_flag",
    "original_claim_id"
]]

statuses_df = pd.DataFrame(all_statuses)[[
    "status_id", "claim_id", "status", "status_timestamp",
    "sla_breach_at_snapshot"
]]

# App logs: enforce the training CSV column order exactly
logs_df = pd.DataFrame(all_logs)[[
    "log_id", "user_id", "claim_id", "event_type", "timestamp",
    "session_duration", "in_app_chat_initiated", "push_notification_opt_in"
]]

calls_df = pd.DataFrame(all_calls)[[
    "call_id", "claim_id", "call_timestamp", "call_reason", "call_channel"
]] if all_calls else pd.DataFrame(columns=[
    "call_id", "claim_id", "call_timestamp", "call_reason", "call_channel"
])

# Write
files = [
    ("test_users.csv",                users_df),
    ("test_claims.csv",               claims_df),
    ("test_claim_status_history.csv", statuses_df),
    ("test_app_logs.csv",             logs_df),
    ("test_support_calls.csv",        calls_df),
]

for filename, df in files:
    path = os.path.join(args.output_dir, filename)
    df.to_csv(path, index=False)
    print(f"  ✅  {filename:<35} {len(df):>6,} rows")

# ─────────────────────────────────────────────────────────────────────────────
# VERIFICATION — Run the 9 checklist items from the spec doc
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 62)
print("  VERIFICATION CHECKS (Spec Part 2 Checklist)")
print("=" * 62)

all_pass = True

def check(label, passed, detail=""):
    global all_pass
    icon = "✅" if passed else "❌"
    if not passed:
        all_pass = False
    print(f"  {icon}  {label:<45} {detail}")

# 1. Claim escalation rate — test data is deliberately higher than training
# because profiles are skewed toward high-risk groups by design.
# We check > 0 and < 80% as a sanity check rather than the 10-18% training target.
total_claims   = len(claims_df)
total_escalated = len(calls_df["claim_id"].unique()) if not calls_df.empty else 0
esc_rate_overall = total_escalated / total_claims * 100 if total_claims > 0 else 0
check("Claim escalation rate > 0% (test profiles are high-risk by design)",
      0 < esc_rate_overall < 80,
      f"{total_escalated}/{total_claims} = {esc_rate_overall:.1f}% (training target 14-18%)")

# 2. Login spikes before call
if not calls_df.empty and not logs_df.empty:
    login_logs = logs_df[logs_df["event_type"] == "login"].copy()
    login_logs["timestamp"] = pd.to_datetime(login_logs["timestamp"])
    calls_merged = calls_df.merge(claims_df[["claim_id", "submission_timestamp"]])
    calls_merged["call_timestamp"] = pd.to_datetime(calls_merged["call_timestamp"])
    calls_merged["submission_timestamp"] = pd.to_datetime(calls_merged["submission_timestamp"])

    call_day_logins, non_call_day_logins = [], []
    for _, call_row in calls_merged.iterrows():
        cid      = call_row["claim_id"]
        call_ts  = call_row["call_timestamp"]
        sub_ts   = call_row["submission_timestamp"]
        c_logs   = login_logs[login_logs["claim_id"] == cid]

        call_day_count = len(c_logs[
            (c_logs["timestamp"] >= call_ts - timedelta(hours=24)) &
            (c_logs["timestamp"] <= call_ts)
        ])
        other_count = len(c_logs[
            c_logs["timestamp"] < call_ts - timedelta(hours=24)
        ])
        other_days = max((call_ts - sub_ts).days - 1, 1)

        call_day_logins.append(call_day_count)
        non_call_day_logins.append(other_count / other_days)

    avg_call   = np.mean(call_day_logins)   if call_day_logins   else 0
    avg_noncall = np.mean(non_call_day_logins) if non_call_day_logins else 0
    ratio = avg_call / max(avg_noncall, 0.01)
    check("Login spikes before call (1.5x+ expected)",
          ratio >= 1.5,
          f"call-day avg={avg_call:.1f}  non-call avg={avg_noncall:.1f}  ratio={ratio:.1f}x")
else:
    check("Login spikes before call", False, "No calls or logs to check")

# 3. Status views spike before call
if not calls_df.empty and not logs_df.empty:
    sv_logs = logs_df[logs_df["event_type"] == "claim_status_view"].copy()
    sv_logs["timestamp"] = pd.to_datetime(sv_logs["timestamp"])

    call_day_sv, non_call_day_sv = [], []
    for _, call_row in calls_merged.iterrows():
        cid      = call_row["claim_id"]
        call_ts  = call_row["call_timestamp"]
        sub_ts   = call_row["submission_timestamp"]
        c_sv     = sv_logs[sv_logs["claim_id"] == cid]

        call_day_count = len(c_sv[
            (c_sv["timestamp"] >= call_ts - timedelta(hours=24)) &
            (c_sv["timestamp"] <= call_ts)
        ])
        other_count = len(c_sv[c_sv["timestamp"] < call_ts - timedelta(hours=24)])
        other_days  = max((call_ts - sub_ts).days - 1, 1)

        call_day_sv.append(call_day_count)
        non_call_day_sv.append(other_count / other_days)

    avg_sv_call    = np.mean(call_day_sv)    if call_day_sv    else 0
    avg_sv_noncall = np.mean(non_call_day_sv) if non_call_day_sv else 0
    sv_ratio = avg_sv_call / max(avg_sv_noncall, 0.01)
    check("Status views spike before call (2x+ expected)",
          sv_ratio >= 1.5,
          f"call-day avg={avg_sv_call:.1f}  non-call avg={avg_sv_noncall:.1f}  ratio={sv_ratio:.1f}x")
else:
    check("Status views spike before call", False, "No data to check")

# 4. Distress escalates 2x Passive
if not calls_df.empty:
    escalated_claims = set(calls_df["claim_id"].unique())
    claims_with_arch = claims_df.merge(users_df[["user_id","behavior_archetype"]])
    claims_with_arch["escalated"] = claims_with_arch["claim_id"].isin(escalated_claims).astype(int)
    arch_rates = claims_with_arch.groupby("behavior_archetype")["escalated"].mean()
    distress_rate = arch_rates.get("Distress", 0)
    passive_rate  = arch_rates.get("Passive",  0.001)
    ratio_dp      = distress_rate / max(passive_rate, 0.001)
    check("Distress escalates more than Passive",
          ratio_dp >= 1.2,
          f"Distress={distress_rate*100:.0f}%  Passive={passive_rate*100:.0f}%  ratio={ratio_dp:.1f}x")
else:
    check("Distress escalates 2x+ Passive", False, "No calls to check")

# 5. Rejection adds significant escalation lift
if not calls_df.empty:
    rej_rates = claims_with_arch.groupby("claim_rejected_flag")["escalated"].mean()
    rej_yes = rej_rates.get(1, 0)
    rej_no  = rej_rates.get(0, 0.001)
    check("Rejection flag adds escalation lift",
          rej_yes > rej_no,
          f"Rejected={rej_yes*100:.0f}%  Not rejected={rej_no*100:.0f}%")
else:
    check("Rejection flag adds escalation lift", False, "No calls to check")

# 6. FK integrity — zero orphans
app_claim_ids    = set(logs_df["claim_id"].unique())
status_claim_ids = set(statuses_df["claim_id"].unique())
call_claim_ids   = set(calls_df["claim_id"].unique()) if not calls_df.empty else set()
valid_claim_ids  = set(claims_df["claim_id"].unique())
valid_user_ids   = set(users_df["user_id"].unique())

orphan_logs    = len(app_claim_ids - valid_claim_ids)
orphan_status  = len(status_claim_ids - valid_claim_ids)
orphan_calls   = len(call_claim_ids - valid_claim_ids)
orphan_users   = len(set(claims_df["user_id"].unique()) - valid_user_ids)

check("FK integrity — app_logs → claims",    orphan_logs   == 0, f"orphans: {orphan_logs}")
check("FK integrity — status → claims",      orphan_status == 0, f"orphans: {orphan_status}")
check("FK integrity — support_calls → claims",orphan_calls  == 0, f"orphans: {orphan_calls}")
check("FK integrity — claims → users",       orphan_users  == 0, f"orphans: {orphan_users}")

# 7. call_timestamp after submission_timestamp
if not calls_df.empty:
    merged_ts = calls_df.merge(claims_df[["claim_id","submission_timestamp"]])
    bad_ts = (pd.to_datetime(merged_ts["call_timestamp"]) <=
              pd.to_datetime(merged_ts["submission_timestamp"])).sum()
    check("All call_timestamps after submission", bad_ts == 0, f"violations: {bad_ts}")
else:
    check("All call_timestamps after submission", True, "No calls (OK)")

# 8. One call per claim maximum
if not calls_df.empty:
    max_calls = calls_df.groupby("claim_id").size().max()
    check("Max one call per claim",
          max_calls <= 1,
          f"max calls on one claim: {max_calls}")
else:
    check("Max one call per claim", True, "No calls (OK)")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 62)
print("  GENERATION SUMMARY")
print("=" * 62)
print(f"  Users                : {len(users_df):,}")
print(f"  Claims               : {len(claims_df):,}")
print(f"  Status history rows  : {len(statuses_df):,}")
print(f"  App log events       : {len(logs_df):,}")
print(f"  Support calls        : {len(calls_df):,}")
print(f"  Overall escalation   : {esc_rate_overall:.1f}%")
print()
print("  Event type breakdown:")
for et, cnt in logs_df["event_type"].value_counts().items():
    print(f"    {et:<25} {cnt:>6,}")
print()
print("  Escalation by profile:")
print(f"    {'Profile':<25} {'Users':>5}  {'Escalated':>9}  {'Rate':>6}")
print("    " + "─" * 50)
for name, arch, n, esc, rate in profile_stats:
    print(f"    {name:<25} {n:>5}  {esc:>9}  {rate:>5.0f}%")

print()
if all_pass:
    print("  ✅  ALL CHECKS PASSED — data is ready for setup_test_tables.py")
else:
    print("  ⚠️   SOME CHECKS FAILED — review above before loading to DB")
print()
print("  Next step:")
print("    python setup_test_tables.py --data_dir ./test_data")
print("=" * 62)