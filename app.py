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

CHECKIN_DEADLINE = time(10, 0)
is_past_deadline = now_ist.time() >= CHECKIN_DEADLINE

# High-risk notification threshold
HIGH_RISK_THRESHOLD = 0.75


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def ensure_db_initialized():
    """Ensure database, tables, and baseline records exist."""

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # -----------------------------------------------------
    # Personnel Records
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personnel_records (
            personnel_id TEXT PRIMARY KEY,
            continuous_duty_days INTEGER,
            leave_due_days INTEGER,
            overtime_hours_30d REAL,
            posting_type TEXT
        )
    """)

    # -----------------------------------------------------
    # Self Assessments
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS self_assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            personnel_id TEXT,
            submission_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            self_assessment_score INTEGER,
            FOREIGN KEY (personnel_id)
            REFERENCES personnel_records(personnel_id)
        )
    """)

    # -----------------------------------------------------
    # Audit Logs
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            officer_action TEXT,
            target_personnel_id TEXT
        )
    """)

    # -----------------------------------------------------
    # HIGH-RISK NOTIFICATIONS TABLE
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS welfare_notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            personnel_id TEXT NOT NULL,
            risk_score REAL NOT NULL,
            risk_tier TEXT,
            posting_type TEXT,
            continuous_duty_days INTEGER,
            leave_days_due INTEGER,
            overtime_hours_30d REAL,
            key_signals TEXT,
            talking_point TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            is_cleared INTEGER DEFAULT 0
        )
    """)

    # -----------------------------------------------------
    # Seed baseline personnel
    # -----------------------------------------------------
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
            """
            INSERT OR IGNORE INTO personnel_records
            VALUES (?, ?, ?, ?, ?)
            """,
            demo_personnel
        )

        conn.commit()

    conn.close()


ensure_db_initialized()


# =========================================================
# DATABASE HELPER FUNCTIONS
# =========================================================

def get_valid_personnel_ids():

    ensure_db_initialized()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT personnel_id
        FROM personnel_records
        ORDER BY personnel_id ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [r[0] for r in rows]


def get_overdue_personnel():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    today_str = now_ist.strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT personnel_id, posting_type
        FROM personnel_records
        WHERE personnel_id NOT IN (
            SELECT DISTINCT personnel_id
            FROM self_assessments
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
            INSERT INTO audit_logs
            (officer_action, target_personnel_id)
            VALUES (?, ?)
        """, (action, target_id))

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Audit log failure: {e}")


# =========================================================
# NOTIFICATION FUNCTIONS
# =========================================================

def create_high_risk_notification(person):

    """
    Create a notification for the Welfare Officer when
    risk_score >= 0.75.

    Prevents duplicate notifications for the same
    personnel ID on the same day.
    """

    try:

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        today_str = now_ist.strftime("%Y-%m-%d")

        # -------------------------------------------------
        # Check if notification already exists today
        # -------------------------------------------------
        cursor.execute("""
            SELECT COUNT(*)
            FROM welfare_notifications
            WHERE personnel_id = ?
            AND date(created_at) = ?
            AND is_cleared = 0
        """, (
            str(person["personnel_id"]),
            today_str
        ))

        already_exists = cursor.fetchone()[0] > 0

        if not already_exists:

            cursor.execute("""
                INSERT INTO welfare_notifications (
                    personnel_id,
                    risk_score,
                    risk_tier,
                    posting_type,
                    continuous_duty_days,
                    leave_days_due,
                    overtime_hours_30d,
                    key_signals,
                    talking_point
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(person["personnel_id"]),
                float(person["risk_score"]),
                str(person.get("risk_tier", "High")),
                str(person.get("posting_type", "N/A")),
                int(person.get("continuous_duty_days", 0)),
                int(person.get("leave_days_due", 0)),
                float(person.get("overtime_hours_last_30d", 0)),
                str(person.get("key_signals", "Operational strain indicators detected.")),
                str(person.get("talking_point", "Confidential welfare follow-up recommended."))
            ))

            conn.commit()

        conn.close()

    except Exception as e:
        print(f"Notification creation error: {e}")


