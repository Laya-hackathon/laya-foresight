# Laya Healthcare — Data Engineering World

This repository is **World 1 — Data Engineering** of the Laya Healthcare
Claim Escalation Risk Model project.

## What this world does
- Generates synthetic training data for the ML model
- Validates data quality and integrity
- Loads all data into the shared Supabase PostgreSQL database
- Runs the nightly pipeline that converts live events into feature snapshots

## Folder Structure

| Folder | What lives here |
|---|---|
| `data/` | All CSV files — raw and processed |
| `generation/` | Synthetic data generation scripts |
| `validation/` | Data validation notebook |
| `database/` | Database setup and connection scripts |
| `pipeline/` | Nightly snapshot job for live data |
| `docs/` | PDF guides and documentation |

## How to set up

**1. Install dependencies**
```bash
pip install pandas sqlalchemy psycopg2-binary numpy
```

**2. Create your `.env` file** in the root folder:
```
DATABASE_URL=postgresql://your-connection-string-here
```

**3. Generate the synthetic data**
```bash
python generation/generate_v3.py
```

**4. Set up the database** (run once)
```bash
python database/setup_database.py
```

## Database Views — what each colleague uses

| Colleague | View / Table | Purpose |
|---|---|---|
| EDA | `v_claim_full` | Every claim joined with user demographics |
| Model Training | `v_train` | Jun–Sep snapshots for training |
| Model Training | `v_test` | Oct–Nov snapshots for testing |
| Website | `claims`, `users`, `app_logs` | Live user and claim data |
| Agentic AI | `v_high_risk_open` | High risk claims to action |

## How to connect to the database
```python
import os
import pandas as pd
from sqlalchemy import create_engine

with open(".env") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ[k] = v

engine = create_engine(os.environ["DATABASE_URL"])

# Example
df = pd.read_sql("SELECT * FROM v_claim_full", engine)
```

## Team

| Role | World | Responsibility |
|---|---|---|
| Data Engineering | World 1 (this repo) | Data generation, validation, database, pipeline |
| EDA | World 2 | Exploratory analysis and insights |
| Model Training | World 3 | Feature engineering, training, predictions |
| Website | World 4 | Member portal, agent dashboard, live events |
| Agentic AI | World 5 | Automated interventions and chatbot |

## Important notes

- Never commit `.env` to GitHub — it contains database credentials
- CSV files are not committed — run `generate_v3.py` to recreate them
- The `pipeline/` folder contains the nightly job for live data processing
- `model_predictions`, `agent_interactions`, `intervention_outcomes` tables
  start empty and fill up as the live system runs