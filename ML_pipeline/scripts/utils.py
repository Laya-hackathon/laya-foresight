import pickle, pandas as pd
import joblib
import json
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score,confusion_matrix,classification_report,roc_auc_score
from sklearn.metrics import ConfusionMatrixDisplay



def model_predict(input_df, model):

    prediction = int(model.predict(input_df)[0])
    probability = float(model.predict_proba(input_df)[0][1])

    return prediction, probability


def send_to_agent(prediction, probability, user_id):

    output = { 
        "member_id": str(user_id),
        "predicted_risk": prediction,
        "risk_probability": probability
    }

    with open("output.json", "w") as f:
        json.dump(output, f, indent=4)

    print("Output sent to agent:", output)