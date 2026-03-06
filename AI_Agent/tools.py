

import json
from datetime import datetime

_current_scenario = None


def set_current_scenario(scenario: dict):
    """Set the active scenario so tools return the right data."""
    global _current_scenario
    _current_scenario = scenario


def get_claim_details(claim_id: str) -> dict:
    """Retrieves full details of a claim from the database."""
    if _current_scenario and _current_scenario["claim_id"] == claim_id:
        return _current_scenario["claim_details"]
    return {"error": f"Claim {claim_id} not found"}


def get_customer_behaviour(user_id: str, claim_id: str) -> dict:
    """Retrieves real-time app activity for a user."""
    if _current_scenario and _current_scenario["user_id"] == user_id:
        return _current_scenario["customer_behaviour"]
    return {"error": f"No behaviour data for user {user_id}"}


def get_customer_history(user_id: str) -> dict:
    """Returns the customer's history with Laya."""
    if _current_scenario and _current_scenario["user_id"] == user_id:
        return _current_scenario["customer_history"]
    return {"error": f"Customer {user_id} not found"}


def alert_employee(claim_id: str, message: str, urgency: str, sla_minutes: int = None) -> dict:
    """Sends an alert to the Laya claims team on Slack."""
    return {
        "sent": True,
        "channel": "#claims-alerts",
        "urgency": urgency,
        "sla_minutes": sla_minutes or (30 if urgency == "URGENT" else 120),
        "timestamp": datetime.now().isoformat(),
        "message_preview": message[:100] + "..." if len(message) > 100 else message
    }


def send_email(user_id: str, subject: str, body_html: str) -> dict:
    """Sends an email to the customer."""
    name = "Customer"
    email = "customer@email.com"
    if _current_scenario and _current_scenario["user_id"] == user_id:
        name = _current_scenario["customer_history"]["name"]
        email = _current_scenario["customer_history"]["email"]
    return {
        "sent": True,
        "recipient": email,
        "recipient_name": name,
        "subject": subject,
        "timestamp": datetime.now().isoformat()
    }


def send_in_app_notification(user_id: str, title: str, body: str, deep_link: str = None) -> dict:
    """Sends a push notification to the customer's phone."""
    name = "Customer"
    if _current_scenario and _current_scenario["user_id"] == user_id:
        name = _current_scenario["customer_history"]["name"]
    return {
        "sent": True,
        "recipient": name,
        "title": title,
        "deep_link": deep_link or "laya://claims",
        "timestamp": datetime.now().isoformat()
    }


def schedule_callback(user_id: str, claim_id: str, priority: str = "NORMAL", notes: str = "") -> dict:
    """Schedules a proactive outbound call from a Laya agent."""
    return {
        "scheduled": True,
        "callback_id": f"CB-{datetime.now().strftime('%Y%m%d%H%M')}",
        "priority": priority,
        "scheduled_for": "Next available slot (within 2 hours)" if priority == "HIGH" else "Next available slot (within 24 hours)",
        "assigned_to": "Claims Team Lead — Aoife Brennan" if priority == "HIGH" else "Available Claims Agent",
        "timestamp": datetime.now().isoformat()
    }


def log_intervention(claim_id: str, actions_taken: list, reasoning: str) -> dict:
    """Records all actions taken and reasoning."""
    return {
        "logged": True,
        "intervention_id": f"INT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "claim_id": claim_id,
        "actions_count": len(actions_taken),
        "timestamp": datetime.now().isoformat()
    }
