import joblib
import pandas as pd
import numpy as np
from feature_engineering import extract_and_engineer_features

MODEL_FILE = "welfare_model.pkl"
SCALER_FILE = "scaler.pkl"
FEATURES_FILE = "model_features.pkl"

def load_inference_artifacts():
    """Loads serialized model, standard scaler, and feature column sequence."""
    clf = joblib.load(MODEL_FILE)
    scaler = joblib.load(SCALER_FILE)
    feature_cols = joblib.load(FEATURES_FILE)
    return clf, scaler, feature_cols

def categorize_risk_tier(probability: float) -> str:
    """
    Ticket 6: Maps continuous risk probability to operational non-clinical bands.
    Thresholds defined per Section 7 specification.
    """
    if probability < 0.40:
        return "Low"
    elif probability < 0.70:
        return "Moderate"
    else:
        return "High"

def run_risk_inference() -> pd.DataFrame:
    """
    Ticket 6: Executes batch inference across all personnel records,
    calculates top contributing risk drivers, and assigns risk tiers.
    """
    clf, scaler, feature_cols = load_inference_artifacts()
    df = extract_and_engineer_features()

    X = df[feature_cols]
    X_scaled = scaler.transform(X)

    # 1. Continuous Risk Probability: P(elevated_welfare_risk = 1)
    risk_probabilities = clf.predict_proba(X_scaled)[:, 1]

    # 2. Compute individual feature contribution: (Scaled Feature Value * Learned Beta)
    coefficients = clf.coef_[0]
    contributions = X_scaled * coefficients

    results = []
    for idx in range(len(df)):
        person_contrib = contributions[idx]
        top_factor_idx = int(np.argmax(person_contrib))
        top_factor_name = feature_cols[top_factor_idx]

        prob = round(float(risk_probabilities[idx]), 3)
        tier = categorize_risk_tier(prob)

        results.append({
            "personnel_id": df.iloc[idx]["personnel_id"],
            "risk_score": prob,
            "risk_tier": tier,
            "top_factor": top_factor_name,
            "continuous_duty_days": int(df.iloc[idx]["continuous_duty_days"]),
            "leave_days_due": int(df.iloc[idx]["leave_days_due"]),
            "overtime_hours_last_30d": int(df.iloc[idx]["overtime_hours_last_30d"]),
            "has_self_assessment": int(df.iloc[idx]["has_self_assessment"])
        })

    inference_df = pd.DataFrame(results).sort_values(by="risk_score", ascending=False)
    return inference_df

if __name__ == "__main__":
    scores_df = run_risk_inference()
    print("--- Ticket 6: Risk Inference Engine Output ---")
    print(f"Total Personnel Scored: {len(scores_df)}")
    print(f"Risk Tier Breakdown:\n{scores_df['risk_tier'].value_counts().to_string()}\n")
    print("Top 5 Cases by Predicted Strain Probability:")
    print(scores_df[["personnel_id", "risk_score", "risk_tier", "top_factor"]].head(5).to_string(index=False))