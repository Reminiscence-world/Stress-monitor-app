import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

from risk_engine import run_risk_inference


# ============================================================
# CONFIGURATION
# ============================================================

DB_NAME = "personnel_welfare.db"

# Risk threshold for generating an alert
ALERT_THRESHOLD = 0.75


st.set_page_config(
    page_title="Personnel Welfare Support Dashboard",
    page_icon="📋",
    layout="wide"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# AUDIT LOG
# ============================================================

def log_audit_event(action: str, target_id: str = "ALL"):

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                officer_action TEXT,
                target_personnel_id TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO audit_logs (
                officer_action,
                target_personnel_id
            )
            VALUES (?, ?)
        """, (action, target_id))

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Audit log failure: {e}")


# ============================================================
# CREATE / UPDATE ALERT TABLE
# ============================================================

def ensure_alert_table():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS welfare_notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,

            assessment_id INTEGER,

            personnel_id TEXT,
            risk_score REAL,
            risk_tier TEXT,

            posting_type TEXT,
            continuous_duty_days INTEGER,
            leave_days_due REAL,
            overtime_hours_30d REAL,

            self_assessment_score REAL,

            key_signals TEXT,
            suggested_actions TEXT,
            talking_point TEXT,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            is_read INTEGER DEFAULT 0,
            is_cleared INTEGER DEFAULT 0
        )
    """)

    conn.commit()

    # --------------------------------------------------------
    # Add missing columns if an older notification table exists
    # --------------------------------------------------------

    existing_columns = []

    try:
        columns = cursor.execute(
            "PRAGMA table_info(welfare_notifications)"
        ).fetchall()

        existing_columns = [row["name"] for row in columns]

    except Exception:
        pass

    required_columns = {
        "assessment_id": "INTEGER",
        "personnel_id": "TEXT",
        "risk_score": "REAL",
        "risk_tier": "TEXT",
        "posting_type": "TEXT",
        "continuous_duty_days": "INTEGER",
        "leave_days_due": "REAL",
        "overtime_hours_30d": "REAL",
        "self_assessment_score": "REAL",
        "key_signals": "TEXT",
        "suggested_actions": "TEXT",
        "talking_point": "TEXT",
        "created_at": "DATETIME",
        "is_read": "INTEGER DEFAULT 0",
        "is_cleared": "INTEGER DEFAULT 0"
    }

    for column, data_type in required_columns.items():

        if column not in existing_columns:

            try:
                cursor.execute(
                    f"""
                    ALTER TABLE welfare_notifications
                    ADD COLUMN {column} {data_type}
                    """
                )
            except Exception:
                pass

    conn.commit()
    conn.close()


ensure_alert_table()


# ============================================================
# GET LATEST ASSESSMENT FOR A PERSON
# ============================================================

def get_latest_assessment_id(personnel_id):

    try:

        conn = get_connection()

        row = conn.execute("""
            SELECT assessment_id
            FROM self_assessments
            WHERE personnel_id = ?
            ORDER BY submission_timestamp DESC, assessment_id DESC
            LIMIT 1
        """, (personnel_id,)).fetchone()

        conn.close()

        if row:
            return row["assessment_id"]

    except Exception:
        pass

    return None


# ============================================================
# CONVERT MODEL SIGNAL INTO HUMAN ALERT
# ============================================================

def make_alert_reason(key_signals, talking_point=None):

    if key_signals is None:
        return "elevated operational strain indicators"

    text = str(key_signals).strip()

    if not text:
        return "elevated operational strain indicators"

    # --------------------------------------------------------
    # Clean common model-generated formats
    # --------------------------------------------------------

    text = text.replace("[", "")
    text = text.replace("]", "")
    text = text.replace("'", "")
    text = text.replace('"', "")

    # --------------------------------------------------------
    # Try to identify the actual welfare factor
    # --------------------------------------------------------

    lower = text.lower()

    if "sleep" in lower:
        return "insufficient sleep"

    if "overtime" in lower:
        return "high overtime workload"

    if "continuous duty" in lower or "duty" in lower:
        return "extended continuous duty"

    if "leave" in lower:
        return "accumulated leave backlog"

    if "self assessment" in lower or "self-assessment" in lower:
        return "elevated self-assessment strain"

    if "rest" in lower:
        return "insufficient rest"

    if "fatigue" in lower:
        return "reported fatigue"

    # --------------------------------------------------------
    # If model returns something like:
    # "sleep_hours_band, overtime_hours_last_30d"
    # --------------------------------------------------------

    if "sleep_hours" in lower:
        return "insufficient sleep"

    if "overtime_hours" in lower:
        return "high overtime workload"

    if "continuous_duty_days" in lower:
        return "extended continuous duty"

    if "leave_days" in lower:
        return "accumulated leave backlog"

    # --------------------------------------------------------
    # Final fallback
    # --------------------------------------------------------

    # Keep only first meaningful part instead of showing
    # a huge technical string.
    first_part = text.split(",")[0].strip()

    if len(first_part) > 70:
        first_part = first_part[:67] + "..."

    return first_part


