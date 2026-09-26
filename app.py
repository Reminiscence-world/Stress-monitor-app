import streamlit as st
import pandas as pd
import sqlite3
import pytz
import auth
import textwrap

st.markdown(
    textwrap.dedent("""
        <div style="font-size: 22px; font-weight: 700;">
            🔔 Welfare Notifications
        </div>
        <div style="font-size: 13px; margin-top: 4px; opacity: 0.85;">
            Personnel requiring welfare attention
        </div>
    """),
    unsafe_allow_html=True
)

from datetime import datetime, time


# =========================================================
# CONFIGURATION
# =========================================================

DB_NAME = "personnel_welfare.db"

NOTIFICATION_THRESHOLD = 0.75

IST = pytz.timezone("Asia/Kolkata")

CHECKIN_DEADLINE = time(10, 0)


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Personnel Welfare Operational Monitoring System",
    page_icon="🛡️",
    layout="wide"
)


# =========================================================
# TIME
# =========================================================

def get_ist_now():

    return datetime.now(IST)


def get_ist_date():

    return get_ist_now().strftime("%Y-%m-%d")


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def ensure_db_initialized():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    # -----------------------------------------------------
    # Personnel table
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personnel_records (

            personnel_id TEXT PRIMARY KEY,

            deployment_type TEXT DEFAULT 'Base Logistics',

            continuous_duty_days INTEGER DEFAULT 0,

            leave_days_taken_last_90d INTEGER DEFAULT 0,

            leave_days_due INTEGER DEFAULT 0,

            transfers_last_2yrs INTEGER DEFAULT 0,

            overtime_hours_last_30d REAL DEFAULT 0,

            sleep_hours_band TEXT DEFAULT '5-7h',

            resting_hr_band TEXT DEFAULT 'normal',

            elevated_welfare_risk INTEGER DEFAULT 0
        )
    """)

    # -----------------------------------------------------
    # Self-assessments
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS self_assessments (

            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,

            personnel_id TEXT NOT NULL,

            submission_timestamp DATETIME
                DEFAULT CURRENT_TIMESTAMP,

            self_assessment_score INTEGER,

            FOREIGN KEY (personnel_id)
                REFERENCES personnel_records(personnel_id)
        )
    """)

    # -----------------------------------------------------
    # Audit logs
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (

            log_id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp DATETIME
                DEFAULT CURRENT_TIMESTAMP,

            officer_action TEXT,

            target_personnel_id TEXT
        )
    """)

    # -----------------------------------------------------
    # Notifications
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS welfare_notifications (

            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,

            assessment_id INTEGER,

            personnel_id TEXT NOT NULL,

            risk_score REAL NOT NULL,

            risk_tier TEXT,

            posting_type TEXT,

            continuous_duty_days INTEGER,

            leave_days_due INTEGER,

            overtime_hours_30d REAL,

            self_assessment_score REAL,

            key_signals TEXT,

            suggested_actions TEXT,

            talking_point TEXT,

            created_at DATETIME
                DEFAULT CURRENT_TIMESTAMP,

            is_read INTEGER DEFAULT 0,

            is_cleared INTEGER DEFAULT 0
        )
    """)

    # -----------------------------------------------------
    # Database migration
    # -----------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(personnel_records)"
    )

    existing_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    required_columns = {

        "deployment_type":
            "TEXT DEFAULT 'Base Logistics'",

        "leave_days_taken_last_90d":
            "INTEGER DEFAULT 0",

        "leave_days_due":
            "INTEGER DEFAULT 0",

        "transfers_last_2yrs":
            "INTEGER DEFAULT 0",

        "overtime_hours_last_30d":
            "REAL DEFAULT 0",

        "sleep_hours_band":
            "TEXT DEFAULT '5-7h'",

        "resting_hr_band":
            "TEXT DEFAULT 'normal'",

        "elevated_welfare_risk":
            "INTEGER DEFAULT 0"
    }

    for column, definition in required_columns.items():

        if column not in existing_columns:

            try:

                cursor.execute(
                    f"""
                    ALTER TABLE personnel_records
                    ADD COLUMN {column} {definition}
                    """
                )

            except sqlite3.Error:
                pass

    # -----------------------------------------------------
    # Migrate old column names
    # -----------------------------------------------------

    if (
        "posting_type" in existing_columns
        and "deployment_type" in existing_columns
    ):

        cursor.execute("""
            UPDATE personnel_records

            SET deployment_type = posting_type

            WHERE
                (deployment_type IS NULL
                 OR deployment_type = '')
                AND posting_type IS NOT NULL
        """)

    if "leave_due_days" in existing_columns:

        cursor.execute("""
            UPDATE personnel_records

            SET leave_days_due = leave_due_days

            WHERE
                (leave_days_due IS NULL
                 OR leave_days_due = 0)
                AND leave_due_days IS NOT NULL
        """)

    if "overtime_hours_30d" in existing_columns:

        cursor.execute("""
            UPDATE personnel_records

            SET overtime_hours_last_30d =
                overtime_hours_30d

            WHERE
                (overtime_hours_last_30d IS NULL
                 OR overtime_hours_last_30d = 0)
                AND overtime_hours_30d IS NOT NULL
        """)

    # -----------------------------------------------------
    # Demo personnel
    # -----------------------------------------------------

    cursor.execute(
        "SELECT COUNT(*) FROM personnel_records"
    )

    personnel_count = cursor.fetchone()[0]

    if personnel_count == 0:

        demo_personnel = [

            (
                "CRP-1001",
                "Active Patrol",
                45,
                10,
                12,
                2,
                28.5,
                "5-7h",
                "elevated",
                0
            ),

            (
                "CRP-1002",
                "Base Logistics",
                12,
                5,
                3,
                0,
                5.0,
                ">7h",
                "normal",
                0
            ),

            (
                "CRP-1003",
                "High Altitude Border Post",
                82,
                5,
                24,
                3,
                46.0,
                "<5h",
                "high",
                1
            ),

            (
                "CRP-1004",
                "Signals",
                5,
                8,
                0,
                0,
                2.0,
                ">7h",
                "normal",
                0
            ),

            (
                "CRP-1005",
                "Active Patrol",
                60,
                4,
                18,
                2,
                38.0,
                "5-7h",
                "elevated",
                1
            ),

            (
                "CRP-1006",
                "Base Logistics",
                18,
                10,
                5,
                1,
                10.0,
                "5-7h",
                "normal",
                0
            ),

            (
                "CRP-1007",
                "Counter-Insurgency QRT",
                95,
                2,
                30,
                4,
                52.0,
                "<5h",
                "high",
                1
            ),

            (
                "CRP-1008",
                "Signals",
                30,
                6,
                8,
                1,
                15.0,
                "5-7h",
                "normal",
                0
            ),

            (
                "CRP-1009",
                "High Altitude Border Post",
                110,
                3,
                35,
                5,
                60.0,
                "<5h",
                "high",
                1
            ),

            (
                "CRP-1010",
                "Base Logistics",
                25,
                9,
                4,
                0,
                12.0,
                ">7h",
                "normal",
                0
            ),

            (
                "CRP-1018",
                "Base Logistics",
                4,
                10,
                12,
                0,
                17.0,
                "5-7h",
                "normal",
                0
            )
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO personnel_records
            (
                personnel_id,
                deployment_type,
                continuous_duty_days,
                leave_days_taken_last_90d,
                leave_days_due,
                transfers_last_2yrs,
                overtime_hours_last_30d,
                sleep_hours_band,
                resting_hr_band,
                elevated_welfare_risk
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, demo_personnel)

    conn.commit()

    conn.close()


ensure_db_initialized()


# =========================================================
# AUTHENTICATION GATE  <-- NEW BLOCK
# =========================================================

if "auth_view" not in st.session_state:
    st.session_state.auth_view = "role_selection"

if not auth.is_authenticated():
    view = st.session_state.auth_view
    if view == "user_login":
        auth.render_user_login()
    elif view == "user_signup":
        auth.render_user_signup()
    elif view == "admin_login":
        auth.render_admin_login()
    else:
        auth.render_role_selection()
    st.stop()   # <-- halts execution here; nothing below runs until logged in


# =========================================================
# DATABASE HELPERS
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

    return [
        row[0]
        for row in rows
    ]


def get_overdue_personnel():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    today = get_ist_date()

    cursor.execute("""
        SELECT
            personnel_id,
            deployment_type

        FROM personnel_records

        WHERE personnel_id NOT IN (

            SELECT DISTINCT personnel_id

            FROM self_assessments

            WHERE date(submission_timestamp) = ?

        )

        ORDER BY personnel_id ASC
    """, (today,))

    rows = cursor.fetchall()

    conn.close()

    return rows


# =========================================================
# AUDIT
# =========================================================

def log_audit_event(
    action: str,
    target_id: str = "ALL"
):

    try:

        conn = sqlite3.connect(DB_NAME)

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO audit_logs
            (
                officer_action,
                target_personnel_id
            )
            VALUES (?, ?)
        """, (
            action,
            target_id
        ))

        conn.commit()

        conn.close()

    except Exception as e:

        print(
            f"Audit log failure: {e}"
        )


# =========================================================
# RISK ENGINE
# =========================================================

@st.cache_data(ttl=3)
def fetch_dashboard_data():

    from risk_engine import run_risk_inference

    return run_risk_inference(
        DB_NAME
    )


# =========================================================
# NOTIFICATION CREATION
# =========================================================

def create_high_risk_notification(person):

    try:

        personnel_id = str(
            person["personnel_id"]
        )

        assessment_id = person.get(
            "assessment_id",
            None
        )

        risk_score = float(
            person["risk_score"]
        )

        # -------------------------------------------------
        # ONLY CREATE ALERT IF RISK >= 0.75
        # -------------------------------------------------

        if risk_score < NOTIFICATION_THRESHOLD:

            return False

        conn = sqlite3.connect(DB_NAME)

        cursor = conn.cursor()

        # -------------------------------------------------
        # Prevent duplicate notification for same
        # assessment
        # -------------------------------------------------

        if assessment_id is not None:

            cursor.execute("""
                SELECT notification_id

                FROM welfare_notifications

                WHERE assessment_id = ?
            """, (
                int(assessment_id),
            ))

            existing = cursor.fetchone()

            if existing:

                conn.close()

                return False

        # -------------------------------------------------
        # Convert signals/actions into readable text
        # -------------------------------------------------

        signals = person.get(
            "key_signals",
            []
        )

        actions = person.get(
            "suggested_actions",
            []
        )

        if isinstance(signals, (list, tuple)):

            signals_text = "\n".join(
                f"• {x}"
                for x in signals
            )

        else:

            signals_text = str(signals)

        if isinstance(actions, (list, tuple)):

            actions_text = "\n".join(
                f"• {x}"
                for x in actions
            )

        else:

            actions_text = str(actions)

        # -------------------------------------------------
        # Self assessment value
        # -------------------------------------------------

        self_score = person.get(
            "self_assessment_score",
            15
        )

        if pd.isna(self_score):

            self_score = 15

        # -------------------------------------------------
        # Insert notification
        # -------------------------------------------------

        cursor.execute("""
            INSERT INTO welfare_notifications
            (
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
                is_read,
                is_cleared
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
        """, (

            (
                int(assessment_id)
                if assessment_id is not None
                else None
            ),

            personnel_id,

            risk_score,

            str(
                person.get(
                    "risk_tier",
                    "High"
                )
            ),

            str(
                person.get(
                    "posting",
                    "Not specified"
                )
            ),

            int(
                person.get(
                    "continuous_duty_days",
                    0
                )
            ),

            int(
                person.get(
                    "leave_days_due",
                    0
                )
            ),

            float(
                person.get(
                    "overtime_hours_last_30d",
                    0
                )
            ),

            float(self_score),

            signals_text,

            actions_text,

            str(
                person.get(
                    "talking_point",
                    ""
                )
            )
        ))

        conn.commit()

        conn.close()

        return True

    except Exception as e:

        print(
            "Notification creation error:",
            e
        )

        return False


def generate_high_risk_notifications(df):

    if df is None or df.empty:

        return

    for _, person in df.iterrows():

        try:

            create_high_risk_notification(
                person
            )

        except Exception as e:

            print(
                "Notification generation error:",
                e
            )


# =========================================================
# NOTIFICATION FETCHING
# =========================================================

def get_notifications():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
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
            is_read,
            is_cleared

        FROM welfare_notifications

        WHERE is_cleared = 0

        ORDER BY notification_id DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    columns = [
        "notification_id",
        "assessment_id",
        "personnel_id",
        "risk_score",
        "risk_tier",
        "posting_type",
        "continuous_duty_days",
        "leave_days_due",
        "overtime_hours_30d",
        "self_assessment_score",
        "key_signals",
        "suggested_actions",
        "talking_point",
        "created_at",
        "is_read",
        "is_cleared"
    ]

    return pd.DataFrame(
        rows,
        columns=columns
    )


def get_unread_notification_count():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)

        FROM welfare_notifications

        WHERE
            is_read = 0
            AND is_cleared = 0
    """)

    count = cursor.fetchone()[0]

    conn.close()

    return int(count)


def mark_notification_read(
    notification_id
):

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE welfare_notifications

        SET is_read = 1

        WHERE notification_id = ?
    """, (
        int(notification_id),
    ))

    conn.commit()

    conn.close()


def mark_all_notifications_read():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE welfare_notifications

        SET is_read = 1

        WHERE
            is_cleared = 0
            AND is_read = 0
    """)

    conn.commit()

    conn.close()


