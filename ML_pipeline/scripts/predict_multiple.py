import pickle, pandas as pd
import joblib
import json
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score,confusion_matrix,classification_report,roc_auc_score
from sklearn.metrics import ConfusionMatrixDisplay


model = joblib.load(r"D:\NCI and visa\Academics\semester 2\laya\code\model & setting\xgb_v1.pkl")

with open(r"D:\NCI and visa\Academics\semester 2\laya\code\model & setting\feature_columns (1).json") as f:
    feature_columns = json.load(f)

print("Model and feature columns loaded successfully.")


test_users_df = pd.read_csv(r"D:\NCI and visa\Academics\semester 2\laya\code\data\test_users_data.csv")
print("Test users data loaded successfully.")
# Ensure the test data has the same feature columns as the model expects
new_data = test_users_df[feature_columns]


# Make predictions

predictions = model.predict(new_data)
probabilities = model.predict_proba(new_data)[:,1]

predictions_df = pd.DataFrame({
    "member_id": test_users_df["member_id"],
    "predicted_risk": predictions,
    "risk_probability": probabilities
})


predictions_df.to_csv("predictions.csv", index=False)

# Output predictions


for idx, member_id in enumerate(predictions_df["member_id"]):
    print(f"Member ID: {member_id},      Predicted Risk: {predictions_df['predicted_risk'].iloc[idx]},    Probability of High Risk: {predictions_df['risk_probability'].iloc[idx]:.4f}")