def generate_high_risk_notifications(df):

    """
    Scan dashboard inference results and create
    notifications for all personnel with risk >= 0.75.
    """

    if df is None or df.empty:
        return

    if "risk_score" not in df.columns:
        return

    critical_cases = df[
        df["risk_score"] >= HIGH_RISK_THRESHOLD
    ]

    for _, person in critical_cases.iterrows():
        create_high_risk_notification(person)


def get_notifications():

    conn = sqlite3.connect(DB_NAME)

    query = """
        SELECT
            notification_id,
            personnel_id,
            risk_score,
            risk_tier,
            posting_type,
            continuous_duty_days,
            leave_days_due,
            overtime_hours_30d,
            key_signals,
            talking_point,
            created_at,
            is_read,
            is_cleared
        FROM welfare_notifications
        WHERE is_cleared = 0
        ORDER BY created_at DESC
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    return df


def get_unread_notification_count():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM welfare_notifications
        WHERE is_read = 0
        AND is_cleared = 0
    """)

    count = cursor.fetchone()[0]

    conn.close()

    return count


def mark_notification_read(notification_id):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE welfare_notifications
        SET is_read = 1
        WHERE notification_id = ?
    """, (notification_id,))

    conn.commit()
    conn.close()


def mark_all_notifications_read():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE welfare_notifications
        SET is_read = 1
        WHERE is_cleared = 0
    """)

    conn.commit()
    conn.close()


