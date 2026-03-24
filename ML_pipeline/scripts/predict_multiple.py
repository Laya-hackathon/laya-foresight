import pandas as pd
import numpy as np
import joblib
import json
import uuid
from datetime import datetime
import shap
import psycopg2
from dotenv import load_dotenv
import os

# ==============================
# 1. LOAD ENV VARIABLES
# ==============================
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env")

# ==============================
# 2. CONNECT TO DATABASE
# ==============================
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

print("Connected to database")

# ==============================
# 3. LOAD MODEL + FEATURES
# ==============================
model = joblib.load(r"D:\NCI and visa\Academics\semester 2\laya\code\model & setting\xgb_v1.pkl")

with open(r"D:\NCI and visa\Academics\semester 2\laya\code\model & setting\feature_columns (1).json") as f:
    feature_columns = json.load(f)

print("Model loaded")

# ==============================
# 4. PREPROCESS DATA
# ==============================
from data_preprocessing_embedding import preprocess_and_encode

input_path = r"D:\NCI and visa\Academics\semester 2\laya\Complete repo\laya-foresight\ML_pipeline\test_data\test_feature_snapshots.csv"
output_path = r"D:\NCI and visa\Academics\semester 2\laya\Complete repo\laya-foresight\ML_pipeline\test_data\test_data_processsed\encoded_test_users_data.csv"

preprocess_and_encode(input_path=input_path, output_path=output_path)

test_users_df = pd.read_csv(output_path)

# ==============================
# 5. VALIDATE REQUIRED COLUMNS
# ==============================
required_cols = ["snapshot_id", "claim_id", "user_id"]

for col in required_cols:
    if col not in test_users_df.columns:
        raise ValueError(f"❌ Missing column: {col}")

# ==============================
# 6. PREDICTIONS
# ==============================
new_data = test_users_df[feature_columns]

predictions = model.predict(new_data)
probabilities = model.predict_proba(new_data)[:, 1]

print("Predictions done")

# ==============================
# 7. SHAP VALUES
# ==============================
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(new_data)

print("SHAP computed")

# ==============================
# DELETE OLD DATA
# ==============================
cursor.execute("TRUNCATE TABLE model_predictions;")
conn.commit()

print("🧹 Old predictions deleted (table truncated)")

# ==============================
# 8. INSERT QUERY
# ==============================
insert_query = """
INSERT INTO model_predictions (
    snapshot_id, claim_id, user_id,
    predicted_at, escalation_score, risk_level,
    model_version, top_feature_1, top_feature_2, top_feature_3
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

# ==============================
# 9. LOOP + INSERT
# ==============================
batch_size = 500

for start in range(0, len(new_data), batch_size):
    batch_values = []

    for i in range(start, min(start + batch_size, len(new_data))):
        shap_row = shap_values[i]

        top_indices = np.argsort(np.abs(shap_row))[-3:][::-1]
        top_features = [feature_columns[idx] for idx in top_indices]

        row = (
            int(test_users_df["snapshot_id"].iloc[i]),
            str(test_users_df["claim_id"].iloc[i]),
            str(test_users_df["user_id"].iloc[i]),
            datetime.utcnow(),
            float(probabilities[i]),
            "high" if predictions[i] == 1 else "low",
            "xgb_v1",
            str(top_features[0]),
            str(top_features[1]),
            str(top_features[2])
        )

        batch_values.append(row)

    try:
        cursor.executemany(insert_query, batch_values)
        conn.commit()
        print(f"Inserted batch {start} to {start + len(batch_values)}")
    except Exception as e:
        conn.rollback()
        print(f"Failed to insert batch {start} to {start + len(batch_values)}")
        print("DB Exception:", type(e).__name__, e)
        raise

# ==============================
# 10. CLEANUP
# ==============================
cursor.close()
conn.close()

print("All predictions stored successfully!")