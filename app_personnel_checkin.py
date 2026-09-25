import streamlit as st
import sqlite3

DB_NAME = "personnel_welfare.db"

st.set_page_config(
    page_title="Personnel Wellness Check-in",
    page_icon="🛡️",
    layout="centered"
)

# Initialize state flag
if "submitted" not in st.session_state:
    st.session_state.submitted = False

# Before:
# st.title("🛡️ Personnel Wellness Self-Check-in")
# st.caption("Confidential • Voluntary • Non-Clinical")

# Replace with this:
st.markdown(
    """
    <h2 style='margin-bottom: 0px; font-weight: 700;'>
        🛡️ Personnel Wellness Self-Check-in
    </h2>
    <p style='color: #6c757d; font-size: 0.95rem; margin-top: 4px; margin-bottom: 20px;'>
        Confidential • Voluntary • Non-Clinical
    </p>
    """,
    unsafe_allow_html=True
)

if st.session_state.submitted:
    # Form is locked after submission
    st.success("Your check-in has been submitted securely. Thank you for taking a moment for your well-being.")
    st.info("To protect submission integrity, only one check-in is permitted per session.")
    if st.button("Submit Another Check-in"):
        st.session_state.submitted = False
        st.rerun()
else:
    st.info(
        "**Voluntary & Non-Clinical Notice:**\n\n"
        "This tool is strictly voluntary and designed to support personal well-being. "
        "It does not provide medical diagnoses, psychological evaluations, or fitness-for-duty assessments."
    )

    with st.form(key="wellness_form"):
        # Query valid IDs directly from the database to prevent orphan entries
        def get_valid_personnel_ids():
            conn = sqlite3.connect("personnel_welfare.db")
            cursor = conn.cursor()
            cursor.execute("SELECT personnel_id FROM personnel_records ORDER BY personnel_id ASC")
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]

        valid_ids = get_valid_personnel_ids() 
        personnel_id = st.selectbox(
            "Select Your Pseudonymous Service ID",
            options=[""] + valid_ids,
            help="Select your assigned pseudonymous ID to log today's voluntary check-in."
        )
        
        st.markdown("---")
        st.subheader("Daily Well-Being Check")
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
            st.error("Please provide a valid pseudonymous Service ID.")
        elif not consent_given:
            st.warning("Please check the consent confirmation box before submitting.")
        else:
            total_score = q1 + q2 + q3 + q4 + q5
            try:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()

                # Layer 2: Database Check - Prevent multiple submissions on the same calendar day
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
                    
                    # Flip the flag to lock the UI and hide the form
                    st.session_state.submitted = True
                    st.rerun()

                conn.close()
            except sqlite3.Error as e:
                st.error(f"Database error: {e}")