def clear_notification(notification_id):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE welfare_notifications
        SET is_cleared = 1,
            is_read = 1
        WHERE notification_id = ?
    """, (notification_id,))

    conn.commit()
    conn.close()


# =========================================================
# CACHE — MODEL INFERENCE
# =========================================================

@st.cache_data(ttl=5)
def fetch_dashboard_data():

    from risk_engine import run_risk_inference

    return run_risk_inference()


# =========================================================
# SIDEBAR PORTAL NAVIGATION
# =========================================================

st.sidebar.title("Operational Portals")

app_mode = st.sidebar.radio(
    "Select View Mode:",
    [
        "Welfare Officer Dashboard",
        "Personnel Wellness Self-Check-in"
    ]
)

st.sidebar.markdown("---")

if st.sidebar.button("🔄 Sync & Refresh Database"):

    st.cache_data.clear()
    st.rerun()

st.sidebar.caption(
    "Security Boundary: Air-Gapped / Unified SQLite Instance"
)


# =========================================================
# VIEW 1: WELFARE OFFICER DASHBOARD
# =========================================================

if app_mode == "Welfare Officer Dashboard":

    # -----------------------------------------------------
    # Load Model
    # -----------------------------------------------------

    try:

        df = fetch_dashboard_data()

    except Exception as e:

        st.error(
            f"Error loading model inference engine: {e}"
        )

        st.stop()


    # -----------------------------------------------------
    # Generate Notifications
    # -----------------------------------------------------

    generate_high_risk_notifications(df)


    # -----------------------------------------------------
    # TOP HEADER
    # -----------------------------------------------------

    header_col1, header_col2 = st.columns([4, 1])

    with header_col1:

        st.title(
            "📋 Personnel Welfare & Operational Strain Monitor"
        )

        st.caption(
            "Decision Support Platform • Administrative & Peer-Care Focus Only"
        )

    # -----------------------------------------------------
    # NOTIFICATION BUTTON — TOP RIGHT
    # -----------------------------------------------------

    with header_col2:

        notification_count = get_unread_notification_count()

        if notification_count > 0:

            notification_label = (
                f"🔔 Notifications ({notification_count})"
            )

        else:

            notification_label = "🔔 Notifications"

        if st.button(
            notification_label,
            use_container_width=True
        ):

            st.session_state["show_notifications"] = (
                not st.session_state.get(
                    "show_notifications",
                    False
                )
            )

            st.rerun()


    # -----------------------------------------------------
    # NOTIFICATION PANEL
    # -----------------------------------------------------

    if st.session_state.get("show_notifications", False):

        notifications = get_notifications()

        st.markdown("---")

        notification_header_col1, notification_header_col2 = st.columns(
            [4, 1]
        )

        with notification_header_col1:

            st.subheader(
                "🔔 Welfare Notifications"
            )

        with notification_header_col2:

            if not notifications.empty:

                if st.button(
                    "Mark All Read",
                    use_container_width=True
                ):

                    mark_all_notifications_read()

                    st.rerun()


        if notifications.empty:

            st.success(
                "✓ No active welfare notifications."
            )

        else:

            unread_count = len(
                notifications[
                    notifications["is_read"] == 0
                ]
            )

            if unread_count > 0:

                st.info(
                    f"{unread_count} notification(s) require review."
                )

            # ---------------------------------------------
            # Individual Notifications
            # ---------------------------------------------

            for _, notification in notifications.iterrows():

                notification_id = int(
                    notification["notification_id"]
                )

                personnel_id = notification["personnel_id"]

                risk_score = float(
                    notification["risk_score"]
                )

                is_unread = (
                    int(notification["is_read"]) == 0
                )

                if is_unread:

                    border_color = "#e05252"
                    background_color = "#241414"

                else:

                    border_color = "#555555"
                    background_color = "#191919"


                st.markdown(
                    f"""
                    <div style="
                        background:{background_color};
                        border:1px solid {border_color};
                        border-left:5px solid #e05252;
                        border-radius:8px;
                        padding:16px;
                        margin-bottom:10px;
                    ">

                        <div style="
                            display:flex;
                            justify-content:space-between;
                            align-items:center;
                        ">

                            <div style="
                                font-size:16px;
                                font-weight:700;
                                color:#ffffff;
                            ">
                                🚨 High-Risk Welfare Alert
                            </div>

                            <div style="
                                font-size:18px;
                                font-weight:700;
                                color:#ff9999;
                            ">
                                {risk_score:.2f}
                            </div>

                        </div>

                        <div style="
                            margin-top:10px;
                            color:#dddddd;
                            font-size:14px;
                        ">

                            <b>Personnel ID:</b>
                            {personnel_id}

                            &nbsp;&nbsp;|&nbsp;&nbsp;

                            <b>Risk Tier:</b>
                            {notification["risk_tier"]}

                        </div>

                        <div style="
                            margin-top:8px;
                            color:#aaaaaa;
                            font-size:13px;
                        ">

                            <b>Posting:</b>
                            {notification["posting_type"]}

                            &nbsp;&nbsp;|&nbsp;&nbsp;

                            <b>Continuous Duty:</b>
                            {notification["continuous_duty_days"]} days

                            &nbsp;&nbsp;|&nbsp;&nbsp;

                            <b>Overtime:</b>
                            {notification["overtime_hours_30d"]} hrs

                        </div>

                        <div style="
                            margin-top:12px;
                            background:#202020;
                            border-radius:6px;
                            padding:10px;
                            color:#eeeeee;
                            font-size:13px;
                        ">

                            <b>Possible Stress / Strain Signals</b>
                            <br><br>
                            {notification["key_signals"]}

                        </div>

                        <div style="
                            margin-top:10px;
                            color:#cccccc;
                            font-size:13px;
                        ">

                            <b>Suggested Welfare Approach:</b>
                            {notification["talking_point"]}

                        </div>

                        <div style="
                            margin-top:10px;
                            color:#777777;
                            font-size:11px;
                        ">

                            Alert generated:
                            {notification["created_at"]}

                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

                button_col1, button_col2 = st.columns([1, 1])

                with button_col1:

                    if is_unread:

                        if st.button(
                            "✓ Mark as Read",
                            key=f"read_{notification_id}",
                            use_container_width=True
                        ):

                            mark_notification_read(
                                notification_id
                            )

                            log_audit_event(
                                "MARK_WELFARE_NOTIFICATION_READ",
                                personnel_id
                            )

                            st.rerun()

                with button_col2:

                    if st.button(
                        "Clear Alert",
                        key=f"clear_{notification_id}",
                        use_container_width=True
                    ):

                        clear_notification(
                            notification_id
                        )

                        log_audit_event(
                            "CLEAR_WELFARE_NOTIFICATION",
                            personnel_id
                        )

                        st.rerun()


        st.markdown("---")


    # -----------------------------------------------------
    # ETHICAL COMPLIANCE NOTICE
    # -----------------------------------------------------

    st.warning(
        "**ETHICAL COMPLIANCE & USAGE NOTICE:**\n\n"
        "• **Non-Clinical:** This system is **not a diagnostic medical tool** "
        "and does not evaluate psychological disorders.\n"
        "• **No Disciplinary Use:** Outputs reflect operational stress "
        "indicators and must not be used for disciplinary actions, "
        "fitness-for-duty boards, or negative performance appraisals.\n"
        "• **Confidentiality & Audit:** Voluntary check-in signals are "
        "isolated. Every query and record inspection is logged for ethical governance."
    )

    st.markdown("---")


    # =====================================================
    # HIGH-RISK CASES
    # =====================================================

    critical_cases = df[
        df["risk_score"] >= HIGH_RISK_THRESHOLD
    ]

    if not critical_cases.empty:

        st.markdown(
            """
            <div style="
                background:linear-gradient(90deg,#3a1515,#241212);
                border:1px solid #b84a4a;
                border-left:6px solid #e05252;
                border-radius:8px;
                padding:16px 20px;
                margin-bottom:20px;
            ">

                <div style="
                    font-size:18px;
                    font-weight:700;
                    color:#ffdddd;
                ">
                    🚨 Welfare Attention Required
                </div>

                <div style="
                    font-size:13px;
                    color:#d8bcbc;
                    margin-top:5px;
                ">
                    Personnel with elevated operational strain
                    require confidential welfare follow-up.
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )


        for _, person in critical_cases.iterrows():

            st.markdown(
                f"""
                <div style="
                    background:#171717;
                    border:1px solid #444;
                    border-radius:8px;
                    padding:18px;
                    margin-bottom:12px;
                ">

                    <div style="
                        display:flex;
                        justify-content:space-between;
                        margin-bottom:12px;
                    ">

                        <div>

                            <span style="
                                font-size:17px;
                                font-weight:700;
                                color:#ffffff;
                            ">
                                Personnel {person['personnel_id']}
                            </span>

                            <span style="
                                margin-left:10px;
                                padding:4px 9px;
                                border-radius:12px;
                                background:#542020;
                                color:#ffb5b5;
                                font-size:12px;
                                font-weight:600;
                            ">
                                HIGH PRIORITY
                            </span>

                        </div>

                        <div style="
                            font-size:18px;
                            font-weight:700;
                            color:#ff8f8f;
                        ">
                            Risk: {person['risk_score']:.2f}
                        </div>

                    </div>


                    <div style="
                        display:grid;
                        grid-template-columns:repeat(3,1fr);
                        gap:12px;
                        margin-bottom:14px;
                    ">

                        <div>
                            <div style="color:#888;font-size:12px;">
                                Posting
                            </div>

                            <div style="color:#eee;font-size:14px;">
                                {person['posting_type']}
                            </div>
                        </div>


                        <div>
                            <div style="color:#888;font-size:12px;">
                                Continuous Duty
                            </div>

                            <div style="color:#eee;font-size:14px;">
                                {person['continuous_duty_days']} days
                            </div>
                        </div>


                        <div>
                            <div style="color:#888;font-size:12px;">
                                Overtime — 30 Days
                            </div>

                            <div style="color:#eee;font-size:14px;">
                                {person['overtime_hours_last_30d']} hrs
                            </div>
                        </div>

                    </div>


                    <div style="
                        background:#202020;
                        border-radius:6px;
                        padding:12px;
                        margin-bottom:10px;
                    ">

                        <div style="
                            color:#999;
                            font-size:12px;
                            margin-bottom:5px;
                        ">
                            POSSIBLE STRESS / STRAIN SIGNALS
                        </div>

                        <div style="
                            color:#f0f0f0;
                            font-size:14px;
                        ">
                            {person['key_signals']}
                        </div>

                    </div>


                    <div style="
                        color:#c9c9c9;
                        font-size:13px;
                    ">

                        <b>Suggested welfare approach:</b>
                        {person['talking_point']}

                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )


    # =====================================================
    # OPERATIONAL HEALTH & COMPLIANCE TRAY
    # =====================================================

    overdue_records = (
        get_overdue_personnel()
        if is_past_deadline
        else []
    )

    with st.container():

        st.markdown(
            f"""
            <div style="
                background:rgba(255,255,255,0.02);
                border:1px solid #333;
                padding:10px 16px;
                border-radius:6px;
                margin-bottom:16px;
            ">

                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                ">

                    <span style="
                        font-weight:600;
                        font-size:0.95rem;
                        color:#e0e0e0;
                    ">
                        Operational Health & Reporting Triage
                    </span>

                    <span style="
                        font-size:0.85rem;
                        color:#888;
                    ">
                        Synced: {current_time_str}
                    </span>

                </div>

            </div>
            """,
            unsafe_allow_html=True
        )


        col_tray1, col_tray2 = st.columns(2)


        # -------------------------------------------------
        # Priority Welfare Reviews
        # -------------------------------------------------

        with col_tray1:

            if not critical_cases.empty:

                with st.expander(
                    f"⚠️ Priority Welfare Reviews ({len(critical_cases)})",
                    expanded=False
                ):

                    st.caption(
                        "Personnel exceeding elevated operational "
                        "strain criteria (P ≥ 0.75):"
                    )

                    for _, row in critical_cases.iterrows():

                        st.markdown(
                            f"""
                            • **`{row['personnel_id']}`**
                            — Assessed P: `{row['risk_score']:.2f}`
                            <br>
                            &nbsp;&nbsp;&nbsp;&nbsp;
                            <small style='color:#888;'>
                            Signals: {row['key_signals']}
                            </small>
                            """,
                            unsafe_allow_html=True
                        )

            else:

                st.success(
                    "✓ No personnel exceeding critical strain threshold."
                )


        # -------------------------------------------------
        # Daily Reporting Window
        # -------------------------------------------------

        with col_tray2:

            if is_past_deadline:

                if overdue_records:

                    with st.expander(
                        f"🕒 Check-In Non-Responsive ({len(overdue_records)})",
                        expanded=False
                    ):

                        st.caption(
                            f"Reporting window closed at "
                            f"{CHECKIN_DEADLINE.strftime('%H:%M')} IST."
                        )

                        for pid, posting in overdue_records:

                            st.markdown(
                                f"• **`{pid}`** ({posting}) — "
                                f"*Pending check-in*"
                            )

                else:

                    st.success(
                        "✓ All personnel completed check-in for today."
                    )

            else:

                st.info(
                    f"⏳ Reporting window open. Daily cutoff: "
                    f"**{CHECKIN_DEADLINE.strftime('%H:%M')} IST**."
                )


    # =====================================================
    # SUMMARY METRICS
    # =====================================================

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

    col2.metric(
        "High Priority Welfare Review",
        high_count,
        delta=(
            f"{round((high_count / total_count) * 100, 1)}%"
            if total_count > 0
            else "0%"
        ),
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


    # =====================================================
    # FILTERS
    # =====================================================

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
            index=0
        )


    with filter_col2:

        search_id = st.text_input(
            "Search Pseudonymous Service ID (e.g., CRP-1001):",
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


    # =====================================================
    # PERSONNEL TABLE
    # =====================================================

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


    export_df = filtered_df[
        display_cols
    ].rename(
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


    # =====================================================
    # CSV EXPORT
    # =====================================================

    csv_data = export_df.to_csv(
        index=False
    ).encode("utf-8")


    st.download_button(
        label="📥 Export Welfare Review List (CSV)",
        data=csv_data,
        file_name=(
            f"welfare_review_"
            f"{selected_tier.lower()}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        ),
        mime="text/csv",
        on_click=lambda: log_audit_event(
            f"EXPORT_CSV_TIER_{selected_tier}"
        )
    )


    st.markdown("---")


    # =====================================================
    # INDIVIDUAL INSPECTOR
    # =====================================================

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
                f"`{case['risk_tier']}` "
                f"(Calculated Probability: "
                f"`{case['risk_score']:.2f}`)"
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


# =========================================================
# VIEW 2: PERSONNEL WELLNESS SELF-CHECK-IN
# =========================================================

else:

    # -----------------------------------------------------
    # Session State
    # -----------------------------------------------------

    if "submitted" not in st.session_state:

        st.session_state.submitted = False


    if "biometric_authenticated" not in st.session_state:

        st.session_state.biometric_authenticated = False


    # -----------------------------------------------------
    # Header
    # -----------------------------------------------------

    st.markdown(
        """
        <h2 style='margin-bottom:0px;font-weight:700;'>
            🛡️ Personnel Wellness Self-Check-in
        </h2>

        <p style='
            color:#6c757d;
            font-size:0.95rem;
            margin-top:4px;
            margin-bottom:20px;
        '>
            Confidential • Voluntary • Non-Clinical •
            Biometric Verification Guard
        </p>
        """,
        unsafe_allow_html=True
    )


    # =====================================================
    # AFTER SUBMISSION
    # =====================================================

    if st.session_state.submitted:

        st.success(
            "Your check-in has been submitted securely. "
            "Thank you for taking a moment for your well-being."
        )

        st.info(
            "To protect submission integrity, only one "
            "check-in is permitted per session."
        )


        if st.button(
            "Submit Another Check-in"
        ):

            st.session_state.submitted = False

            st.session_state.biometric_authenticated = False

            st.rerun()


    # =====================================================
    # CHECK-IN FORM
    # =====================================================

    else:

        st.info(
            "**Voluntary & Non-Clinical Notice:**\n\n"
            "This tool is strictly voluntary and designed "
            "to support personal well-being. It does not "
            "provide medical diagnoses, psychological "
            "evaluations, or fitness-for-duty assessments."
        )


        valid_ids = get_valid_personnel_ids()


        # -------------------------------------------------
        # Identity
        # -------------------------------------------------

        st.markdown(
            "### 1. Identity & Biometric Verification"
        )


        personnel_id = st.selectbox(
            "Select Your Pseudonymous Service ID",
            options=[""] + valid_ids,
            help=(
                "Select your assigned pseudonymous ID "
                "to begin authentication."
            )
        )


        if personnel_id:

            if not st.session_state.biometric_authenticated:

                col1, col2 = st.columns([2, 1])


                with col1:

                    st.caption(
                        f"Hardware Token / Scanner awaiting "
                        f"input for `{personnel_id}`..."
                    )


                with col2:

                    if st.button(
                        "Simulate Biometric Scan 🖲️"
                    ):

                        st.session_state.biometric_authenticated = True

                        st.rerun()


            else:

                st.success(
                    f"✓ Biometric Identity Confirmed: "
                    f"Match verified for `{personnel_id}` "
                    f"via offline token handshake."
                )


                if st.button(
                    "Reset Authentication"
                ):

                    st.session_state.biometric_authenticated = False

                    st.rerun()


        st.markdown("---")


        # -------------------------------------------------
        # Assessment
        # -------------------------------------------------

        st.markdown(
            "### 2. Daily Well-Being Assessment"
        )


        if not st.session_state.biometric_authenticated:

            st.warning(
                "Please select your Service ID and complete "
                "the Biometric Scan above to unlock the "
                "assessment form."
            )


        else:

            with st.form(
                key="wellness_form"
            ):

                q1 = st.slider(
                    "1. I feel adequately rested after my sleep periods.",
                    1,
                    5,
                    3
                )


                q2 = st.slider(
                    "2. My current daily workload feels manageable.",
                    1,
                    5,
                    3
                )


                q3 = st.slider(
                    "3. I have maintained steady physical and "
                    "mental energy levels today.",
                    1,
                    5,
                    3
                )


                q4 = st.slider(
                    "4. I feel supported by my peer group and team.",
                    1,
                    5,
                    3
                )


                q5 = st.slider(
                    "5. My overall morale and motivation remain steady.",
                    1,
                    5,
                    3
                )


                st.markdown("---")


                consent_given = st.checkbox(
                    "I voluntarily choose to share this wellness self-check-in."
                )


                submit_btn = st.form_submit_button(
                    "Submit Check-in"
                )


            # =================================================
            # SUBMISSION PROCESS
            # =================================================

            if submit_btn:

                clean_id = personnel_id.strip()


                if not clean_id:

                    st.error(
                        "Please select a valid pseudonymous Service ID."
                    )


                elif not consent_given:

                    st.warning(
                        "Please check the consent confirmation "
                        "box before submitting."
                    )


                else:

                    total_score = (
                        q1 + q2 + q3 + q4 + q5
                    )


                    try:

                        conn = sqlite3.connect(DB_NAME)

                        cursor = conn.cursor()


                        # -------------------------------------
                        # Prevent duplicate submission today
                        # -------------------------------------

                        today_str = now_ist.strftime(
                            "%Y-%m-%d"
                        )


                        cursor.execute(
                            """
                            SELECT COUNT(*)
                            FROM self_assessments
                            WHERE personnel_id = ?
                            AND date(submission_timestamp) = ?
                            """,
                            (
                                clean_id,
                                today_str
                            )
                        )


                        already_submitted_today = (
                            cursor.fetchone()[0] > 0
                        )


                        if already_submitted_today:

                            st.warning(
                                f"ID {clean_id} has already logged "
                                "a check-in for today. Only one "
                                "submission per day is allowed."
                            )


                        else:

                            # ---------------------------------
                            # Save check-in
                            # ---------------------------------

                            cursor.execute(
                                """
                                INSERT INTO self_assessments
                                (
                                    personnel_id,
                                    self_assessment_score,
                                    submission_timestamp
                                )
                                VALUES (?, ?, ?)
                                """,
                                (
                                    clean_id,
                                    total_score,
                                    now_ist.strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    )
                                )
                            )


                            conn.commit()

                            conn.close()


                            # ---------------------------------
                            # Clear model cache
                            # ---------------------------------

                            st.cache_data.clear()


                            # ---------------------------------
                            # Re-run risk model immediately
                            # ---------------------------------

                            try:

                                from risk_engine import run_risk_inference

                                updated_df = (
                                    run_risk_inference()
                                )


                                # ---------------------------------
                                # Find submitted personnel
                                # ---------------------------------

                                submitted_person = (
                                    updated_df[
                                        updated_df["personnel_id"]
                                        == clean_id
                                    ]
                                )


                                if not submitted_person.empty:

                                    person = (
                                        submitted_person.iloc[0]
                                    )


                                    current_risk = float(
                                        person["risk_score"]
                                    )


                                    # ---------------------------------
                                    # CREATE NOTIFICATION
                                    # ---------------------------------

                                    if (
                                        current_risk
                                        >= HIGH_RISK_THRESHOLD
                                    ):

                                        create_high_risk_notification(
                                            person
                                        )


                            except Exception as model_error:

                                print(
                                    "Risk notification model error:",
                                    model_error
                                )


                            # ---------------------------------
                            # Successful submission
                            # ---------------------------------

                            st.session_state.submitted = True

                            st.session_state.biometric_authenticated = False

                            st.rerun()


                    except sqlite3.Error as e:

                        st.error(
                            f"Database error: {e}"
                        )
