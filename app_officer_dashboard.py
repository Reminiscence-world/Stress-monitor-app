import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from risk_engine import run_risk_inference


# =========================================================
# CONFIGURATION
# =========================================================

DB_NAME = "personnel_welfare.db"

NOTIFICATION_THRESHOLD = 0.75


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Personnel Welfare Support Dashboard",
    page_icon="📋",
    layout="wide"
)


# =========================================================
# SESSION STATE
# =========================================================

if "show_notifications" not in st.session_state:
    st.session_state.show_notifications = False


# =========================================================
# DATABASE / NOTIFICATION SETUP
# =========================================================

def ensure_notification_table():

    conn = sqlite3.connect(DB_NAME)

    cursor = conn.cursor()

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

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            is_read INTEGER DEFAULT 0,

            is_cleared INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


ensure_notification_table()


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
            CREATE TABLE IF NOT EXISTS audit_logs (

                log_id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp DATETIME
                    DEFAULT CURRENT_TIMESTAMP,

                officer_action TEXT,

                target_personnel_id TEXT
            )
        """)

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
# NOTIFICATION FUNCTIONS
# =========================================================

def get_notifications():

    conn = sqlite3.connect(DB_NAME)

    query = """
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
    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df


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
# CREATE NOTIFICATION FROM MODEL RESULT
# =========================================================

def create_notification_from_case(case):

    try:

        risk_score = float(
            case["risk_score"]
        )

        # -----------------------------------------------
        # ONLY CREATE IF RISK >= 0.75
        # -----------------------------------------------

        if risk_score < NOTIFICATION_THRESHOLD:

            return False


        personnel_id = str(
            case["personnel_id"]
        )


        # -----------------------------------------------
        # Get assessment ID if available
        # -----------------------------------------------

        assessment_id = case.get(
            "assessment_id",
            None
        )


        conn = sqlite3.connect(
            DB_NAME
        )

        cursor = conn.cursor()


        # -----------------------------------------------
        # Prevent duplicate assessment alerts
        # -----------------------------------------------

        if assessment_id is not None:

            cursor.execute("""
                SELECT notification_id

                FROM welfare_notifications

                WHERE assessment_id = ?
            """, (
                int(assessment_id),
            ))

            if cursor.fetchone():

                conn.close()

                return False


        # -----------------------------------------------
        # Signals
        # -----------------------------------------------

        signals = case.get(
            "key_signals",
            []
        )

        if isinstance(
            signals,
            (list, tuple)
        ):

            signals_text = "\n".join(
                f"• {x}"
                for x in signals
            )

        else:

            signals_text = str(
                signals
            )


        # -----------------------------------------------
        # Actions
        # -----------------------------------------------

        actions = case.get(
            "suggested_actions",
            []
        )

        if isinstance(
            actions,
            (list, tuple)
        ):

            actions_text = "\n".join(
                f"• {x}"
                for x in actions
            )

        else:

            actions_text = str(
                actions
            )


        # -----------------------------------------------
        # Self assessment
        # -----------------------------------------------

        self_score = case.get(
            "self_assessment_score",
            None
        )

        if pd.isna(self_score):

            self_score = None


        # -----------------------------------------------
        # Insert
        # -----------------------------------------------

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

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, 0, 0
            )
        """, (

            (
                int(assessment_id)
                if assessment_id is not None
                else None
            ),

            personnel_id,

            risk_score,

            str(
                case.get(
                    "risk_tier",
                    "High"
                )
            ),

            str(
                case.get(
                    "posting",
                    "Not specified"
                )
            ),

            int(
                case.get(
                    "continuous_duty_days",
                    0
                )
            ),

            int(
                case.get(
                    "leave_days_due",
                    0
                )
            ),

            float(
                case.get(
                    "overtime_hours_last_30d",
                    0
                )
            ),

            self_score,

            signals_text,

            actions_text,

            str(
                case.get(
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


# =========================================================
# TITLE + NOTIFICATION BAR
# =========================================================

title_col, notification_col = st.columns(
    [8, 2]
)


with title_col:

    st.title(
        "📋 Personnel Welfare & Operational Strain Monitor"
    )

    st.caption(
        "Decision Support Platform • "
        "Administrative & Peer-Care Focus Only"
    )


with notification_col:

    st.markdown(
        """
        <div style="
            text-align:right;
            color:#777;
            font-size:11px;
            font-weight:700;
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
        key="notification_button",
        use_container_width=True
    ):

        st.session_state.show_notifications = (
            not st.session_state.show_notifications
        )

        st.rerun()


