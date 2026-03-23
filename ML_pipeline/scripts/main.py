import pandas as pd
import joblib
import json

from utils import model_predict, send_to_agent

# Load model
model = joblib.load(r"D:\NCI and visa\Academics\semester 2\laya\code\model & setting\xgb_v1.pkl")

# Load feature columns
with open(r"D:\NCI and visa\Academics\semester 2\laya\code\model & setting\feature_columns (1).json") as f:
    feature_columns = json.load(f)

print("Model and feature columns loaded successfully.")

# Load test data
test_users_df = pd.read_csv(r"D:\NCI and visa\Academics\semester 2\laya\code\data\test_users_data.csv")
print("Test users data loaded successfully.")

# Ensure correct feature order
new_data = test_users_df[feature_columns]

# Take ONE input
input_df = new_data.iloc[[0]]

print(input_df)

# Predict
prediction, probability = model_predict(input_df, model)

# Send result
send_to_agent(prediction, probability, test_users_df["member_id"].iloc[0])