import sqlite3
import pandas as pd

DB_NAME = "personnel_welfare.db"

def extract_and_engineer_features(db_path: str = DB_NAME) -> pd.DataFrame:
    """
    Ticket 4: Merges personnel records with voluntary self-assessments
    and transforms raw inputs into an ML-ready feature vector.
    """
    conn = sqlite3.connect(db_path)

    # 1. SQL Query: Get personnel records + their most recent self-assessment
    query = """
    SELECT 
        p.personnel_id,
        p.deployment_type,
        p.continuous_duty_days,
        p.leave_days_taken_last_90d,
        p.leave_days_due,
        p.transfers_last_2yrs,
        p.overtime_hours_last_30d,
        p.sleep_hours_band,
        p.resting_hr_band,
        s.latest_self_score,
        p.elevated_welfare_risk
    FROM personnel_records p
    LEFT JOIN (
        SELECT personnel_id, self_assessment_score AS latest_self_score
        FROM self_assessments
        GROUP BY personnel_id
        HAVING MAX(submission_timestamp)
    ) s ON p.personnel_id = s.personnel_id;
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()

    # 2. Handle voluntary self-assessment sparsity
    # Flag whether assessment exists, impute neutral value (15 out of 25) for non-participants
    df["has_self_assessment"] = df["latest_self_score"].notnull().astype(int)
    df["self_assessment_score_imputed"] = df["latest_self_score"].fillna(15.0)

    # 3. Categorical encoding for deployment type
    deployment_dummies = pd.get_dummies(df["deployment_type"], prefix="deploy", dtype=int)
    
    # 4. Ordinal/numeric mapping for biometric summary bands
    sleep_map = {"<5h": 0, "5-7h": 1, ">7h": 2}
    hr_map = {"normal": 0, "elevated": 1, "high": 2}
    
    df["sleep_band_numeric"] = df["sleep_hours_band"].map(sleep_map).fillna(1)
    df["resting_hr_numeric"] = df["resting_hr_band"].map(hr_map).fillna(0)

    # 5. Assemble final model feature matrix
    feature_columns = [
        "continuous_duty_days",
        "leave_days_taken_last_90d",
        "leave_days_due",
        "transfers_last_2yrs",
        "overtime_hours_last_30d",
        "has_self_assessment",
        "self_assessment_score_imputed",
        "sleep_band_numeric",
        "resting_hr_numeric"
    ]
    
    engineered_df = pd.concat([df[["personnel_id"] + feature_columns], deployment_dummies, df["elevated_welfare_risk"]], axis=1)
    return engineered_df

if __name__ == "__main__":
    features_df = extract_and_engineer_features()
    print("Feature engineering completed successfully.")
    print(f"Engineered Dataset Shape: {features_df.shape}")
    print(f"Sample Features:\n{features_df.head(2).T}")