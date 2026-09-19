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
    """Ticket 6: Maps continuous risk probability to operational non-clinical bands."""
    if probability < 0.40:
        return "Low"
    elif probability < 0.70:
        return "Moderate"
    else:
        return "High"

def generate_welfare_recommendation(top_factor: str, risk_tier: str, person_data: dict) -> str:
    """
    Ticket 7: Rule-based recommendation engine mapping top drivers to
    non-clinical, administrative and peer-support actions.
    """
    if risk_tier == "Low":
        return "Maintain routine operational tempo and regular peer check-ins."

    # Map driver to administrative or supportive welfare talking points
    if "continuous_duty" in top_factor or "leave" in top_factor:
        return "Recommend workload review and prioritization of accrued leave entitlement."
    elif "transfers" in top_factor:
        return "Recommend a welfare check-in focused on station relocation and family support."
    elif "overtime" in top_factor:
        return "Recommend roster audit to rebalance extra-duty and shift allocations."
    elif "resting_hr" in top_factor or "sleep" in top_factor:
        return "Flagged rest imbalance; recommend voluntary rest cycle and recovery scheduling."
    elif "self_assessment" in top_factor and person_data.get("has_self_assessment", 0) == 1:
        return "Voluntary check-in indicates low morale; schedule an informal welfare check-in."
    else:
        return "Conduct routine welfare review and monitor duty cycle adjustments."

def run_risk_inference() -> pd.DataFrame:
    """Executes Ticket 6 inference and Ticket 7 recommendation synthesis."""
    clf, scaler, feature_cols = load_inference_artifacts()
    df = extract_and_engineer_features()

    X = df[feature_cols]
    X_scaled = scaler.transform(X)

    # Ticket 6: Continuous Risk Probability
    risk_probabilities = clf.predict_proba(X_scaled)[:, 1]

    # Ticket 6: Feature contributions (Scaled Value * Weight)
    coefficients = clf.coef_[0]
    contributions = X_scaled * coefficients

    results = []
    for idx in range(len(df)):
        person_contrib = contributions[idx]
        top_factor_idx = int(np.argmax(person_contrib))
        top_factor_name = feature_cols[top_factor_idx]

        prob = round(float(risk_probabilities[idx]), 3)
        tier = categorize_risk_tier(prob)
        person_dict = df.iloc[idx].to_dict()

        # Ticket 7: Generate tailored recommendation
        recommendation = generate_welfare_recommendation(top_factor_name, tier, person_dict)

        results.append({
            "personnel_id": df.iloc[idx]["personnel_id"],
            "risk_score": prob,
            "risk_tier": tier,
            "top_factor": top_factor_name,
            "recommendation": recommendation,
            "continuous_duty_days": int(df.iloc[idx]["continuous_duty_days"]),
            "leave_days_due": int(df.iloc[idx]["leave_days_due"]),
            "overtime_hours_last_30d": int(df.iloc[idx]["overtime_hours_last_30d"]),
            "has_self_assessment": int(df.iloc[idx]["has_self_assessment"])
        })

    inference_df = pd.DataFrame(results).sort_values(by="risk_score", ascending=False)
    return inference_df

if __name__ == "__main__":
    results_df = run_risk_inference()
    print("--- Ticket 7: Inferred Cases with Tailored Recommendations ---")
    print(results_df[["personnel_id", "risk_tier", "top_factor", "recommendation"]].head(5).to_string(index=False))