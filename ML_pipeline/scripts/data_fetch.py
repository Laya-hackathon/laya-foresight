import os
import sys
import pandas as pd
from sqlalchemy import create_engine
import logging


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




with engine.connect() as conn:
    print("Connected!")

# Example
try:
    df = pd.read_sql("SELECT * FROM test_feature_snapshots", engine)
    print(df.head())  # Display the first few rows of the DataFrame
    print("Data fetched from database successfully.")
except Exception as e:
    print(f"Failed to connect to database: {e}")
    print("Loading data from local CSV file instead.")

print("Data loaded from CSV.")
df.to_csv(os.path.join(os.path.dirname(__file__), '..', 'test_data', 'test_feature_snapshots.csv'), index=False)