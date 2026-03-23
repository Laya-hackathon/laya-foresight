"""
Laya Healthcare — Patch User Contacts
Adds realistic fake Irish names, emails and phone numbers
to the existing 2,000 users in the database.

Safe to run — only touches full_name, email, phone_number columns.
Everything else in the database is completely untouched.

Run from inside the database/ folder:
    python patch_user_contacts.py
"""

import os
import random
import pandas as pd
from sqlalchemy import create_engine, text

# ── Load .env ─────────────────────────────────────────────────────────────────
def load_env():
    with open("../.env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

load_env()
engine = create_engine(os.environ["DATABASE_URL"], echo=False)

print("=" * 55)
print("  LAYA — PATCH USER CONTACTS")
print("=" * 55)

# ── Realistic Irish name pools ────────────────────────────────────────────────
IRISH_FIRST_NAMES = [
    # Male
    "Liam", "Conor", "Seán", "Patrick", "Ciarán", "Eoin", "Darragh",
    "Oisín", "Fionn", "Cormac", "Declan", "Brendan", "Ronan", "Cathal",
    "Niall", "Tadhg", "Fergus", "Killian", "Ruairí", "Cian",
    "James", "Michael", "David", "John", "Kevin", "Brian", "Mark",
    "Shane", "Aidan", "Donal",
    # Female
    "Aoife", "Niamh", "Saoirse", "Ciara", "Sinéad", "Caoimhe", "Aisling",
    "Meadhbh", "Róisín", "Orla", "Fionnuala", "Clodagh", "Siobhán",
    "Mairéad", "Éabha", "Sorcha", "Grainne", "Deirdre", "Nuala", "Brigid",
    "Emma", "Sarah", "Rachel", "Claire", "Laura", "Katie", "Michelle",
    "Amy", "Jennifer", "Karen",
]

IRISH_LAST_NAMES = [
    "Murphy", "Kelly", "O'Brien", "Walsh", "Smith", "O'Connor", "McCarthy",
    "O'Sullivan", "Byrne", "Ryan", "O'Neill", "O'Reilly", "Doyle", "Burke",
    "Fitzgerald", "Lynch", "Gallagher", "Murray", "Quinn", "Moore",
    "McLoughlin", "O'Callaghan", "Kennedy", "Dunne", "Brennan", "Collins",
    "Connell", "Clarke", "Johnston", "Hughes", "Farrell", "Whelan",
    "Nolan", "Doherty", "Sheridan", "Moran", "Foley", "Sweeney",
    "Martin", "Cullen", "Boyle", "Healy", "Sheehan", "Barry", "Donnelly",
    "Flanagan", "Mullen", "Kavanagh", "Power", "Ward",
]

EMAIL_DOMAINS = [
    "gmail.com", "hotmail.com", "yahoo.com", "outlook.com",
    "icloud.com", "eircom.net", "live.ie", "gmail.ie"
]

# ── Generate realistic Irish mobile numbers ───────────────────────────────────
def irish_phone():
    """
    Irish mobile numbers:
    - Start with 083, 085, 086, 087, 089
    - Followed by 7 digits
    """
    prefix = random.choice(["083", "085", "086", "087", "089"])
    number = "".join([str(random.randint(0, 9)) for _ in range(7)])
    return f"+353 {prefix[1:]} {number[:3]} {number[3:]}"

# ── Generate unique email ─────────────────────────────────────────────────────
def make_email(first, last, used_emails):
    """Create a unique email address from name."""
    first_clean = first.lower().replace("é","e").replace("á","a")\
                              .replace("í","i").replace("ó","o")\
                              .replace("ú","u").replace("'","")
    last_clean  = last.lower().replace("é","e").replace("á","a")\
                              .replace("í","i").replace("ó","o")\
                              .replace("ú","u").replace("'","")

    domain = random.choice(EMAIL_DOMAINS)

    # Try different formats until unique
    formats = [
        f"{first_clean}.{last_clean}@{domain}",
        f"{first_clean}{last_clean}@{domain}",
        f"{first_clean[0]}{last_clean}@{domain}",
        f"{first_clean}.{last_clean}{random.randint(1,99)}@{domain}",
        f"{first_clean}{random.randint(1,999)}@{domain}",
    ]

    for fmt in formats:
        if fmt not in used_emails:
            used_emails.add(fmt)
            return fmt

    # Fallback with random suffix
    fallback = f"{first_clean}.{last_clean}.{random.randint(100,999)}@{domain}"
    used_emails.add(fallback)
    return fallback

# ── Load existing user_ids from database ─────────────────────────────────────
print("\n  Loading users from database...")
with engine.connect() as conn:
    users_df = pd.read_sql("SELECT user_id FROM users ORDER BY user_id", conn)

print(f"  Found {len(users_df):,} users to patch")

# ── Generate contact details for each user ────────────────────────────────────
print("\n  Generating names, emails and phone numbers...")

random.seed(42)  # reproducible results
used_emails = set()
patches = []

for user_id in users_df["user_id"]:
    first = random.choice(IRISH_FIRST_NAMES)
    last  = random.choice(IRISH_LAST_NAMES)
    full_name    = f"{first} {last}"
    email        = make_email(first, last, used_emails)
    phone_number = irish_phone()

    patches.append({
        "user_id":      user_id,
        "full_name":    full_name,
        "email":        email,
        "phone_number": phone_number,
    })

print(f"  Generated {len(patches):,} contact records")

# ── Write to database ─────────────────────────────────────────────────────────
print("\n  Writing to database...")

with engine.begin() as conn:
    for patch in patches:
        conn.execute(text("""
            UPDATE users
            SET full_name    = :full_name,
                email        = :email,
                phone_number = :phone_number
            WHERE user_id = :user_id
        """), patch)

print(f"  ✅  {len(patches):,} users patched")

# ── Verify ────────────────────────────────────────────────────────────────────
print("\n  Verification...")
with engine.connect() as conn:
    # Check nulls remaining
    nulls = conn.execute(text("""
        SELECT COUNT(*) FROM users
        WHERE full_name IS NULL
           OR email IS NULL
           OR phone_number IS NULL
    """)).fetchone()[0]

    # Sample 5 users
    sample = pd.read_sql("""
        SELECT user_id, full_name, email, phone_number, age_group, plan_type
        FROM users
        ORDER BY RANDOM()
        LIMIT 5
    """, conn)

print(f"  Rows still NULL: {nulls}  {'✅ All filled' if nulls == 0 else '❌ Some still empty'}")
print(f"\n  Sample of patched users:")
print(f"  {'user_id':<10}  {'full_name':<22}  {'email':<35}  {'phone':<18}  {'age':<8}  plan")
print("  " + "-" * 105)
for _, row in sample.iterrows():
    print(f"  {row.user_id:<10}  {row.full_name:<22}  {row.email:<35}  "
          f"{row.phone_number:<18}  {row.age_group:<8}  {row.plan_type}")

# Check email uniqueness
with engine.connect() as conn:
    total     = conn.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]
    unique_em = conn.execute(text("SELECT COUNT(DISTINCT email) FROM users")).fetchone()[0]

print(f"\n  Total users:    {total:,}")
print(f"  Unique emails:  {unique_em:,}  {'✅' if unique_em == total else '⚠️  some duplicates'}")

print("\n" + "=" * 55)
print("  ✅  PATCH COMPLETE")
print("  Users table now has name, email and phone number.")
print("  All other tables and data untouched.")
print("=" * 55)