def clear_notification(
    notification_id
):

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE welfare_notifications

        SET
            is_cleared = 1,
            is_read = 1

        WHERE notification_id = ?
    """, (
        int(notification_id),
    ))

    conn.commit()

    conn.close()


# =========================================================
# SESSION STATE
# =========================================================

if "show_notifications" not in st.session_state:

    st.session_state.show_notifications = False


if "submitted" not in st.session_state:

    st.session_state.submitted = False


if "biometric_authenticated" not in st.session_state:

    st.session_state.biometric_authenticated = False


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("Operational Portals")

st.sidebar.write(f"Logged in as **{st.session_state.auth['identifier']}**")

if st.sidebar.button("Logout"):
    auth.logout()
    st.rerun()

st.sidebar.markdown("---")

if auth.current_role() == "administrator":
    app_mode = "Welfare Officer Dashboard"
else:
    app_mode = "Personnel Wellness Self-Check-in"

st.sidebar.caption(f"View: **{app_mode}**")

if st.sidebar.button("🔄 Sync & Refresh Database"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.caption(
    "Security Boundary: Air-Gapped / Unified SQLite Instance"
)


# =========================================================
# WELFARE OFFICER DASHBOARD
# =========================================================

if app_mode == "Welfare Officer Dashboard":

    # -----------------------------------------------------
    # Get latest model results
    # -----------------------------------------------------

    try:

        df = fetch_dashboard_data()

    except Exception as e:

        st.error(
            f"Error loading model inference engine: {e}"
        )

        st.stop()


    # -----------------------------------------------------
    # Create notifications for existing high-risk cases
    # -----------------------------------------------------

    generate_high_risk_notifications(df)


    # =====================================================
    # HEADER + NOTIFICATION BAR
    # =====================================================

    header_col, notification_col = st.columns(
        [8, 2]
    )


    # -----------------------------------------------------
    # LEFT SIDE HEADER
    # -----------------------------------------------------

    with header_col:

        st.title(
            "📋 Personnel Welfare & Operational Strain Monitor"
        )

        st.caption(
            "Decision Support Platform • "
            "Administrative & Peer-Care Focus Only"
        )


    # -----------------------------------------------------
    # RIGHT SIDE NOTIFICATION BUTTON
    # -----------------------------------------------------

    with notification_col:

        st.markdown(
            """
            <div style="
                text-align:right;
                font-size:12px;
                font-weight:700;
                color:#777;
                margin-top:8px;
                margin-bottom:5px;
            ">
                WELFARE CENTER
            </div>
            """,
            unsafe_allow_html=True
        )

        unread_count = (
            get_unread_notification_count()
        )

        if unread_count > 0:

            notification_label = (
                f"🔔 Notifications • "
                f"{unread_count} NEW"
            )

        else:

            notification_label = (
                "🔔 Notifications"
            )


        if st.button(
            notification_label,
            key="open_notifications",
            use_container_width=True
        ):

            st.session_state.show_notifications = (
                not st.session_state.show_notifications
            )

            st.rerun()


    # =====================================================
    # NOTIFICATION PANEL
    # =====================================================

    if st.session_state.show_notifications:

        st.markdown("---")

        # -------------------------------------------------
        # Panel header
        # -------------------------------------------------

        panel_col1, panel_col2 = st.columns(
            [7, 3]
        )

        with panel_col1:

            st.markdown(
                """
                <div style="
                    background:#0B2545;
                    color:white;
                    padding:16px 20px;
                    border-radius:10px;
                    margin-bottom:10px;
                ">

                    <div style="
                        font-size:22px;
                        font-weight:700;
                    ">
                        🔔 Welfare Notifications
                    </div>

                    <div style="
                        font-size:13px;
                        margin-top:4px;
                        opacity:0.85;
                    ">
                        Personnel requiring welfare attention
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )


        with panel_col2:

            notifications = get_notifications()

            if not notifications.empty:

                if st.button(
                    "✓ Mark All as Read",
                    key="mark_all_notifications",
                    use_container_width=True
                ):

                    mark_all_notifications_read()

                    st.rerun()


        # -------------------------------------------------
        # No notifications
        # -------------------------------------------------

        if notifications.empty:

            st.success(
                "✓ No active high-risk welfare notifications."
            )


        # -------------------------------------------------
        # Notifications available
        # -------------------------------------------------

        else:

            st.caption(
                f"{len(notifications)} active "
                f"welfare notification(s)"
            )

            # ---------------------------------------------
            # EACH NOTIFICATION
            # ---------------------------------------------

            for _, notification in (
                notifications.iterrows()
            ):

                risk = float(
                    notification["risk_score"]
                )

                unread = (
                    int(
                        notification["is_read"]
                    ) == 0
                )

                # -----------------------------------------
                # Alert heading
                # -----------------------------------------

                if unread:

                    st.markdown(
                        """
                        <div style="
                            color:#B42318;
                            font-weight:700;
                            font-size:15px;
                            margin-top:15px;
                            margin-bottom:8px;
                        ">
                            🔴 NEW WELFARE ALERT
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                else:

                    st.markdown(
                        """
                        <div style="
                            color:#C08A3E;
                            font-weight:700;
                            font-size:15px;
                            margin-top:15px;
                            margin-bottom:8px;
                        ">
                            🟠 WELFARE ALERT
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                # -----------------------------------------
                # Safe values
                # -----------------------------------------

                personnel_id = str(
                    notification["personnel_id"]
                )

                posting_type = str(
                    notification["posting_type"]
                )

                risk_tier = str(
                    notification["risk_tier"]
                )

                continuous_duty = int(
                    notification[
                        "continuous_duty_days"
                    ]
                )

                leave_due = int(
                    notification[
                        "leave_days_due"
                    ]
                )

                overtime = float(
                    notification[
                        "overtime_hours_30d"
                    ]
                )


                self_score = notification[
                    "self_assessment_score"
                ]

                if pd.isna(self_score):

                    self_score_text = (
                        "Not submitted"
                    )

                else:

                    self_score_text = (
                        f"{float(self_score):.0f}/25"
                    )


                key_signals = str(
                    notification["key_signals"]
                )

                key_signals_html = (
                    key_signals
                    .replace("\n", "<br>")
                )


                suggested_actions = str(
                    notification[
                        "suggested_actions"
                    ]
                )

                suggested_actions_html = (
                    suggested_actions
                    .replace("\n", "<br>")
                )


                talking_point = str(
                    notification[
                        "talking_point"
                    ]
                )


                # -----------------------------------------
                # Notification Card
                # -----------------------------------------

                st.markdown(
                    f"""
                    <div style="
                        border:1px solid #D9DEE8;
                        border-left:6px solid #C08A3E;
                        border-radius:12px;
                        padding:20px;
                        margin-bottom:8px;
                        background:#F8FBFF;
                        box-shadow:
                            0 2px 8px
                            rgba(0,0,0,0.04);
                    ">

                        <!-- HEADER -->

                        <div style="
                            display:flex;
                            justify-content:
                                space-between;
                            align-items:center;
                        ">

                            <div>

                                <div style="
                                    font-size:22px;
                                    font-weight:700;
                                    color:#0B2545;
                                ">
                                    Personnel
                                    {personnel_id}
                                </div>

                                <div style="
                                    font-size:14px;
                                    color:#666;
                                    margin-top:4px;
                                ">
                                    Posting:
                                    {posting_type}
                                </div>

                            </div>


                            <div style="
                                text-align:center;
                                min-width:90px;
                            ">

                                <div style="
                                    font-size:30px;
                                    font-weight:800;
                                    color:#C08A3E;
                                ">
                                    {risk:.2f}
                                </div>

                                <div style="
                                    font-size:11px;
                                    color:#777;
                                    font-weight:600;
                                ">
                                    MODEL RISK
                                </div>

                            </div>

                        </div>


                        <hr style="
                            border:none;
                            border-top:
                                1px solid #D9DEE8;
                            margin:15px 0;
                        ">


                        <!-- RISK TIER -->

                        <div style="
                            font-size:14px;
                            margin-bottom:12px;
                        ">

                            <b>Risk Tier:</b>
                            {risk_tier}

                        </div>


                        <!-- OPERATIONAL FACTORS -->

                        <div style="
                            display:grid;
                            grid-template-columns:
                                repeat(4, 1fr);
                            gap:10px;
                        ">


                            <div style="
                                background:white;
                                padding:12px;
                                border-radius:8px;
                                border:
                                    1px solid #E1E5EC;
                            ">

                                <div style="
                                    font-size:10px;
                                    color:#777;
                                    font-weight:600;
                                ">
                                    CONTINUOUS DUTY
                                </div>

                                <div style="
                                    font-size:20px;
                                    font-weight:700;
                                    color:#0B2545;
                                ">
                                    {continuous_duty}
                                </div>

                                <div style="
                                    font-size:11px;
                                    color:#777;
                                ">
                                    days
                                </div>

                            </div>


                            <div style="
                                background:white;
                                padding:12px;
                                border-radius:8px;
                                border:
                                    1px solid #E1E5EC;
                            ">

                                <div style="
                                    font-size:10px;
                                    color:#777;
                                    font-weight:600;
                                ">
                                    LEAVE DUE
                                </div>

                                <div style="
                                    font-size:20px;
                                    font-weight:700;
                                    color:#0B2545;
                                ">
                                    {leave_due}
                                </div>

                                <div style="
                                    font-size:11px;
                                    color:#777;
                                ">
                                    days
                                </div>

                            </div>


                            <div style="
                                background:white;
                                padding:12px;
                                border-radius:8px;
                                border:
                                    1px solid #E1E5EC;
                            ">

                                <div style="
                                    font-size:10px;
                                    color:#777;
                                    font-weight:600;
                                ">
                                    OVERTIME
                                </div>

                                <div style="
                                    font-size:20px;
                                    font-weight:700;
                                    color:#0B2545;
                                ">
                                    {overtime:.1f}
                                </div>

                                <div style="
                                    font-size:11px;
                                    color:#777;
                                ">
                                    hrs / 30 days
                                </div>

                            </div>


                            <div style="
                                background:white;
                                padding:12px;
                                border-radius:8px;
                                border:
                                    1px solid #E1E5EC;
                            ">

                                <div style="
                                    font-size:10px;
                                    color:#777;
                                    font-weight:600;
                                ">
                                    SELF-ASSESSMENT
                                </div>

                                <div style="
                                    font-size:20px;
                                    font-weight:700;
                                    color:#0B2545;
                                ">
                                    {self_score_text}
                                </div>

                            </div>

                        </div>


                        <!-- KEY SIGNALS -->

                        <div style="
                            margin-top:20px;
                        ">

                            <div style="
                                font-size:14px;
                                font-weight:700;
                                color:#0B2545;
                                margin-bottom:7px;
                            ">
                                Key Signals
                            </div>

                            <div style="
                                font-size:14px;
                                line-height:1.6;
                                color:#444;
                            ">
                                {key_signals_html}
                            </div>

                        </div>


                        <!-- SUGGESTED ACTION -->

                        <div style="
                            margin-top:18px;
                            padding:14px;
                            background:#FFF9EF;
                            border-radius:8px;
                            border:
                                1px solid #F0DFC0;
                        ">

                            <div style="
                                font-size:14px;
                                font-weight:700;
                                color:#0B2545;
                                margin-bottom:7px;
                            ">
                                Suggested Welfare Action
                            </div>

                            <div style="
                                font-size:14px;
                                line-height:1.6;
                                color:#444;
                            ">
                                {suggested_actions_html}
                            </div>

                        </div>


                        <!-- GUIDANCE -->

                        <div style="
                            margin-top:15px;
                            font-size:14px;
                            line-height:1.5;
                            color:#444;
                        ">

                            <b>Guidance:</b>
                            {talking_point}

                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )


                # -----------------------------------------
                # Action buttons
                # -----------------------------------------

                button_col1, button_col2, button_col3 = (
                    st.columns([1.2, 1.2, 5.6])
                )


                with button_col1:

                    if unread:

                        if st.button(
                            "✓ Mark as Read",
                            key=(
                                f"read_"
                                f"{notification['notification_id']}"
                            ),
                            use_container_width=True
                        ):

                            mark_notification_read(
                                notification[
                                    "notification_id"
                                ]
                            )

                            st.rerun()


                with button_col2:

                    if st.button(
                        "Clear Alert",
                        key=(
                            f"clear_"
                            f"{notification['notification_id']}"
                        ),
                        use_container_width=True
                    ):

                        clear_notification(
                            notification[
                                "notification_id"
                            ]
                        )

                        st.rerun()


                st.markdown("---")


    # =====================================================
    # ETHICAL NOTICE
    # =====================================================

    st.warning(
        "**ETHICAL COMPLIANCE & USAGE NOTICE:**\n\n"
        "• **Non-Clinical:** This system is not a "
        "diagnostic medical tool.\n\n"
        "• **No Disciplinary Use:** Outputs reflect "
        "operational welfare indicators and should not "
        "be used for disciplinary actions, fitness-for-duty "
        "boards, or negative performance appraisals.\n\n"
        "• **Confidentiality:** Voluntary check-in signals "
        "should be handled confidentially and used only "
        "for appropriate welfare support."
    )


    st.markdown("---")


    # =====================================================
    # SUMMARY METRICS
    # =====================================================

    if not df.empty:

        high_count = len(
            df[
                df["risk_score"] >= 0.70
            ]
        )

        critical_count = len(
            df[
                df["risk_score"]
                >= NOTIFICATION_THRESHOLD
            ]
        )

        average_risk = (
            df["risk_score"].mean()
        )

        total_personnel = len(df)


        metric1, metric2, metric3, metric4 = (
            st.columns(4)
        )


        with metric1:

            st.metric(
                "Personnel Monitored",
                total_personnel
            )


        with metric2:

            st.metric(
                "High Risk",
                high_count
            )


        with metric3:

            st.metric(
                "Welfare Alerts",
                critical_count
            )


        with metric4:

            st.metric(
                "Average Risk",
                f"{average_risk:.2f}"
            )


    st.markdown("---")


    # =====================================================
    # PRIORITY WELFARE CASES
    # =====================================================

    st.subheader(
        "Priority Welfare Cases"
    )

    critical_cases = df[
        df["risk_score"]
        >= NOTIFICATION_THRESHOLD
    ].copy()


    if critical_cases.empty:

        st.success(
            "No personnel currently meet the "
            "0.75 notification threshold."
        )

    else:

        display_columns = [
            "personnel_id",
            "risk_score",
            "risk_tier",
            "posting",
            "continuous_duty_days",
            "leave_days_due",
            "overtime_hours_last_30d",
            "self_assessment_score"
        ]

        st.dataframe(
            critical_cases[
                display_columns
            ].rename(
                columns={
                    "personnel_id":
                        "Personnel ID",

                    "risk_score":
                        "Risk Score",

                    "risk_tier":
                        "Risk Tier",

                    "posting":
                        "Posting",

                    "continuous_duty_days":
                        "Continuous Duty",

                    "leave_days_due":
                        "Leave Due",

                    "overtime_hours_last_30d":
                        "Overtime / 30d",

                    "self_assessment_score":
                        "Self Check-in"
                }
            ),
            use_container_width=True,
            hide_index=True
        )


    # =====================================================
    # FULL PERSONNEL TABLE
    # =====================================================

    st.markdown("---")

    st.subheader(
        "All Personnel"
    )


    if not df.empty:

        table_columns = [
            "personnel_id",
            "risk_score",
            "risk_tier",
            "posting",
            "continuous_duty_days",
            "leave_days_due",
            "overtime_hours_last_30d",
            "self_assessment_score"
        ]

        st.dataframe(
            df[
                table_columns
            ].rename(
                columns={
                    "personnel_id":
                        "Personnel ID",

                    "risk_score":
                        "Risk Score",

                    "risk_tier":
                        "Risk Tier",

                    "posting":
                        "Posting",

                    "continuous_duty_days":
                        "Continuous Duty",

                    "leave_days_due":
                        "Leave Due",

                    "overtime_hours_last_30d":
                        "Overtime / 30d",

                    "self_assessment_score":
                        "Self Check-in"
                }
            ),
            use_container_width=True,
            hide_index=True
        )


    # =====================================================
    # PERSONNEL CASE EXPLORER
    # =====================================================

    st.markdown("---")

    st.subheader(
        "Personnel Case Explorer"
    )


    if not df.empty:

        selected_id = st.selectbox(
            "Select Personnel",
            df["personnel_id"].tolist()
        )


        selected_rows = df[
            df["personnel_id"]
            == selected_id
        ]


        if not selected_rows.empty:

            person = selected_rows.iloc[0]


            col1, col2, col3 = st.columns(3)


            with col1:

                st.metric(
                    "Risk Score",
                    f"{float(person['risk_score']):.2f}"
                )


            with col2:

                st.metric(
                    "Risk Tier",
                    person["risk_tier"]
                )


            with col3:

                st.metric(
                    "Self Check-in",
                    f"{float(person['self_assessment_score']):.0f}/25"
                )


            st.markdown(
                "### Key Signals"
            )


            for signal in person[
                "key_signals"
            ]:

                st.write(
                    f"• {signal}"
                )


            st.markdown(
                "### Suggested Welfare Actions"
            )


            for action in person[
                "suggested_actions"
            ]:

                st.write(
                    f"• {action}"
                )


            st.info(
                person["talking_point"]
            )


    # =====================================================
    # OVERDUE CHECK-INS
    # =====================================================

    st.markdown("---")

    current_time = get_ist_now()


    overdue_records = (
        get_overdue_personnel()
        if current_time.time()
        >= CHECKIN_DEADLINE
        else []
    )


    st.subheader(
        "Overdue Check-ins"
    )


    if overdue_records:

        overdue_df = pd.DataFrame(
            overdue_records,
            columns=[
                "Personnel ID",
                "Posting"
            ]
        )

        st.dataframe(
            overdue_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.success(
            "No overdue check-ins currently detected."
        )


    # =====================================================
    # CSV EXPORT
    # =====================================================

    st.markdown("---")


    if not df.empty:

        csv_data = df.to_csv(
            index=False
        ).encode("utf-8")


        st.download_button(
            "⬇️ Export Welfare Risk Data",
            data=csv_data,
            file_name="welfare_risk_report.csv",
            mime="text/csv"
        )


# =========================================================
# PERSONNEL SELF CHECK-IN
# =========================================================

else:

    st.title(
        "🛡️ Personnel Wellness Self-Check-in"
    )

    st.caption(
        "Voluntary • Confidential • Non-Clinical"
    )


    st.markdown(
        """
        <div style="
            padding:18px;
            border-radius:12px;
            background:#f4f7fb;
            border:1px solid #dce3ec;
        ">

        This voluntary check-in helps the welfare team
        identify operational strain indicators that may
        require appropriate welfare support.

        The system is not a medical diagnostic tool.

        </div>
        """,
        unsafe_allow_html=True
    )


    st.markdown("---")


    # =====================================================
    # ALREADY SUBMITTED
    # =====================================================

    if st.session_state.submitted:

        st.success(
            "✓ Your check-in has been submitted securely."
        )

        st.info(
            "Only one check-in is permitted per day."
        )


        if st.button(
            "Submit Another Check-in"
        ):

            st.session_state.submitted = False

            st.session_state.biometric_authenticated = False

            st.rerun()


    else:

        # =================================================
        # IDENTITY
        # =================================================

        st.subheader(
            "1. Identity & Verification"
        )


        valid_ids = get_valid_personnel_ids()


        personnel_id = st.selectbox(
            "Select Your Service ID",
            options=[""] + valid_ids
        )


        if personnel_id:

            if not st.session_state.biometric_authenticated:

                col1, col2 = st.columns(
                    [2, 1]
                )


                with col1:

                    st.caption(
                        f"Hardware Token / Scanner "
                        f"awaiting input for "
                        f"`{personnel_id}`..."
                    )


                with col2:

                    if st.button(
                        "Simulate Biometric Scan 🖲️"
                    ):

                        st.session_state.biometric_authenticated = True

                        st.rerun()


            else:

                st.success(
                    f"✓ Identity verified for "
                    f"`{personnel_id}`"
                )


                if st.button(
                    "Reset Authentication"
                ):

                    st.session_state.biometric_authenticated = False

                    st.rerun()


        st.markdown("---")


        # =================================================
        # ASSESSMENT
        # =================================================

        st.subheader(
            "2. Daily Well-Being Assessment"
        )


        if not st.session_state.biometric_authenticated:

            st.warning(
                "Please select your Service ID and "
                "complete verification above."
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
                    "3. I have maintained steady physical and mental energy levels today.",
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
            # SUBMIT
            # =================================================

            if submit_btn:

                clean_id = (
                    personnel_id.strip()
                )


                if not clean_id:

                    st.error(
                        "Please select a valid Service ID."
                    )


                elif not consent_given:

                    st.warning(
                        "Please confirm voluntary consent."
                    )


                else:

                    total_score = (
                        q1 + q2 + q3 + q4 + q5
                    )


                    try:

                        conn = sqlite3.connect(
                            DB_NAME
                        )

                        cursor = conn.cursor()


                        # ---------------------------------
                        # Check today's submission
                        # ---------------------------------

                        cursor.execute("""
                            SELECT COUNT(*)

                            FROM self_assessments

                            WHERE
                                personnel_id = ?

                                AND date(
                                    submission_timestamp
                                ) = ?
                        """, (
                            clean_id,
                            get_ist_date()
                        ))


                        already_submitted_today = (
                            cursor.fetchone()[0] > 0
                        )


                        if already_submitted_today:

                            conn.close()

                            st.warning(
                                f"ID {clean_id} has already "
                                f"logged a check-in today."
                            )


                        else:

                            # ---------------------------------
                            # Insert assessment
                            # ---------------------------------

                            cursor.execute("""
                                INSERT INTO self_assessments
                                (
                                    personnel_id,
                                    submission_timestamp,
                                    self_assessment_score
                                )

                                VALUES (?, ?, ?)
                            """, (
                                clean_id,

                                get_ist_now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),

                                total_score
                            ))


                            # Exact assessment ID
                            assessment_id = (
                                cursor.lastrowid
                            )


                            conn.commit()

                            conn.close()


                            # ---------------------------------
                            # Clear cached model
                            # ---------------------------------

                            st.cache_data.clear()


                            # ---------------------------------
                            # Immediately run inference
                            # ---------------------------------

                            from risk_engine import (
                                run_risk_inference
                            )


                            fresh_df = (
                                run_risk_inference(
                                    DB_NAME
                                )
                            )


                            # ---------------------------------
                            # Find exact personnel
                            # ---------------------------------

                            matching = fresh_df[
                                fresh_df[
                                    "personnel_id"
                                ] == clean_id
                            ]


                            notification_created = False


                            if not matching.empty:

                                person = (
                                    matching.iloc[0].copy()
                                )


                                # Tie this notification
                                # to THIS exact assessment

                                person[
                                    "assessment_id"
                                ] = assessment_id


                                # ---------------------------------
                                # ACTUAL NOTIFICATION TRIGGER
                                # ---------------------------------

                                current_risk = float(
                                    person[
                                        "risk_score"
                                    ]
                                )


                                if (
                                    current_risk
                                    >= NOTIFICATION_THRESHOLD
                                ):

                                    notification_created = (
                                        create_high_risk_notification(
                                            person
                                        )
                                    )


                            # ---------------------------------
                            # Success state
                            # ---------------------------------

                            st.session_state.submitted = True

                            st.session_state.biometric_authenticated = False


                            # ---------------------------------
                            # User message
                            # ---------------------------------

                            if notification_created:

                                st.success(
                                    "✓ Check-in submitted securely."
                                )

                                st.info(
                                    "Your check-in has been "
                                    "recorded and routed to the "
                                    "appropriate welfare review workflow."
                                )

                            else:

                                st.success(
                                    "✓ Check-in submitted securely."
                                )


                            st.rerun()


                    except sqlite3.Error as e:

                        st.error(
                            f"Database error: {e}"
                        )


                    except Exception as e:

                        st.error(
                            f"Processing error: {e}"
                        )
