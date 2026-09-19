import streamlit as st
import pandas as pd
from risk_engine import run_risk_inference

# Page configuration
st.set_page_config(
    page_title="Personnel Welfare Support Dashboard",
    page_icon="📋",
    layout="wide"
)

# 1. Mandatory Ethical & Non-Clinical Notice (Spec Section 3 & 8)
st.title("📋 Personnel Welfare & Operational Strain Monitor")
st.caption("Decision Support Platform • Administrative & Peer-Care Focus Only")

st.warning(
    "**ETHICAL COMPLIANCE & USAGE NOTICE:**\n\n"
    "• **Non-Clinical:** This system is **not a diagnostic medical tool** and does not evaluate psychological disorders.\n"
    "• **No Disciplinary Use:** Outputs reflect operational stress indicators (fatigue, duty cycles) and **must not** be used for disciplinary actions, fitness-for-duty boards, or negative performance appraisals.\n"
    "• **Confidentiality:** All voluntary check-in signals are isolated and pseudonymized."
)

st.markdown("---")

# 2. Ingest scored data from Ticket 6 & 7
@st.cache_data(ttl=60)
def fetch_dashboard_data():
    return run_risk_inference()

try:
    df = fetch_dashboard_data()
except Exception as e:
    st.error(f"Error loading model inference engine: {e}")
    st.stop()

# 3. High-Level Summary Metrics
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

# 4. Filters & Controls
filter_col1, filter_col2 = st.columns([1, 2])

with filter_col1:
    selected_tier = st.selectbox(
        "Filter by Operational Strain Tier:",
        options=["All", "High", "Moderate", "Low"],
        index=1  # Defaults to High for immediate triage
    )

with filter_col2:
    search_id = st.text_input("Search Pseudonymous Service ID (e.g., CRP-1044):", "").strip()

filtered_df = df.copy()
if selected_tier != "All":
    filtered_df = filtered_df[filtered_df["risk_tier"] == selected_tier]

if search_id:
    filtered_df = filtered_df[filtered_df["personnel_id"].str.contains(search_id, case=False, na=False)]

# 5. Primary Personnel Table
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

st.dataframe(
    filtered_df[display_cols].rename(columns={
        "personnel_id": "Service ID",
        "risk_tier": "Strain Tier",
        "risk_score": "Risk Probability",
        "continuous_duty_days": "Continuous Duty (Days)",
        "leave_days_due": "Leave Due (Days)",
        "overtime_hours_last_30d": "Overtime 30d (Hrs)",
        "key_signals": "Primary Contributing Signals",
        "talking_point": "Recommended Supportive Action"
    }),
    use_container_width=True,
    hide_index=True
)

st.markdown("---")

# 6. Detailed Individual Inspector (Strictly Synced to Filtered Results)
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