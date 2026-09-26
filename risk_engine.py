import joblib
import pandas as pd
import numpy as np

from feature_engineering import extract_and_engineer_features


MODEL_FILE = "welfare_model.pkl"
SCALER_FILE = "scaler.pkl"
FEATURE_FILE = "model_features.pkl"


# ---------------------------------------------------------
# Risk tier
# ---------------------------------------------------------

def categorize_risk_tier(probability: float) -> str:

    if probability < 0.40:
        return "Low"

    elif probability < 0.70:
        return "Moderate"

    else:
        return "High"


# ---------------------------------------------------------
# Build welfare dossier
# ---------------------------------------------------------

def build_compact_dossier(
    row_data,
    top_features
):

    signals = []
    actions = []

    continuous_duty = float(
        row_data.get("continuous_duty_days", 0)
    )

    leave_due = float(
        row_data.get("leave_days_due", 0)
    )

    overtime = float(
        row_data.get("overtime_hours_last_30d", 0)
    )

    sleep = float(
        row_data.get("sleep_band_numeric", 1)
    )

    resting_hr = float(
        row_data.get("resting_hr_numeric", 0)
    )

    has_assessment = int(
        row_data.get("has_self_assessment", 0)
    )

    assessment_score = row_data.get(
        "self_assessment_score_imputed",
        15
    )

    # -----------------------------------------------------
    # Operational signals
    # -----------------------------------------------------

    if continuous_duty >= 60:
        signals.append(
            f"Extended continuous duty: {int(continuous_duty)} days"
        )

        actions.append(
            "Review duty-cycle and rest rotation"
        )

    elif continuous_duty >= 30:
        signals.append(
            f"Elevated continuous duty: {int(continuous_duty)} days"
        )

    if overtime >= 40:
        signals.append(
            f"High overtime exposure: {overtime:.1f} hrs / 30 days"
        )

        actions.append(
            "Review recent overtime allocation"
        )

    elif overtime >= 20:
        signals.append(
            f"Elevated overtime: {overtime:.1f} hrs / 30 days"
        )

    if leave_due >= 20:
        signals.append(
            f"High leave balance due: {int(leave_due)} days"
        )

        actions.append(
            "Review pending leave availability"
        )

    elif leave_due >= 10:
        signals.append(
            f"Leave due: {int(leave_due)} days"
        )

    if sleep == 0:
        signals.append(
            "Sleep duration band below 5 hours"
        )

        actions.append(
            "Review recent rest and recovery opportunities"
        )

    elif sleep == 1:
        signals.append(
            "Sleep duration band: 5–7 hours"
        )

    if resting_hr >= 2:
        signals.append(
            "High resting heart-rate band"
        )

    elif resting_hr == 1:
        signals.append(
            "Elevated resting heart-rate band"
        )

    # -----------------------------------------------------
    # Self-assessment
    # -----------------------------------------------------

    if has_assessment == 1:

        signals.append(
            f"Voluntary self-check-in recorded: "
            f"{float(assessment_score):.0f}/25"
        )

        if float(assessment_score) <= 10:

            actions.append(
                "Offer confidential welfare conversation"
            )

        elif float(assessment_score) <= 15:

            actions.append(
                "Consider peer-support follow-up"
            )

    # -----------------------------------------------------
    # Model contributing factors
    # -----------------------------------------------------

    for feature in top_features:

        readable = feature.replace("_", " ")

        if readable not in [
            signal.lower()
            for signal in signals
        ]:

            signals.append(
                f"Model signal: {readable}"
            )

    # -----------------------------------------------------
    # Default action
    # -----------------------------------------------------

    if not actions:

        actions.append(
            "Conduct routine welfare review"
        )

    # Remove duplicates
    signals = list(dict.fromkeys(signals))
    actions = list(dict.fromkeys(actions))

    talking_point = (
        "Begin with a confidential, non-disciplinary welfare conversation "
        "and review the operational factors contributing to the elevated risk."
    )

    return signals, actions, talking_point


