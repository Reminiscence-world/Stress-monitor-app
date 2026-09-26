import streamlit as st
import pandas as pd
import sqlite3import auth 

from datetime import datetime

from risk_engine import run_risk_inference


def run():
    auth.require_role("administrator") 
    # ============================================================
    # CONFIGURATION
    # ============================================================
    
    DB_NAME = "personnel_welfare.db"
    
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
    # ALERT TABLE
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
        # Make old database compatible
        # --------------------------------------------------------
    
        try:
    
            columns = cursor.execute(
                "PRAGMA table_info(welfare_notifications)"
            ).fetchall()
    
            existing_columns = [
                row["name"]
                for row in columns
            ]
    
        except Exception:
    
            existing_columns = []
    
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
    # GET LATEST ASSESSMENT
    # ============================================================
    
    def get_latest_assessment(personnel_id):
    
        try:
    
            conn = get_connection()
    
            row = conn.execute("""
                SELECT *
                FROM self_assessments
                WHERE personnel_id = ?
                ORDER BY assessment_id DESC
                LIMIT 1
            """, (personnel_id,)).fetchone()
    
            conn.close()
    
            if row:
    
                return dict(row)
    
        except Exception as e:
    
            print(
                f"Assessment lookup error: {e}"
            )
    
        return None
    
    
    # ============================================================
    # FIND THE FIVE CHECK-IN SCORES
    # ============================================================
    
    def get_checkin_reason(personnel_id):
    
        """
        Looks at the latest personnel check-in and tries to find
        the five individual 1-5 responses.
    
        The function supports several possible database column names.
        """
    
        assessment = get_latest_assessment(
            personnel_id
        )
    
        if not assessment:
    
            return (
                "elevated operational strain indicators",
                None
            )
    
        # --------------------------------------------------------
        # Possible column names for each question
        # --------------------------------------------------------
    
        question_columns = {
    
            "inadequate rest after sleep": [
                "sleep_score",
                "rest_score",
                "sleep_rest_score",
                "question_1",
                "q1",
                "q1_score"
            ],
    
            "a workload that feels difficult to manage": [
                "workload_score",
                "daily_workload_score",
                "question_2",
                "q2",
                "q2_score"
            ],
    
            "reduced physical or mental energy": [
                "energy_score",
                "physical_mental_energy_score",
                "question_3",
                "q3",
                "q3_score"
            ],
    
            "limited support from peers or the team": [
                "support_score",
                "peer_support_score",
                "team_support_score",
                "question_4",
                "q4",
                "q4_score"
            ],
    
            "reduced morale or motivation": [
                "morale_score",
                "motivation_score",
                "question_5",
                "q5",
                "q5_score"
            ]
        }
    
        found_scores = {}
    
        # --------------------------------------------------------
        # Search for the actual columns
        # --------------------------------------------------------
    
        for reason, possible_columns in question_columns.items():
    
            for column in possible_columns:
    
                if column in assessment:
    
                    value = assessment[column]
    
                    try:
    
                        if value is not None:
    
                            value = float(value)
    
                            if 1 <= value <= 5:
    
                                found_scores[
                                    reason
                                ] = value
    
                                break
    
                    except Exception:
    
                        pass
    
        # --------------------------------------------------------
        # If the five individual scores exist
        # --------------------------------------------------------
    
        if found_scores:
    
            lowest_score = min(
                found_scores.values()
            )
    
            lowest_reasons = [
                reason
                for reason, score in found_scores.items()
                if score == lowest_score
            ]
    
            # If multiple questions have the same lowest score,
            # mention them together.
            if len(lowest_reasons) == 1:
    
                return (
                    lowest_reasons[0],
                    lowest_score
                )
    
            else:
    
                combined_reason = (
                    " and ".join(lowest_reasons)
                )
    
                return (
                    combined_reason,
                    lowest_score
                )
    
        # --------------------------------------------------------
        # Fallback if individual scores aren't stored
        # --------------------------------------------------------
    
        return (
            "elevated operational strain indicators",
            None
        )
    
    
    # ============================================================
    # HUMAN-READABLE MODEL FALLBACK
    # ============================================================
    
    def make_alert_reason(
        key_signals,
        talking_point=None
    ):
    
        if key_signals is None:
    
            return (
                "elevated operational strain indicators"
            )
    
        text = str(
            key_signals
        ).strip()
    
        if not text:
    
            return (
                "elevated operational strain indicators"
            )
    
        # Remove technical formatting
        text = text.replace("[", "")
        text = text.replace("]", "")
        text = text.replace("'", "")
        text = text.replace('"', "")
    
        lower = text.lower()
    
        if "sleep" in lower:
    
            return "inadequate rest after sleep"
    
        if "rest" in lower:
    
            return "inadequate rest"
    
        if "overtime" in lower:
    
            return "high workload or overtime"
    
        if "workload" in lower:
    
            return "a workload that feels difficult to manage"
    
        if "continuous duty" in lower:
    
            return "extended continuous duty"
    
        if "duty" in lower:
    
            return "extended continuous duty"
    
        if "energy" in lower:
    
            return "reduced physical or mental energy"
    
        if "support" in lower:
    
            return "limited support from peers or the team"
    
        if "peer" in lower:
    
            return "limited support from peers or the team"
    
        if "team" in lower:
    
            return "limited support from peers or the team"
    
        if "morale" in lower:
    
            return "reduced morale or motivation"
    
        if "motivation" in lower:
    
            return "reduced morale or motivation"
    
        if "fatigue" in lower:
    
            return "reported fatigue"
    
        if "leave" in lower:
    
            return "accumulated leave backlog"
    
        # --------------------------------------------------------
        # Final safe fallback
        # --------------------------------------------------------
    
        first_part = text.split(",")[0].strip()
    
        if len(first_part) > 70:
    
            first_part = (
                first_part[:67] + "..."
            )
    
        return first_part
    
    
    # ============================================================
    # CREATE ALERT
    # ============================================================
    
    def create_alert_from_case(case):
    
        try:
    
            risk_score = float(
                case.get("risk_score", 0)
            )
    
        except Exception:
    
            return
    
        # --------------------------------------------------------
        # Only create alert if risk >= 0.75
        # --------------------------------------------------------
    
        if risk_score < ALERT_THRESHOLD:
    
            return
    
        personnel_id = str(
            case.get(
                "personnel_id",
                ""
            )
        ).strip()
    
        if not personnel_id:
    
            return
    
        # --------------------------------------------------------
        # Get latest assessment
        # --------------------------------------------------------
    
        assessment = get_latest_assessment(
            personnel_id
        )
    
        if not assessment:
    
            print(
                f"No assessment found for {personnel_id}"
            )
    
            return
    
        assessment_id = assessment.get(
            "assessment_id"
        )
    
        if assessment_id is None:
    
            return
    
        conn = get_connection()
    
        try:
    
            # ----------------------------------------------------
            # Don't create duplicate alert for same check-in
            # ----------------------------------------------------
    
            existing = conn.execute("""
                SELECT notification_id
                FROM welfare_notifications
                WHERE assessment_id = ?
                LIMIT 1
            """, (
                assessment_id,
            )).fetchone()
    
            if existing:
    
                conn.close()
    
                return
    
            # ----------------------------------------------------
            # FIRST TRY:
            # Use the five individual check-in scores
            # ----------------------------------------------------
    
            reason, checkin_score = (
                get_checkin_reason(
                    personnel_id
                )
            )
    
            # ----------------------------------------------------
            # FALLBACK:
            # Use model signal if individual answers aren't
            # available in the database.
            # ----------------------------------------------------
    
            if (
                reason ==
                "elevated operational strain indicators"
            ):
    
                reason = make_alert_reason(
                    case.get(
                        "key_signals",
                        ""
                    ),
                    case.get(
                        "talking_point",
                        ""
                    )
                )
    
            # ----------------------------------------------------
            # Create the alert
            # ----------------------------------------------------
    
            conn.execute("""
                INSERT INTO welfare_notifications (
                    assessment_id,
                    personnel_id,
                    risk_score,
                    risk_tier,
                    key_signals,
                    talking_point,
                    created_at,
                    is_read,
                    is_cleared
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
            """, (
    
                assessment_id,
    
                personnel_id,
    
                risk_score,
    
                str(
                    case.get(
                        "risk_tier",
                        "High"
                    )
                ),
    
                reason,
    
                case.get(
                    "talking_point",
                    ""
                ),
    
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            ))
    
            conn.commit()
    
            print(
                f"ALERT CREATED: "
                f"{personnel_id} | "
                f"Risk: {risk_score:.2f} | "
                f"Reason: {reason} | "
                f"Assessment: {assessment_id}"
            )
    
        except sqlite3.Error as e:
    
            print(
                f"Notification database error: {e}"
            )
    
        finally:
    
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
    
        return [
            dict(row)
            for row in rows
        ]
    
    
    # ============================================================
    # UNREAD ALERT COUNT
    # ============================================================
    
    def get_unread_alert_count():
    
        conn = get_connection()
    
        row = conn.execute("""
            SELECT COUNT(*)
            FROM welfare_notifications
            WHERE is_read = 0
            AND is_cleared = 0
        """).fetchone()
    
        conn.close()
    
        return int(row[0])
    
    
    # ============================================================
    # MARK ALERT AS READ
    # ============================================================
    
    def mark_alert_read(
        notification_id
    ):
    
        conn = get_connection()
    
        conn.execute("""
            UPDATE welfare_notifications
            SET is_read = 1
            WHERE notification_id = ?
        """, (
            notification_id,
        ))
    
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
    # CREATE NEW ALERTS
    # ============================================================
    
    if df is not None and not df.empty:
    
        for _, case in df.iterrows():
    
            create_alert_from_case(
                case
            )
    
    
    # ============================================================
    # SESSION STATE
    # ============================================================
    
    if "show_alerts" not in st.session_state:
    
        st.session_state.show_alerts = False
    
    
    # ============================================================
    # TOP HEADER
    # ============================================================
    
    header_col, bell_col = st.columns(
        [9, 1]
    )
    
    
    with header_col:
    
        st.title(
            "📋 Personnel Welfare & Operational Strain Monitor"
        )
    
        st.caption(
            "Decision Support Platform • "
            "Administrative & Peer-Care Focus Only"
        )
    
    
    with bell_col:
    
        st.markdown(
            "<div style='height:18px'></div>",
            unsafe_allow_html=True
        )
    
        unread_count = (
            get_unread_alert_count()
        )
    
        if unread_count > 0:
    
            bell_text = (
                f"🔔 {unread_count}"
            )
    
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
    
        st.markdown("---")
    
        if not alerts:
    
            st.info(
                "No active welfare alerts."
            )
    
        else:
    
            for alert in alerts:
    
                personnel_id = str(
                    alert.get(
                        "personnel_id",
                        "Unknown"
                    )
                )
    
                score = float(
                    alert.get(
                        "risk_score",
                        0
                    )
                )
    
                reason = str(
                    alert.get(
                        "key_signals",
                        "elevated operational strain"
                    )
                ).strip()
    
                created_at = str(
                    alert.get(
                        "created_at",
                        ""
                    )
                )
    
                # ------------------------------------------------
                # CLEAN HUMAN-READABLE ALERT
                # ------------------------------------------------
    
                st.error(
                    f"🔴 **{personnel_id}** has a risk score "
                    f"of **{score:.2f}**. "
                    f"The primary concern reported was "
                    f"**{reason}**."
                )
    
                if created_at:
    
                    st.caption(
                        f"Alert generated: {created_at}"
                    )
    
                if not alert["is_read"]:
    
                    if st.button(
                        "Mark as read",
                        key=(
                            f"read_"
                            f"{alert['notification_id']}"
                        )
                    ):
    
                        mark_alert_read(
                            alert[
                                "notification_id"
                            ]
                        )
    
                        st.rerun()
    
    
    # ============================================================
    # ETHICAL NOTICE
    # ============================================================
    
    st.warning(
        "**ETHICAL COMPLIANCE & USAGE NOTICE:**\n\n"
        "• **Non-Clinical:** This system is not a diagnostic "
        "medical tool and does not evaluate psychological disorders.\n"
        "• **No Disciplinary Use:** Outputs reflect operational "
        "stress indicators and must not be used for disciplinary "
        "actions, fitness-for-duty boards, or negative performance "
        "appraisals.\n"
        "• **Confidentiality & Audit:** Voluntary check-in signals "
        "are isolated and dashboard access is logged."
    )
    
    
    st.markdown("---")
    
    
    # ============================================================
    # SUMMARY METRICS
    # ============================================================
    
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
            (
                high_count /
                total_count
            ) * 100,
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
            "Search Pseudonymous Service ID:",
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
            ]
            .astype(str)
            .str.contains(
                search_id,
                case=False,
                na=False
            )
        ]
    
    
    log_audit_event(
        f"VIEW_FILTERED_ROSTER_TIER_"
        f"{selected_tier}",
        search_id
        if search_id
        else "ROSTER"
    )
    
    
    # ============================================================
    # PERSONNEL TABLE
    # ============================================================
    
    st.subheader(
        f"Personnel Roster "
        f"({len(filtered_df)} records)"
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
    
        col
    
        for col in display_cols
    
        if col in filtered_df.columns
    ]
    
    
    export_df = filtered_df[
        available_display_cols
    ].copy()
    
    
    export_df = export_df.rename(
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
    
    
    # ============================================================
    # CSV EXPORT
    # ============================================================
    
    csv_data = (
        export_df
        .to_csv(index=False)
        .encode("utf-8")
    )
    
    
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
                f"EXPORT_CSV_TIER_"
                f"{selected_tier}"
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
            filtered_df[
                "personnel_id"
            ] == inspect_id
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