# ============================================================
# CREATE ALERT FOR A NEW HIGH-RISK CHECK-IN
# ============================================================

def create_alert_from_case(case):

    try:

        risk_score = float(case.get("risk_score", 0))

    except Exception:
        return

    # Only generate an alert when risk >= 0.75
    if risk_score < ALERT_THRESHOLD:
        return

    personnel_id = str(case.get("personnel_id", "")).strip()

    if not personnel_id:
        return

    # --------------------------------------------------------
    # Find the latest check-in submitted by this person
    # --------------------------------------------------------

    assessment_id = get_latest_assessment_id(personnel_id)

    # If the model doesn't have an assessment ID and there
    # is no check-in, don't create a welfare alert.
    if assessment_id is None:
        return

    conn = get_connection()

    # --------------------------------------------------------
    # Prevent duplicate alert for the SAME check-in
    # --------------------------------------------------------

    existing = conn.execute("""
        SELECT notification_id
        FROM welfare_notifications
        WHERE assessment_id = ?
        LIMIT 1
    """, (assessment_id,)).fetchone()

    if existing:
        conn.close()
        return

    # --------------------------------------------------------
    # Extract information
    # --------------------------------------------------------

    risk_tier = str(case.get("risk_tier", "High"))

    posting = case.get(
        "posting_type",
        case.get("posting", "Not specified")
    )

    continuous_duty = case.get(
        "continuous_duty_days",
        "N/A"
    )

    leave_due = case.get(
        "leave_days_due",
        "N/A"
    )

    overtime = case.get(
        "overtime_hours_last_30d",
        case.get("overtime_hours_30d", "N/A")
    )

    self_score = case.get(
        "self_assessment_score",
        None
    )

    key_signals = case.get(
        "key_signals",
        ""
    )

    talking_point = case.get(
        "talking_point",
        ""
    )

    suggested_action = case.get(
        "suggested_actions",
        talking_point
    )

    # --------------------------------------------------------
    # Human-readable reason
    # --------------------------------------------------------

    reason = make_alert_reason(
        key_signals,
        talking_point
    )

    # --------------------------------------------------------
    # Insert alert
    # --------------------------------------------------------

    conn.execute("""
        INSERT INTO welfare_notifications (
            assessment_id,
            personnel_id,
            risk_score,
            risk_tier,
            posting_type,
            continuous_duty_days,
            leave_days_due,
            overtime_hours_30d,
            self_assessment_score,
            key_signals,
            suggested_actions,
            talking_point,
            created_at,
            is_read,
            is_cleared
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
    """, (
        assessment_id,
        personnel_id,
        risk_score,
        risk_tier,
        posting,
        continuous_duty,
        leave_due,
        overtime,
        self_score,
        reason,
        suggested_action,
        talking_point,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


# ============================================================
# GET ACTIVE ALERTS
# ============================================================

def get_alerts():

    conn = get_connection()

    rows = conn.execute("""
        SELECT
            notification_id,
            assessment_id,
            personnel_id,
            risk_score,
            risk_tier,
            posting_type,
            continuous_duty_days,
            leave_days_due,
            overtime_hours_30d,
            self_assessment_score,
            key_signals,
            suggested_actions,
            talking_point,
            created_at,
            is_read
        FROM welfare_notifications
        WHERE is_cleared = 0
        ORDER BY created_at DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# ============================================================
# UNREAD ALERT COUNT
# ============================================================

def get_unread_alert_count():

    conn = get_connection()

    row = conn.execute("""
        SELECT COUNT(*) AS count
        FROM welfare_notifications
        WHERE is_read = 0
        AND is_cleared = 0
    """).fetchone()

    conn.close()

    return int(row["count"])


# ============================================================
# MARK ALERT AS READ
# ============================================================

def mark_alert_read(notification_id):

    conn = get_connection()

    conn.execute("""
        UPDATE welfare_notifications
        SET is_read = 1
        WHERE notification_id = ?
    """, (notification_id,))

    conn.commit()
    conn.close()


# ============================================================
# CLEAR ALL ALERTS
# ============================================================

def clear_all_alerts():

    conn = get_connection()

    conn.execute("""
        UPDATE welfare_notifications
        SET is_cleared = 1
    """)

    conn.commit()
    conn.close()


# ============================================================
# LOAD MODEL DATA
# ============================================================

@st.cache_data(ttl=5)
def fetch_dashboard_data():

    return run_risk_inference()


try:

    df = fetch_dashboard_data()

except Exception as e:

    st.error(
        f"Error loading model inference engine: {e}"
    )

    st.stop()


# ============================================================
# CREATE NEW ALERTS BEFORE DISPLAYING THE ICON
# ============================================================

if df is not None and not df.empty:

    for _, case in df.iterrows():

        create_alert_from_case(case)


# ============================================================
# SESSION STATE
# ============================================================

if "show_alerts" not in st.session_state:

    st.session_state.show_alerts = False


# ============================================================
# CUSTOM ALERT ICON STYLE
# ============================================================

st.markdown("""
<style>

.alert-button button {
    border: none !important;
    background: transparent !important;
    font-size: 24px !important;
    padding: 0 !important;
}

.alert-box {
    background: #ffffff;
    border: 1px solid #d9e2ec;
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 20px;
    box-shadow: 0px 5px 18px rgba(0,0,0,0.08);
}

.single-alert {
    background: #fff7f7;
    border-left: 5px solid #d93025;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
    color: #1f2937;
}

.alert-person {
    font-size: 16px;
    font-weight: 700;
    color: #0B2545;
}

.alert-message {
    font-size: 15px;
    margin-top: 5px;
    color: #344054;
}

.alert-time {
    font-size: 11px;
    color: #8a94a6;
    margin-top: 7px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# TOP HEADER + BELL ICON
# ============================================================

header_col, bell_col = st.columns([9, 1])

with header_col:

    st.title(
        "📋 Personnel Welfare & Operational Strain Monitor"
    )

    st.caption(
        "Decision Support Platform • Administrative & Peer-Care Focus Only"
    )


with bell_col:

    st.markdown(
        "<div style='height:18px'></div>",
        unsafe_allow_html=True
    )

    unread_count = get_unread_alert_count()

    if unread_count > 0:

        bell_text = f"🔔 {unread_count}"

    else:

        bell_text = "🔔"

    if st.button(
        bell_text,
        key="bell_button",
        use_container_width=True
    ):

        st.session_state.show_alerts = (
            not st.session_state.show_alerts
        )


# ============================================================
# ALERT PANEL
# ============================================================

if st.session_state.show_alerts:

    alerts = get_alerts()

    st.markdown(
        '<div class="alert-box">',
        unsafe_allow_html=True
    )

    if not alerts:

        st.success("No active welfare alerts.")

    else:

        for alert in alerts:

            personnel_id = alert["personnel_id"]

            score = float(alert["risk_score"])

            reason = alert.get(
                "key_signals",
                "elevated operational strain"
            )

            created_at = alert.get(
                "created_at",
                ""
            )

            # ------------------------------------------------
            # THIS IS THE ACTUAL MESSAGE SHOWN TO THE OFFICER
            # ------------------------------------------------

            message = (
                f"<b>{personnel_id}</b> has a risk score of "
                f"<b>{score:.2f}</b> due to "
                f"<b>{reason}</b>."
            )

            st.markdown(
                f"""
                <div class="single-alert">

                    <div class="alert-person">
                        🔴 Welfare Alert
                    </div>

                    <div class="alert-message">
                        {message}
                    </div>

                    <div class="alert-time">
                        {created_at}
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )

            if not alert["is_read"]:

                if st.button(
                    "Mark as read",
                    key=f"read_{alert['notification_id']}"
                ):

                    mark_alert_read(
                        alert["notification_id"]
                    )

                    st.rerun()

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )


# ============================================================
# ETHICAL NOTICE
# ============================================================

st.warning(
    "**ETHICAL COMPLIANCE & USAGE NOTICE:**\n\n"
    "• **Non-Clinical:** This system is not a diagnostic medical tool "
    "and does not evaluate psychological disorders.\n"
    "• **No Disciplinary Use:** Outputs reflect operational stress "
    "indicators and must not be used for disciplinary actions, "
    "fitness-for-duty boards, or negative performance appraisals.\n"
    "• **Confidentiality & Audit:** Voluntary check-in signals are "
    "isolated and dashboard access is logged."
)


st.markdown("---")


# ============================================================
# SUMMARY METRICS
# ============================================================

col1, col2, col3, col4 = st.columns(4)

total_count = len(df)

high_count = len(
    df[df["risk_tier"] == "High"]
)

mod_count = len(
    df[df["risk_tier"] == "Moderate"]
)

low_count = len(
    df[df["risk_tier"] == "Low"]
)


col1.metric(
    "Total Monitored",
    total_count
)

if total_count > 0:

    high_percentage = round(
        (high_count / total_count) * 100,
        1
    )

else:

    high_percentage = 0


col2.metric(
    "High Priority Welfare Review",
    high_count,
    delta=f"{high_percentage}%",
    delta_color="inverse"
)

col3.metric(
    "Moderate Strain",
    mod_count
)

col4.metric(
    "Baseline / Routine",
    low_count
)


st.markdown("---")


# ============================================================
# FILTERS
# ============================================================

filter_col1, filter_col2 = st.columns([1, 2])


with filter_col1:

    selected_tier = st.selectbox(
        "Filter by Operational Strain Tier:",
        options=[
            "All",
            "High",
            "Moderate",
            "Low"
        ],
        index=1
    )


with filter_col2:

    search_id = st.text_input(
        "Search Pseudonymous Service ID:",
        ""
    ).strip()


filtered_df = df.copy()


if selected_tier != "All":

    filtered_df = filtered_df[
        filtered_df["risk_tier"] == selected_tier
    ]


if search_id:

    filtered_df = filtered_df[
        filtered_df["personnel_id"]
        .astype(str)
        .str.contains(
            search_id,
            case=False,
            na=False
        )
    ]


log_audit_event(
    f"VIEW_FILTERED_ROSTER_TIER_{selected_tier}",
    search_id if search_id else "ROSTER"
)


# ============================================================
# PERSONNEL TABLE
# ============================================================

st.subheader(
    f"Personnel Roster ({len(filtered_df)} records)"
)


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


available_display_cols = [
    col for col in display_cols
    if col in filtered_df.columns
]


export_df = filtered_df[
    available_display_cols
].copy()


export_df = export_df.rename(
    columns={
        "personnel_id": "Service ID",
        "risk_tier": "Strain Tier",
        "risk_score": "Risk Probability",
        "continuous_duty_days": "Continuous Duty (Days)",
        "leave_days_due": "Leave Due (Days)",
        "overtime_hours_last_30d": "Overtime 30d (Hrs)",
        "key_signals": "Primary Contributing Signals",
        "talking_point": "Recommended Supportive Action"
    }
)


st.dataframe(
    export_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# CSV EXPORT
# ============================================================

csv_data = export_df.to_csv(
    index=False
).encode("utf-8")


st.download_button(
    label="📥 Export Welfare Review List",
    data=csv_data,
    file_name=(
        f"welfare_review_"
        f"{selected_tier.lower()}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    ),
    mime="text/csv",
    on_click=lambda:
        log_audit_event(
            f"EXPORT_CSV_TIER_{selected_tier}"
        )
)


st.markdown("---")


# ============================================================
# INDIVIDUAL CASE DRILLDOWN
# ============================================================

st.subheader(
    "🔍 Personnel Case Drilldown"
)


available_ids = filtered_df[
    "personnel_id"
].tolist()


if not available_ids:

    st.info(
        "No personnel match the current filter criteria."
    )

else:

    inspect_id = st.selectbox(
        "Select Service ID for Detailed Dossier:",
        options=available_ids,
        index=0
    )

    case = filtered_df[
        filtered_df["personnel_id"] == inspect_id
    ].iloc[0]


    log_audit_event(
        "VIEW_CASE_DRILLDOWN",
        inspect_id
    )


    dossier_col1, dossier_col2 = st.columns(2)


    with dossier_col1:

        st.write(
            f"**Service ID:** `{case['personnel_id']}`"
        )

        st.write(
            f"**Assessed Operational Tier:** "
            f"`{case['risk_tier']}`"
        )

        st.write(
            f"**Calculated Probability:** "
            f"`{case['risk_score']}`"
        )

        st.write(
            f"**Continuous Duty Duration:** "
            f"{case['continuous_duty_days']} days"
        )

        st.write(
            f"**Accrued Leave Backlog:** "
            f"{case['leave_days_due']} days"
        )

        st.write(
            f"**Overtime Logged (30d):** "
            f"{case['overtime_hours_last_30d']} hours"
        )

        st.write(
            f"**Voluntary Check-in Submitted:** "
            f"{'Yes' if case['has_self_assessment'] == 1 else 'No'}"
        )


    with dossier_col2:

        st.info(
            f"**Key Operational Signals:**\n\n"
            f"{case['key_signals']}"
        )

        st.success(
            f"**Suggested Welfare Approach:**\n\n"
            f"{case['talking_point']}"
        )
