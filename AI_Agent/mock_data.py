

SCENARIOS = {
    "scenario_1": {
        "id": "scenario_1",
        "name": "High-Value Surgical Claim — Missing Documents",
        "description": "€8,200 surgical claim, missing specialist referral, customer obsessively checking app",
        "risk_band": "HIGH",
        "risk_score": 0.92,
        "claim_id": "CLM-2026-08421",
        "user_id": "USR-4491",
        "claim_details": {
            "claim_id": "CLM-2026-08421",
            "claim_type": "Surgical",
            "category": "Orthopaedic Surgery",
            "amount_eur": 8200.00,
            "status": "Under Review — Documents Pending",
            "submission_date": "2026-02-12",
            "days_since_submission": 14,
            "missing_docs": ["Specialist referral letter from Dr. Aisling Murphy"],
            "estimated_completion_date": "2026-03-05",
            "hospital": "Blackrock Clinic, Dublin",
            "procedure": "Arthroscopic knee reconstruction"
        },
        "customer_behaviour": {
            "user_id": "USR-4491",
            "claim_id": "CLM-2026-08421",
            "checks_1h": 3,
            "checks_6h": 7,
            "checks_24h": 12,
            "is_accelerating": True,
            "mins_since_last_open": 8,
            "currently_in_app": True,
            "pages_viewed": ["claim_status", "document_upload", "faq_processing_times", "contact_us"],
            "last_document_upload_attempt": "2026-02-25T14:22:00Z"
        },
        "customer_history": {
            "user_id": "USR-4491",
            "name": "Sarah O'Brien",
            "email": "sarah.obrien@email.ie",
            "tenure_years": 6,
            "total_past_claims": 4,
            "past_escalations": 0,
            "last_call_date": None,
            "customer_segment": "Premium",
            "plan": "Laya Exceed",
            "has_dependents": True
        }
    },

    "scenario_2": {
        "id": "scenario_2",
        "name": "Routine Dental — Low Risk, No Action Needed",
        "description": "€340 dental claim, standard processing, customer checked once — likely no intervention needed",
        "risk_band": "LOW",
        "risk_score": 0.18,
        "claim_id": "CLM-2026-09102",
        "user_id": "USR-7723",
        "claim_details": {
            "claim_id": "CLM-2026-09102",
            "claim_type": "Dental",
            "category": "Routine Dental",
            "amount_eur": 340.00,
            "status": "Processing",
            "submission_date": "2026-02-24",
            "days_since_submission": 2,
            "missing_docs": [],
            "estimated_completion_date": "2026-03-03",
            "hospital": None,
            "procedure": "Root canal treatment"
        },
        "customer_behaviour": {
            "user_id": "USR-7723",
            "claim_id": "CLM-2026-09102",
            "checks_1h": 0,
            "checks_6h": 0,
            "checks_24h": 1,
            "is_accelerating": False,
            "mins_since_last_open": 480,
            "currently_in_app": False,
            "pages_viewed": ["claim_status"],
            "last_document_upload_attempt": None
        },
        "customer_history": {
            "user_id": "USR-7723",
            "name": "Conor Fitzpatrick",
            "email": "conor.fitz@gmail.com",
            "tenure_years": 2,
            "total_past_claims": 1,
            "past_escalations": 0,
            "last_call_date": None,
            "customer_segment": "Standard",
            "plan": "Laya Connect",
            "has_dependents": False
        }
    },

    "scenario_3": {
        "id": "scenario_3",
        "name": "Maternity Claim — Processing Delay, Anxious Customer",
        "description": "€4,500 maternity claim, delayed 18 days, first-time mother anxious about coverage",
        "risk_band": "HIGH",
        "risk_score": 0.84,
        "claim_id": "CLM-2026-07833",
        "user_id": "USR-3312",
        "claim_details": {
            "claim_id": "CLM-2026-07833",
            "claim_type": "Maternity",
            "category": "Maternity & Newborn Care",
            "amount_eur": 4500.00,
            "status": "Processing — Delayed",
            "submission_date": "2026-02-08",
            "days_since_submission": 18,
            "missing_docs": [],
            "estimated_completion_date": "Overdue — originally 2026-02-22",
            "hospital": "National Maternity Hospital, Holles Street",
            "procedure": "Caesarean section delivery + 3-night stay"
        },
        "customer_behaviour": {
            "user_id": "USR-3312",
            "claim_id": "CLM-2026-07833",
            "checks_1h": 2,
            "checks_6h": 5,
            "checks_24h": 9,
            "is_accelerating": True,
            "mins_since_last_open": 22,
            "currently_in_app": True,
            "pages_viewed": ["claim_status", "claim_status", "maternity_benefits", "contact_us", "complaints"],
            "last_document_upload_attempt": None
        },
        "customer_history": {
            "user_id": "USR-3312",
            "name": "Emma Gallagher",
            "email": "emma.gallagher@outlook.com",
            "tenure_years": 3,
            "total_past_claims": 0,
            "past_escalations": 0,
            "last_call_date": None,
            "customer_segment": "Standard",
            "plan": "Laya Extend",
            "has_dependents": True
        }
    },

    "scenario_4": {
        "id": "scenario_4",
        "name": "Mental Health Claim — Sensitive Category",
        "description": "€2,800 mental health claim, customer hasn't opened app in 2 days, sensitive handling needed",
        "risk_band": "MEDIUM",
        "risk_score": 0.61,
        "claim_id": "CLM-2026-08190",
        "user_id": "USR-5508",
        "claim_details": {
            "claim_id": "CLM-2026-08190",
            "claim_type": "Mental Health",
            "category": "Psychiatric & Psychological Services",
            "amount_eur": 2800.00,
            "status": "Under Review",
            "submission_date": "2026-02-16",
            "days_since_submission": 10,
            "missing_docs": [],
            "estimated_completion_date": "2026-03-01",
            "hospital": None,
            "procedure": "10-session outpatient CBT programme"
        },
        "customer_behaviour": {
            "user_id": "USR-5508",
            "claim_id": "CLM-2026-08190",
            "checks_1h": 0,
            "checks_6h": 0,
            "checks_24h": 0,
            "is_accelerating": False,
            "mins_since_last_open": 2880,
            "currently_in_app": False,
            "pages_viewed": ["claim_status"],
            "last_document_upload_attempt": None
        },
        "customer_history": {
            "user_id": "USR-5508",
            "name": "David Keane",
            "email": "d.keane@protonmail.com",
            "tenure_years": 8,
            "total_past_claims": 6,
            "past_escalations": 1,
            "last_call_date": "2025-11-14",
            "customer_segment": "Premium",
            "plan": "Laya Exceed",
            "has_dependents": False
        }
    },

    "scenario_5": {
        "id": "scenario_5",
        "name": "High-Value Duplicate Submission — Potential Fraud",
        "description": "€12,000 claim with duplicate submissions detected, urgent internal review needed",
        "risk_band": "CRITICAL",
        "risk_score": 0.97,
        "claim_id": "CLM-2026-09455",
        "user_id": "USR-8891",
        "claim_details": {
            "claim_id": "CLM-2026-09455",
            "claim_type": "Surgical",
            "category": "Cardiac Surgery",
            "amount_eur": 12000.00,
            "status": "Flagged — Duplicate Detected",
            "submission_date": "2026-02-20",
            "days_since_submission": 6,
            "missing_docs": ["Consultant discharge summary"],
            "estimated_completion_date": "Suspended pending review",
            "hospital": "Mater Private Hospital, Dublin",
            "procedure": "Cardiac catheterisation + stent placement",
            "flags": ["Duplicate claim CLM-2026-09201 submitted 2026-02-15 for same procedure", "Amount discrepancy: first submission was €9,800"]
        },
        "customer_behaviour": {
            "user_id": "USR-8891",
            "claim_id": "CLM-2026-09455",
            "checks_1h": 0,
            "checks_6h": 1,
            "checks_24h": 2,
            "is_accelerating": False,
            "mins_since_last_open": 120,
            "currently_in_app": False,
            "pages_viewed": ["claim_status", "claim_history"],
            "last_document_upload_attempt": "2026-02-21T09:15:00Z"
        },
        "customer_history": {
            "user_id": "USR-8891",
            "name": "Patrick Nolan",
            "email": "p.nolan@email.ie",
            "tenure_years": 1,
            "total_past_claims": 3,
            "past_escalations": 2,
            "last_call_date": "2026-01-28",
            "customer_segment": "Watch List",
            "plan": "Laya Aspire",
            "has_dependents": True
        }
    }
}


def get_scenario(scenario_id: str) -> dict:
    return SCENARIOS.get(scenario_id)


def get_all_scenarios() -> list:
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "description": s["description"],
            "risk_band": s["risk_band"],
            "risk_score": s["risk_score"],
            "claim_id": s["claim_id"],
            "user_id": s["user_id"],
            "amount_eur": s["claim_details"]["amount_eur"],
            "claim_type": s["claim_details"]["claim_type"],
            "customer_name": s["customer_history"]["name"],
        }
        for s in SCENARIOS.values()
    ]
