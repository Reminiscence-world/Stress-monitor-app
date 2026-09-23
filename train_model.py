import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from feature_engineering import extract_and_engineer_features

MODEL_FILE = "welfare_model.pkl"
SCALER_FILE = "scaler.pkl"
FEATURES_FILE = "model_features.pkl"

def train_risk_model():
    # 1. Ingest engineered features from Ticket 4
    df = extract_and_engineer_features()
    
    # 2. Separate identifiers, features (X), and target (y)
    drop_cols = ["personnel_id", "elevated_welfare_risk"]
    feature_cols = [c for c in df.columns if c not in drop_cols]
    
    X = df[feature_cols]
    y = df["elevated_welfare_risk"]

    # 3. Train-Test Split (80/20 stratified split)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # 4. Standardize continuous features for balanced coefficient interpretability
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 5. Train Logistic Regression
    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(X_train_scaled, y_train)

    # 6. Evaluate model metrics
    y_pred = clf.predict(X_test_scaled)
    y_prob = clf.predict_proba(X_test_scaled)[:, 1]

    print("--- Model Performance on Synthetic Holdout Set ---")
    print(classification_report(y_test, y_pred, target_names=["Normal", "Elevated Risk"]))
    print(f"ROC-AUC Score: {roc_auc_score(y_test, y_prob):.3f}\n")

    # 7. Print Model Explainability (Feature Coefficients)
    coefficients = pd.DataFrame({
        "Feature": feature_cols,
        "Coefficient": clf.coef_[0]
    }).sort_values(by="Coefficient", ascending=False)

    print("--- Top Contributing Risk Factors (Learned Weights) ---")
    print(coefficients.to_string(index=False))

    # 8. Save artifacts for Ticket 6 & 8
    joblib.dump(clf, MODEL_FILE)
    joblib.dump(scaler, SCALER_FILE)
    joblib.dump(feature_cols, FEATURES_FILE)
    print(f"\nArtifacts successfully exported: {MODEL_FILE}, {SCALER_FILE}, {FEATURES_FILE}")

if __name__ == "__main__":
    train_risk_model()

#contribution