# =========================================================
# NOTIFICATION PANEL
# =========================================================

if st.session_state.show_notifications:

    st.markdown("---")


    notifications = get_notifications()


    # -----------------------------------------------------
    # Panel Header
    # -----------------------------------------------------

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

        if not notifications.empty:

            if st.button(
                "✓ Mark All as Read",
                key="mark_all_notifications",
                use_container_width=True
            ):

                mark_all_notifications_read()

                st.rerun()


    st.markdown("")


    # -----------------------------------------------------
    # Empty
    # -----------------------------------------------------

    if notifications.empty:

        st.success(
            "✓ No active high-risk welfare notifications."
        )


    # -----------------------------------------------------
    # Notifications
    # -----------------------------------------------------

    else:

        st.caption(
            f"{len(notifications)} active welfare alert(s)"
        )


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


            if unread:

                st.markdown(
                    "### 🔴 NEW WELFARE ALERT"
                )

            else:

                st.markdown(
                    "### 🟠 Welfare Alert"
                )


            personnel_id = str(
                notification["personnel_id"]
            )

            posting = str(
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


            self_score = (
                notification[
                    "self_assessment_score"
                ]
            )


            if pd.isna(self_score):

                self_score_text = (
                    "Not submitted"
                )

            else:

                self_score_text = (
                    f"{float(self_score):.0f}/25"
                )


            signals = str(
                notification["key_signals"]
            ).replace(
                "\n",
                "<br>"
            )


            actions = str(
                notification["suggested_actions"]
            ).replace(
                "\n",
                "<br>"
            )


            talking_point = str(
                notification["talking_point"]
            )


            # ---------------------------------------------
            # CARD
            # ---------------------------------------------

            st.markdown(
                f"""
                <div style="
                    border:1px solid #D9DEE8;
                    border-left:6px solid #C08A3E;
                    border-radius:12px;
                    padding:20px;
                    background:#F8FBFF;
                    margin-bottom:8px;
                ">

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
                                Personnel {personnel_id}
                            </div>

                            <div style="
                                color:#666;
                                margin-top:4px;
                            ">
                                Posting: {posting}
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
                            ">
                                MODEL RISK
                            </div>

                        </div>

                    </div>


                    <hr>


                    <b>Risk Tier:</b>
                    {risk_tier}

                    <br><br>


                    <b>Continuous Duty:</b>
                    {continuous_duty} days

                    <br>

                    <b>Leave Due:</b>
                    {leave_due} days

                    <br>

                    <b>Overtime:</b>
                    {overtime:.1f} hrs / 30 days

                    <br>

                    <b>Self-Assessment:</b>
                    {self_score_text}

                    <br><br>


                    <b>Key Signals</b>

                    <br>

                    {signals}

                    <br><br>


                    <b>Suggested Welfare Action</b>

                    <br>

                    {actions}

                    <br><br>


                    <b>Guidance:</b>

                    {talking_point}

                </div>
                """,
                unsafe_allow_html=True
            )


            # ---------------------------------------------
            # ACTION BUTTONS
            # ---------------------------------------------

            button_col1, button_col2 = (
                st.columns(2)
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


# =========================================================
# ETHICAL NOTICE
# =========================================================

st.warning(
    "**ETHICAL COMPLIANCE & USAGE NOTICE:**\n\n"
    "• **Non-Clinical:** This system is **not a diagnostic "
    "medical tool** and does not evaluate psychological disorders.\n"
    "• **No Disciplinary Use:** Outputs reflect operational "
    "stress indicators and **must not** be used for disciplinary "
    "actions, fitness-for-duty boards, or negative performance appraisals.\n"
    "• **Confidentiality & Audit:** Voluntary check-in signals "
    "are isolated. Every query and record inspection is logged "
    "for ethical governance."
)


st.markdown("---")


# =========================================================
# FETCH MODEL DATA
# =========================================================

@st.cache_data(ttl=3)
def fetch_dashboard_data():

    return run_risk_inference()


try:

    df = fetch_dashboard_data()

except Exception as e:

    st.error(
        f"Error loading model inference engine: {e}"
    )

    st.stop()


# =========================================================
# AUTOMATICALLY CREATE ALERTS FOR HIGH-RISK CASES
# =========================================================

if not df.empty:

    for _, case in df.iterrows():

        try:

            create_notification_from_case(
                case
            )

        except Exception as e:

            print(
                "Notification generation error:",
                e
            )


# =========================================================
# HIGH-LEVEL SUMMARY METRICS
# =========================================================

col1, col2, col3, col4 = st.columns(4)


total_count = len(df)


high_count = len(
    df[
        df["risk_tier"] == "High"
    ]
)


mod_count = len(
    df[
        df["risk_tier"] == "Moderate"
    ]
)


low_count = len(
    df[
        df["risk_tier"] == "Low"
    ]
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


# =========================================================
# FILTERS
# =========================================================

filter_col1, filter_col2 = (
    st.columns([1, 2])
)


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
        "Search Pseudonymous Service ID "
        "(e.g., CRP-1044):",
        ""
    ).strip()


filtered_df = df.copy()


if selected_tier != "All":

    filtered_df = filtered_df[
        filtered_df["risk_tier"]
        == selected_tier
    ]


if search_id:

    filtered_df = filtered_df[
        filtered_df[
            "personnel_id"
        ].str.contains(
            search_id,
            case=False,
            na=False
        )
    ]


# =========================================================
# AUDIT FILTER
# =========================================================

log_audit_event(
    f"VIEW_FILTERED_ROSTER_TIER_{selected_tier}",
    search_id
    if search_id
    else "ROSTER"
)


# =========================================================
# PRIMARY PERSONNEL TABLE
# =========================================================

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

        "personnel_id":
            "Service ID",

        "risk_tier":
            "Strain Tier",

        "risk_score":
            "Risk Probability",

        "continuous_duty_days":
            "Continuous Duty (Days)",

        "leave_days_due":
            "Leave Due (Days)",

        "overtime_hours_last_30d":
            "Overtime 30d (Hrs)",

        "key_signals":
            "Primary Contributing Signals",

        "talking_point":
            "Recommended Supportive Action"
    }
)


