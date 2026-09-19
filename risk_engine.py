import joblib
import pandas as pd
import numpy as np
from feature_engineering import extract_and_engineer_features

MODEL_FILE = "welfare_model.pkl"
SCALER_FILE = "scaler.pkl"
FEATURES_FILE = "model_features.pkl"

def load_inference_artifacts():
    clf = joblib.load(MODEL_FILE)
    scaler = joblib.load(SCALER_FILE)
    feature_cols = joblib.load(FEATURES_FILE)
    return clf, scaler, feature_cols

def categorize_risk_tier(probability: float) -> str:
    """Ticket 6: Maps probability to operational bands."""
    if probability < 0.40:
        return "Low"
    elif probability < 0.70:
        return "Moderate"
    else:
        return "High"

def build_compact_dossier(top_factors: list, row_data: dict, risk_tier: str) -> dict:
    """
    Ticket 7 Upgrade: Compact, multi-factor, factual talking dossier.
    Strictly administrative and supportive; zero clinical diagnostic labels.
    """
    if risk_tier == "Low":
        return {
            "signals": "Standard baseline metrics",
            "focus_action": "Maintain routine operational tempo and peer check-ins."
        }

    signals = []
    actions = []

    for factor in top_factors:
        if "continuous_duty" in factor:
            signals.append(f"Continuous Duty: {int(row_data['continuous_duty_days'])} days")
            actions.append("Workload/leave-utilization review")
        elif "leave_days_due" in factor:
            signals.append(f"Leave Backlog: {int(row_data['leave_days_due'])} days due")
            actions.append("Leave schedule prioritization")
        elif "overtime" in factor:
            signals.append(f"Overtime: {int(row_data['overtime_hours_last_30d'])} hrs/mo")
            actions.append("Roster rebalancing")
        elif "transfers" in factor:
            signals.append(f"Transfers: {int(row_data['transfers_last_2yrs'])} in 2 yrs")
            actions.append("Family accommodation & relocation check")
        elif "resting_hr" in factor:
            signals.append("Resting HR Band: Elevated")
            actions.append("Recovery cycle check")
        elif "sleep" in factor:
            signals.append("Reported Sleep: <5h band")
            actions.append("Rest cycle assessment")
        elif "self_assessment" in factor and row_data.get("has_self_assessment", 0) == 1:
            signals.append("Voluntary survey indicates fatigue/stress")
            actions.append("Informal welfare conversation")

    # Deduplicate and combine into compact one-liners
    dedup_actions = list(dict.fromkeys(actions))
    
    return {
        "signals": " • ".join(signals) if signals else "Accumulated operational strain indicators",
        "focus_action": "Focus: " + (", ".join(dedup_actions) if dedup_actions else "General welfare follow-up")
    }

def run_risk_inference() -> pd.DataFrame:
    clf, scaler, feature_cols = load_inference_artifacts()
    df = extract_and_engineer_features()

    X = df[feature_cols]
    X_scaled = scaler.transform(X)

    risk_probabilities = clf.predict_proba(X_scaled)[:, 1]
    coefficients = clf.coef_[0]
    contributions = X_scaled * coefficients

    results = []
    for idx in range(len(df)):
        person_contrib = contributions[idx]
        
        # Select the TOP 2 contributing factors for better context
        top_two_indices = np.argsort(person_contrib)[-2:][::-1]
        top_factors = [feature_cols[i] for i in top_two_indices]

        prob = round(float(risk_probabilities[idx]), 3)
        tier = categorize_risk_tier(prob)
        row_dict = df.iloc[idx].to_dict()

        dossier = build_compact_dossier(top_factors, row_dict, tier)

        results.append({
            "personnel_id": df.iloc[idx]["personnel_id"],
            "risk_score": prob,
            "risk_tier": tier,
            "key_signals": dossier["signals"],
            "talking_point": dossier["focus_action"],
            "continuous_duty_days": int(df.iloc[idx]["continuous_duty_days"]),
            "leave_days_due": int(df.iloc[idx]["leave_days_due"]),
            "overtime_hours_last_30d": int(df.iloc[idx]["overtime_hours_last_30d"]),
            "has_self_assessment": int(df.iloc[idx]["has_self_assessment"])
        })

    return pd.DataFrame(results).sort_values(by="risk_score", ascending=False)

if __name__ == "__main__":
    results_df = run_risk_inference()
    print("--- Compact Multi-Factor Dossier Preview (Top 5) ---")
    for _, row in results_df.head(5).iterrows():
        print(f"[{row['personnel_id']}] Tier: {row['risk_tier']} | Score: {row['risk_score']}")
        print(f"  Signals: {row['key_signals']}")
        print(f"  Action:  {row['talking_point']}\n")