# ---------------------------------------------------------
# Main inference function
# ---------------------------------------------------------

def run_risk_inference(
    db_path: str = "personnel_welfare.db"
):

    # -----------------------------------------------------
    # Load model artifacts
    # -----------------------------------------------------

    clf = joblib.load(MODEL_FILE)
    scaler = joblib.load(SCALER_FILE)
    feature_cols = joblib.load(FEATURE_FILE)

    # -----------------------------------------------------
    # Extract features
    # -----------------------------------------------------

    df = extract_and_engineer_features(db_path)

    if df.empty:
        return pd.DataFrame()

    # -----------------------------------------------------
    # Make sure model feature columns exist
    #
    # This is important because deployment dummy columns
    # may differ between training and current database.
    # -----------------------------------------------------

    X = df.reindex(
        columns=feature_cols,
        fill_value=0
    )

    # Ensure numeric
    X = X.apply(
        pd.to_numeric,
        errors="coerce"
    ).fillna(0)

    # -----------------------------------------------------
    # Scale
    # -----------------------------------------------------

    X_scaled = scaler.transform(X)

    # -----------------------------------------------------
    # Prediction
    # -----------------------------------------------------

    probabilities = clf.predict_proba(
        X_scaled
    )[:, 1]

    # -----------------------------------------------------
    # Model contributions
    # -----------------------------------------------------

    contributions = None

    if hasattr(clf, "coef_"):

        contributions = (
            X_scaled *
            clf.coef_[0]
        )

    # -----------------------------------------------------
    # Build results
    # -----------------------------------------------------

    results = []

    for index, row in df.iterrows():

        probability = float(
            probabilities[index]
        )

        risk_tier = categorize_risk_tier(
            probability
        )

        # -------------------------------------------------
        # Top contributing features
        # -------------------------------------------------

        top_features = []

        if contributions is not None:

            contribution_row = contributions[index]

            feature_contributions = list(
                zip(
                    feature_cols,
                    contribution_row
                )
            )

            feature_contributions.sort(
                key=lambda x: abs(x[1]),
                reverse=True
            )

            top_features = [
                feature
                for feature, contribution
                in feature_contributions[:3]
            ]

        # -------------------------------------------------
        # Dossier
        # -------------------------------------------------

        signals, actions, talking_point = (
            build_compact_dossier(
                row.to_dict(),
                top_features
            )
        )

        # -------------------------------------------------
        # Result
        # -------------------------------------------------

        results.append({

            "personnel_id":
                row["personnel_id"],

            "assessment_id":
                row.get(
                    "latest_assessment_id",
                    None
                ),

            "risk_score":
                probability,

            "risk_tier":
                risk_tier,

            "posting":
                row.get(
                    "deployment_type",
                    "Not specified"
                ),

            "continuous_duty_days":
                row.get(
                    "continuous_duty_days",
                    0
                ),

            "leave_days_due":
                row.get(
                    "leave_days_due",
                    0
                ),

            "overtime_hours_last_30d":
                row.get(
                    "overtime_hours_last_30d",
                    0
                ),

            "has_self_assessment":
                row.get(
                    "has_self_assessment",
                    0
                ),

            "self_assessment_score":
                row.get(
                    "self_assessment_score_imputed",
                    15
                ),

            "key_signals":
                signals,

            "suggested_actions":
                actions,

            "talking_point":
                talking_point,

            "top_features":
                top_features
        })

    results_df = pd.DataFrame(results)

    if not results_df.empty:

        results_df = results_df.sort_values(
            "risk_score",
            ascending=False
        ).reset_index(drop=True)

    return results_df


if __name__ == "__main__":

    results = run_risk_inference()

    print("\nRisk inference completed.")

    if not results.empty:

        print(
            results[
                [
                    "personnel_id",
                    "risk_score",
                    "risk_tier",
                    "self_assessment_score"
                ]
            ].to_string(index=False)
        )