st.dataframe(
    export_df,
    use_container_width=True,
    hide_index=True
)


# =========================================================
# CSV EXPORT
# =========================================================

csv_data = (
    export_df
    .to_csv(index=False)
    .encode("utf-8")
)


st.download_button(
    label="📥 Export Welfare Review List (CSV)",
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


# =========================================================
# PERSONNEL CASE DRILLDOWN
# =========================================================

st.subheader(
    "🔍 Personnel Case Drilldown"
)


available_ids = (
    filtered_df[
        "personnel_id"
    ].tolist()
)


if not available_ids:

    st.info(
        "No personnel match the current "
        "filter criteria."
    )


else:

    inspect_id = st.selectbox(
        "Select Service ID for Detailed Dossier:",
        options=available_ids,
        index=0
    )


    case = filtered_df[
        filtered_df["personnel_id"]
        == inspect_id
    ].iloc[0]


    log_audit_event(
        "VIEW_CASE_DRILLDOWN",
        inspect_id
    )


    dossier_col1, dossier_col2 = (
        st.columns(2)
    )


    with dossier_col1:

        st.write(
            f"**Service ID:** "
            f"`{case['personnel_id']}`"
        )


        st.write(
            f"**Assessed Operational Tier:** "
            f"`{case['risk_tier']}` "
            f"(Calculated Probability: "
            f"`{case['risk_score']}`)"
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
