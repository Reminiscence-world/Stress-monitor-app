# Stress-monitor-app 
# Personnel Welfare Support & Operational Strain Decision-Support System

A transparent, non-clinical welfare decision-support system built for operational defense environments. The platform synthesizes administrative duty records, rest indicators, and voluntary self-reported wellness checks to surface early indicators of operational strain—enabling commanders and welfare officers to intervene supportively before burnout occurs.

---

## Core Ethics & Operational Guardrails

* **Strictly Non-Clinical & Non-Diagnostic:** This software does not diagnose medical or psychiatric conditions. It evaluates operational strain indicators (continuous duty, overtime, rest cycles) to provide administrative discussion points.
* **Anti-Disciplinary Policy:** System outputs are strictly restricted to supportive welfare check-ins, leave adjustments, and roster rebalancing. They are prohibited by design from being used in performance ratings, disciplinary proceedings, or fitness-for-duty medical boards[cite: 1].
* **Voluntary Participation & Privacy Isolation:** Self-assessments are strictly voluntary, pseudonymized (`CRP-XXXX`), and stored in an isolated table[cite: 1]. Missing assessments are handled neutrally and never penalized by the inference engine[cite: 1].
* **Audited Administrative Access:** Officer roster inspections, individual case drilldowns, and data exports are logged to an internal audit table (`audit_logs`) to prevent unauthorized surveillance.

---

## System Architecture

```text
[ Data Ingestion ]
  * generate_synthetic_data.py  -> Generates realistic administrative HR & rest logs
  * app_personnel_checkin.py    -> Voluntary mobile check-in app with session locking
  * init_db.py                  -> SQLite relational store (personnel_welfare.db)

[ Inference & Logic Pipeline ]
  * feature_engineering.py      -> Left-join, imputation, and categorical encoding
  * train_model.py              -> Interpretable Logistic Regression training
  * risk_engine.py              -> Probability bucketing & Multi-Factor Dossier generation

[ Supervisory Presentation Layer ]
  * app_officer_dashboard.py    -> Triage roster, synchronized drilldown, and audit logging

  Model Explainability & Transparency
Rather than deploying black-box neural networks, the platform uses a standardized Logistic Regression classifier. Every predicted score can be directly explained by verifiable weights:

Primary Strain Drivers: Consecutive duty days, accumulated overtime hours, leave entitlement arrears, and station transfer frequency.

Mitigating Factors: Regular sleep duration bands, home station postings, and positive self-reported morale.

Flagged records generate a Multi-Factor Welfare Dossier highlighting factual triggers and practical administrative talking points.

Setup & Running Instructions
1. Prerequisites & Environment Setup
(For new environments or external evaluators cloning the project. If you have already installed these packages locally, you can proceed directly to Step 2.)

git clone [https://github.com/Reminiscence-world/Stress-monitor-app.git](https://github.com/Reminiscence-world/Stress-monitor-app.git)
cd Stress-monitor-app
pip install streamlit pandas numpy scikit-learn joblib   (in bash)

2. Initialize Database & Model Pipeline
Run these commands in order to populate the SQLite store and serialize the model artifacts:
python generate_synthetic_data.py
python init_db.py
python train_model.py    (in bash)

3. Launch the Applications
Personnel Self-Check-in (Mobile View):
streamlit run app_personnel_checkin.py --server.port 8501   (in bash)
Accessible in browser at: http://localhost:8501

Welfare Officer Dashboard:
streamlit run app_officer_dashboard.py --server.port 8502 
Accessible in browser at: http://localhost:8502

Regulatory Notice
This repository utilizes synthetic demonstrator data for evaluation purposes. The platform operates strictly as an administrative decision-support system and must always remain under human-in-the-loop supervisory oversight.

---

### Push to GitHub

Once saved, stage, commit, and push it in PowerShell:

```powershell
git add README.md
git commit -m "docs: complete ticket 10 - comprehensive system architecture and ethics guardrails"
git push origin main
