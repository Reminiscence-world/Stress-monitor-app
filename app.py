import streamlit as st
import pandas as pd
import sqlite3
import pytz
from datetime import datetime, time

DB_NAME = "personnel_welfare.db"

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Personnel Welfare Operational Monitoring System",
    page_icon="🛡️",
    layout="wide"
)

# ---------------------------------------------------------
# Operational Clock & Overdue Check-in Engine (IST)
# ---------------------------------------------------------
IST = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)
current_time_str = now_ist.strftime("%d %b %Y | %H:%M hrs IST")

# Configurable daily reporting cutoff time (10:00 AM IST)
CHECKIN_DEADLINE = time(10, 0)
is_past_deadline = now_ist.time() >= CHECKIN_DEADLINE

# ---------------------------------------------------------
# Database Auto-Initialization & Audit Subsystem
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

    # 3. Compliance Audit Trail Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            officer_action TEXT,
            target_personnel_id TEXT
        )
    """)
    
    # Seed baseline personnel if empty
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
            ("CRP-1010", 25, 4, 12.0, "Base Logistics"),
            ("CRP-1018", 4, 12, 17.0, "Base Logistics")
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO personnel_records VALUES (?, ?, ?, ?, ?)", 
            demo_personnel
        )
        conn.commit()
        
    conn.close()

ensure_db_initialized()

def get_valid_personnel_ids():
    ensure_db_initialized()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT personnel_id FROM personnel_records ORDER BY personnel_id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_overdue_personnel():
    """Identify personnel who have not submitted a check-in for today's IST date."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_str = now_ist.strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT personnel_id, posting_type FROM personnel_records
        WHERE personnel_id NOT IN (
            SELECT DISTINCT personnel_id FROM self_assessments 
            WHERE date(submission_timestamp) = ?
        )
        ORDER BY personnel_id ASC
    """, (today_str,))
    overdue_rows = cursor.fetchall()
    conn.close()
    return overdue_rows

def log_audit_event(action: str, target_id: str = "ALL"):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (officer_action, target_personnel_id)
            VALUES (?, ?)
        """, (action, target_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Audit log failure: {e}")

# Cache expires after 5 seconds to ensure real-time updates when check-ins are logged
@st.cache_data(ttl=5)
def fetch_dashboard_data():
    from risk_engine import run_risk_inference
    return run_risk_inference()

# ---------------------------------------------------------
# Sidebar Portal Navigation
# ---------------------------------------------------------
st.sidebar.title("Operational Portals")
app_mode = st.sidebar.radio(
    "Select View Mode:",
    ["Welfare Officer Dashboard", "Personnel Wellness Self-Check-in"]
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Sync & Refresh Database"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.caption("Security Boundary: Air-Gapped / Unified SQLite Instance")

# =========================================================
# VIEW 1: WELFARE OFFICER DASHBOARD
# =========================================================
if app_mode == "Welfare Officer Dashboard":
    st.title("📋 Personnel Welfare & Operational Strain Monitor")
    st.caption("Decision Support Platform • Administrative & Peer-Care Focus Only")

    st.warning(
        "**ETHICAL COMPLIANCE & USAGE NOTICE:**\n\n"
        "• **Non-Clinical:** This system is **not a diagnostic medical tool** and does not evaluate psychological disorders.\n"
        "• **No Disciplinary Use:** Outputs reflect operational stress indicators (fatigue, duty cycles) and **must not** be used for disciplinary actions, fitness-for-duty boards, or negative performance appraisals.\n"
        "• **Confidentiality & Audit:** Voluntary check-in signals are isolated. Every query and record inspection is logged for ethical governance."
    )

    st.markdown("---")

    try:
        df = fetch_dashboard_data()
    except Exception as e:
        st.error(f"Error loading model inference engine: {e}")
        st.stop()

    # ---------------------------------------------------------
    # Structured Operational Health & Compliance Triage Tray
    # ---------------------------------------------------------
    critical_cases = df[df["risk_score"] >= 0.75]
    overdue_records = get_overdue_personnel() if is_past_deadline else []

    with st.container():
        st.markdown(
            f"""
            <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid #333; 
                        padding: 10px 16px; border-radius: 6px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 600; font-size: 0.95rem; color: #e0e0e0;">
                        Operational Health & Reporting Triage
                    </span>
                    <span style="font-size: 0.85rem; color: #888;">
                        Synced: {current_time_str}
                    </span>
                </div>
            </div>
            """, 
            unsafe_allow_html=True
        )

        col_tray1, col_tray2 = st.columns(2)

        # 1. Critical Strain Follow-Up (Clean, calm collapsible list)
        with col_tray1:
            if not critical_cases.empty:
                with st.expander(f"⚠️ Priority Welfare Reviews ({len(critical_cases)})", expanded=False):
                    st.caption("Personnel exceeding elevated operational strain criteria (P ≥ 0.75):")
                    for _, row in critical_cases.iterrows():
                        st.markdown(
                            f"• **`{row['personnel_id']}`** — Assessed P: `{row['risk_score']}`  \n"
                            f"&nbsp;&nbsp;&nbsp;&nbsp;<small style='color: #888;'>Signals: {row['key_signals']}</small>", 
                            unsafe_allow_html=True
                        )
            else:
                st.success("✓ No personnel exceeding critical strain threshold.")

        # 2. Daily Reporting Window / Overdue Alert
        with col_tray2:
            if is_past_deadline:
                if overdue_records:
                    with st.expander(f"🕒 Check-In Non-Responsive ({len(overdue_records)})", expanded=False):
                        st.caption(f"Reporting window closed at {CHECKIN_DEADLINE.strftime('%H:%M')} IST.")
                        for pid, posting in overdue_records:
                            st.markdown(f"• **`{pid}`** ({posting}) — *Pending check-in*")
                else:
                    st.success("✓ All personnel completed check-in for today.")
            else:
                st.info(f"⏳ Reporting window open. Daily cutoff: **{CHECKIN_DEADLINE.strftime('%H:%M')} IST**.")

    # High-Level Summary Metrics
    col1, col2, col3, col4 = st.columns(4)
    total_count = len(df)
    high_count = len(df[df["risk_tier"] == "High"])
    mod_count = len(df[df["risk_tier"] == "Moderate"])
    low_count = len(df[df["risk_tier"] == "Low"])

    col1.metric("Total Monitored", total_count)
    col2.metric("High Priority Welfare Review", high_count, delta=f"{round((high_count/total_count)*100, 1)}%", delta_color="inverse")
    col3.metric("Moderate Strain", mod_count)
    col4.metric("Baseline / Routine", low_count)

    st.markdown("---")

    # Filters & Controls
    filter_col1, filter_col2 = st.columns([1, 2])

    with filter_col1:
        selected_tier = st.selectbox(
            "Filter by Operational Strain Tier:",
            options=["All", "High", "Moderate", "Low"],
            index=0
        )

    with filter_col2:
        search_id = st.text_input("Search Pseudonymous Service ID (e.g., CRP-1001):", "").strip()

    filtered_df = df.copy()
    if selected_tier != "All":
        filtered_df = filtered_df[filtered_df["risk_tier"] == selected_tier]

    if search_id:
        filtered_df = filtered_df[filtered_df["personnel_id"].str.contains(search_id, case=False, na=False)]

    log_audit_event(f"VIEW_FILTERED_ROSTER_TIER_{selected_tier}", search_id if search_id else "ROSTER")

    # Primary Personnel Table
    st.subheader(f"Personnel Roster ({len(filtered_df)} records)")

    display_cols = [
        "personnel_id",
        "risk_tier",
        "risk_score",
        "continuous_duty_days",
        "leave_days_due",
        "overtime_hours_last_30d",
        "key_signals",
        "talking_point"
    ]

    export_df = filtered_df[display_cols].rename(columns={
        "personnel_id": "Service ID",
        "risk_tier": "Strain Tier",
        "risk_score": "Risk Probability",
        "continuous_duty_days": "Continuous Duty (Days)",
        "leave_days_due": "Leave Due (Days)",
        "overtime_hours_last_30d": "Overtime 30d (Hrs)",
        "key_signals": "Primary Contributing Signals",
        "talking_point": "Recommended Supportive Action"
    })

    st.dataframe(export_df, use_container_width=True, hide_index=True)

    csv_data = export_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Welfare Review List (CSV)",
        data=csv_data,
        file_name=f"welfare_review_{selected_tier.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        on_click=lambda: log_audit_event(f"EXPORT_CSV_TIER_{selected_tier}")
    )

    st.markdown("---")

    # Detailed Individual Inspector
    st.subheader("🔍 Personnel Case Drilldown")
    available_ids = filtered_df["personnel_id"].tolist()

    if not available_ids:
        st.info("No personnel match the current filter criteria.")
    else:
        inspect_id = st.selectbox(
            "Select Service ID for Detailed Dossier:",
            options=available_ids,
            index=0
        )

        case = filtered_df[filtered_df["personnel_id"] == inspect_id].iloc[0]
        log_audit_event("VIEW_CASE_DRILLDOWN", inspect_id)
        
        dossier_col1, dossier_col2 = st.columns(2)
        with dossier_col1:
            st.write(f"**Service ID:** `{case['personnel_id']}`")
            st.write(f"**Assessed Operational Tier:** `{case['risk_tier']}` (Calculated Probability: `{case['risk_score']}`)")
            st.write(f"**Continuous Duty Duration:** {case['continuous_duty_days']} days")
            st.write(f"**Accrued Leave Backlog:** {case['leave_days_due']} days")
            st.write(f"**Overtime Logged (30d):** {case['overtime_hours_last_30d']} hours")
            st.write(f"**Voluntary Check-in Submitted:** {'Yes' if case['has_self_assessment'] == 1 else 'No'}")

        with dossier_col2:
            st.info(f"**Key Operational Signals:**\n\n{case['key_signals']}")
            st.success(f"**Suggested Welfare Approach:**\n\n{case['talking_point']}")

# =========================================================
# VIEW 2: PERSONNEL WELLNESS SELF-CHECK-IN
# =========================================================
else:
    if "submitted" not in st.session_state:
        st.session_state.submitted = False

    if "biometric_authenticated" not in st.session_state:
        st.session_state.biometric_authenticated = False

    st.markdown(
        """
        <h2 style='margin-bottom: 0px; font-weight: 700;'>
            🛡️ Personnel Wellness Self-Check-in
        </h2>
        <p style='color: #6c757d; font-size: 0.95rem; margin-top: 4px; margin-bottom: 20px;'>
            Confidential • Voluntary • Non-Clinical • Biometric Verification Guard
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

                        # Prevent multiple submissions on the same calendar day
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
                            
                            # Invalidate cache so Officer Dashboard reflects update immediately
                            st.cache_data.clear()
                            st.session_state.submitted = True
                            st.rerun()

                        conn.close()
                    except sqlite3.Error as e:
                        st.error(f"Database error: {e}")