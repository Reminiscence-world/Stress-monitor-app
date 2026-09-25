import streamlit as st
import sqlite3

DB_NAME = "personnel_welfare.db"

st.set_page_config(
    page_title="Personnel Wellness Check-in",
    page_icon="🛡️",
    layout="centered"
)

# ---------------------------------------------------------
# Self-healing Schema & Auto-seed for Cloud Deployments
# ---------------------------------------------------------
def ensure_db_initialized():
    """Ensure database, tables, and baseline records exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Personnel Records Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personnel_records (
            personnel_id TEXT PRIMARY KEY,
            continuous_duty_days INTEGER,
            leave_due_days INTEGER,
            overtime_hours_30d REAL,
            posting_type TEXT
        )
    """)
    
    # 2. Self Assessments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS self_assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            personnel_id TEXT,
            submission_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            self_assessment_score INTEGER,
            FOREIGN KEY (personnel_id) REFERENCES personnel_records(personnel_id)
        )
    """)
    
    # Check if baseline personnel exist; if not, seed demo records
    cursor.execute("SELECT COUNT(*) FROM personnel_records")
    if cursor.fetchone()[0] == 0:
        demo_personnel = [
            ("CRP-1001", 45, 12, 28.5, "Active Patrol"),
            ("CRP-1002", 12, 3, 5.0, "Base Logistics"),
            ("CRP-1003", 82, 24, 46.0, "High Altitude Border Post"),
            ("CRP-1004", 5, 0, 2.0, "Signals"),
            ("CRP-1005", 60, 18, 38.0, "Active Patrol"),
            ("CRP-1006", 18, 5, 10.0, "Base Logistics"),
            ("CRP-1007", 95, 30, 52.0, "Counter-Insurgency QRT"),
            ("CRP-1008", 30, 8, 15.0, "Signals"),
            ("CRP-1009", 110, 35, 60.0, "High Altitude Border Post"),
            ("CRP-1010", 25, 4, 12.0, "Base Logistics")
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO personnel_records VALUES (?, ?, ?, ?, ?)", 
            demo_personnel
        )
        conn.commit()
        
    conn.close()

def get_valid_personnel_ids():
    ensure_db_initialized()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT personnel_id FROM personnel_records ORDER BY personnel_id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

# ---------------------------------------------------------
# State Management
# ---------------------------------------------------------
if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "biometric_authenticated" not in st.session_state:
    st.session_state.biometric_authenticated = False

# ---------------------------------------------------------
# Header & Privacy Notice
# ---------------------------------------------------------
st.markdown(
    """
    <h2 style='margin-bottom: 0px; font-weight: 700;'>
        🛡️ Personnel Wellness Self-Check-in
    </h2>
    <p style='color: #6c757d; font-size: 0.95rem; margin-top: 4px; margin-bottom: 20px;'>
        Confidential • Voluntary • Non-Clinical • Air-Gapped Verification
    </p>
    """,
    unsafe_allow_html=True
)

if st.session_state.submitted:
    st.success("Your check-in has been submitted securely. Thank you for taking a moment for your well-being.")
    st.info("To protect submission integrity, only one check-in is permitted per session.")
    if st.button("Submit Another Check-in"):
        st.session_state.submitted = False
        st.session_state.biometric_authenticated = False
        st.rerun()
else:
    st.info(
        "**Voluntary & Non-Clinical Notice:**\n\n"
        "This tool is strictly voluntary and designed to support personal well-being. "
        "It does not provide medical diagnoses, psychological evaluations, or fitness-for-duty assessments."
    )

    valid_ids = get_valid_personnel_ids()

    # ---------------------------------------------------------
    # Anti-Buddy Verification (Biometric / Offline Token Simulation)
    # ---------------------------------------------------------
    st.markdown("### 1. Identity & Biometric Verification")
    personnel_id = st.selectbox(
        "Select Your Pseudonymous Service ID",
        options=[""] + valid_ids,
        help="Select your assigned pseudonymous ID to begin authentication."
    )

    if personnel_id:
        if not st.session_state.biometric_authenticated:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.caption(f"Hardware Token / Scanner awaiting input for `{personnel_id}`...")
            with col2:
                if st.button("Simulate Biometric Scan 🖲️"):
                    st.session_state.biometric_authenticated = True
                    st.rerun()
        else:
            st.success(f"✓ Biometric Identity Confirmed: Match verified for `{personnel_id}` via offline token handshake.")
            if st.button("Reset Authentication"):
                st.session_state.biometric_authenticated = False
                st.rerun()

    st.markdown("---")

    # ---------------------------------------------------------
    # Check-in Form (Locked until authenticated)
    # ---------------------------------------------------------
    st.markdown("### 2. Daily Well-Being Assessment")
    
    if not st.session_state.biometric_authenticated:
        st.warning("Please select your Service ID and complete the Biometric Scan above to unlock the assessment form.")
    else:
        with st.form(key="wellness_form"):
            q1 = st.slider("1. I feel adequately rested after my sleep periods.", 1, 5, 3)
            q2 = st.slider("2. My current daily workload feels manageable.", 1, 5, 3)
            q3 = st.slider("3. I have maintained steady physical and mental energy levels today.", 1, 5, 3)
            q4 = st.slider("4. I feel supported by my peer group and team.", 1, 5, 3)
            q5 = st.slider("5. My overall morale and motivation remain steady.", 1, 5, 3)

            st.markdown("---")
            consent_given = st.checkbox("I voluntarily choose to share this wellness self-check-in.")
            submit_btn = st.form_submit_button("Submit Check-in")

        if submit_btn:
            clean_id = personnel_id.strip()
            if not clean_id:
                st.error("Please select a valid pseudonymous Service ID.")
            elif not consent_given:
                st.warning("Please check the consent confirmation box before submitting.")
            else:
                total_score = q1 + q2 + q3 + q4 + q5
                try:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()

                    # Prevent duplicate submissions on the same calendar day
                    cursor.execute("""
                        SELECT COUNT(*) FROM self_assessments 
                        WHERE personnel_id = ? AND date(submission_timestamp) = date('now')
                    """, (clean_id,))
                    already_submitted_today = cursor.fetchone()[0] > 0

                    if already_submitted_today:
                        st.warning(f"ID {clean_id} has already logged a check-in for today. Only one submission per day is allowed.")
                    else:
                        cursor.execute("""
                            INSERT INTO self_assessments (personnel_id, self_assessment_score)
                            VALUES (?, ?)
                        """, (clean_id, total_score))
                        conn.commit()
                        
                        st.session_state.submitted = True
                        st.rerun()

                    conn.close()
                except sqlite3.Error as e:
                    st.error(f"Database error: {e}")