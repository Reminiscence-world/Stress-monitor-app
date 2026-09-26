import sqlite3
import pandas as pd

DB_NAME = "personnel_welfare.db"


def extract_and_engineer_features(db_path: str = DB_NAME) -> pd.DataFrame:
    """
    Extracts personnel records + latest voluntary self-assessment
    and prepares the ML feature matrix.

    Important:
    - latest_self_score is taken from the most recent assessment
    - latest_assessment_id is retained for notification tracking
    - self-assessment score is included in the ML features
    """

    conn = sqlite3.connect(db_path)

    # ---------------------------------------------------------
    # Get personnel + MOST RECENT self-assessment
    # ---------------------------------------------------------
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
        p.elevated_welfare_risk,

        s.assessment_id AS latest_assessment_id,
        s.self_assessment_score AS latest_self_score

    FROM personnel_records p

    LEFT JOIN (
        SELECT
            assessment_id,
            personnel_id,
            self_assessment_score,
            submission_timestamp
        FROM self_assessments
        WHERE assessment_id IN (
            SELECT assessment_id
            FROM (
                SELECT
                    assessment_id,
                    personnel_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY personnel_id
                        ORDER BY submission_timestamp DESC, assessment_id DESC
                    ) AS rn
                FROM self_assessments
            )
            WHERE rn = 1
        )
    ) s
    ON p.personnel_id = s.personnel_id

    ORDER BY p.personnel_id ASC;
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    if df.empty:
        return df

    # ---------------------------------------------------------
    # Self-assessment handling
    # ---------------------------------------------------------

    df["has_self_assessment"] = (
        df["latest_self_score"].notnull().astype(int)
    )

    # Neutral score = 15/25
    df["self_assessment_score_imputed"] = (
        df["latest_self_score"].fillna(15.0)
    )

    # ---------------------------------------------------------
    # Deployment encoding
    # ---------------------------------------------------------

    deployment_dummies = pd.get_dummies(
        df["deployment_type"],
        prefix="deploy",
        dtype=int
    )

    # ---------------------------------------------------------
    # Sleep mapping
    # ---------------------------------------------------------

    sleep_map = {
        "<5h": 0,
        "5-7h": 1,
        ">7h": 2
    }

    df["sleep_band_numeric"] = (
        df["sleep_hours_band"]
        .map(sleep_map)
        .fillna(1)
    )

    # ---------------------------------------------------------
    # Resting heart-rate mapping
    # ---------------------------------------------------------

    hr_map = {
        "normal": 0,
        "elevated": 1,
        "high": 2
    }

    df["resting_hr_numeric"] = (
        df["resting_hr_band"]
        .map(hr_map)
        .fillna(0)
    )

    # ---------------------------------------------------------
    # Core ML features
    # ---------------------------------------------------------

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

    # Ensure numeric fields are numeric
    for col in feature_columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0)

    # ---------------------------------------------------------
    # Final engineered dataframe
    # ---------------------------------------------------------

    engineered_df = pd.concat(
        [
            df[
                [
                    "personnel_id",
                    "latest_assessment_id"
                ] + feature_columns
            ],
            deployment_dummies,
            df[["elevated_welfare_risk"]]
        ],
        axis=1
    )

    return engineered_df


if __name__ == "__main__":

    features_df = extract_and_engineer_features()

    print("Feature engineering completed successfully.")
    print(f"Engineered Dataset Shape: {features_df.shape}")

    print("\nSample Features:")
    print(features_df.head(2).T)
