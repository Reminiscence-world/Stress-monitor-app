import sqlite3
import pandas as pd
import os

DB_NAME = "personnel_welfare.db"
CSV_FILE = "synthetic_personnel_welfare_data.csv"

def init_database():
    # 1. Connect to SQLite (creates the file if not present)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 2. Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS personnel_records (
        personnel_id TEXT PRIMARY KEY,
        deployment_type TEXT,
        continuous_duty_days INTEGER,
        leave_days_taken_last_90d INTEGER,
        leave_days_due INTEGER,
        transfers_last_2yrs INTEGER,
        overtime_hours_last_30d INTEGER,
        sleep_hours_band TEXT,
        resting_hr_band TEXT,
        ground_truth_composite_score REAL,
        elevated_welfare_risk INTEGER
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS self_assessments (
        assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        personnel_id TEXT,
        self_assessment_score INTEGER,
        submission_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (personnel_id) REFERENCES personnel_records(personnel_id)
    );
    """)

    # --- NEW: Authentication tables (appended for auth.py) ---------------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        personnel_id TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        department TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        is_active_account INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS administrators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        officer_id TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'welfare_officer',
        is_active_account INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        logout_time TIMESTAMP,
        token TEXT NOT NULL UNIQUE,
        is_active INTEGER NOT NULL DEFAULT 1
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        officer_id TEXT NOT NULL,
        action TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # --- END NEW ------------------------------------------------------------

    
    conn.commit()
    print("Database tables initialized successfully.")
    return conn

def load_data(conn):
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found. Run generate_synthetic_data.py first.")
        return

    df = pd.read_csv(CSV_FILE)

    # Split main records and voluntary assessment into the respective tables
    personnel_df = df[[
        "personnel_id", "deployment_type", "continuous_duty_days",
        "leave_days_taken_last_90d", "leave_days_due", "transfers_last_2yrs",
        "overtime_hours_last_30d", "sleep_hours_band", "resting_hr_band",
        "ground_truth_composite_score", "elevated_welfare_risk"
    ]]

    # Insert main records
    personnel_df.to_sql("personnel_records", conn, if_exists="replace", index=False)
    print(f"Loaded {len(personnel_df)} rows into 'personnel_records'.")

    # Insert optional assessments (only where personnel actually opted in, score != -1)
    assessments_df = df[df["self_assessment_score"] != -1][["personnel_id", "self_assessment_score"]]
    assessments_df.to_sql("self_assessments", conn, if_exists="append", index=False)
    print(f"Loaded {len(assessments_df)} voluntary records into 'self_assessments'.")

    conn.close()

if __name__ == "__main__":
    connection = init_database()
    load_data(connection)
