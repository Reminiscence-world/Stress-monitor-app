import numpy as np
import pandas as pd

def generate_welfare_dataset(num_samples: int = 500, random_seed: int = 42) -> pd.DataFrame:
    """
    Ticket 1: Synthetic Dataset Generator for Problem Statement 186.
    Generates synthetic administrative, voluntary self-report, and bucketed 
    biometric wellness records with a transparent, rule-constructed ground-truth label.
    """
    np.random.seed(random_seed)

    records = []
    
    for i in range(1, num_samples + 1):
        # 1. Pseudonymous Identifier (Section 4 & 12)
        personnel_id = f"CRP-{1000 + i}"
        
        # 2. Deployment Context (Home-station, Field, High-stress) (Section 4)
        deployment_type = np.random.choice(
            ["home_station", "field", "high_stress"], 
            p=[0.35, 0.40, 0.25]
        )
        
        # 3. Administrative HR Indicators (Section 4)
        if deployment_type == "home_station":
            continuous_duty_days = int(np.clip(np.random.exponential(scale=10), 1, 45))
            leave_days_taken = int(np.clip(np.random.normal(12, 4), 0, 30))
            leave_days_due = int(np.clip(np.random.normal(10, 5), 0, 45))
            transfers_last_2yrs = int(np.random.choice([0, 1, 2], p=[0.7, 0.25, 0.05]))
            overtime_hours = int(np.clip(np.random.normal(15, 8), 0, 60))
        elif deployment_type == "field":
            continuous_duty_days = int(np.clip(np.random.exponential(scale=25), 5, 75))
            leave_days_taken = int(np.clip(np.random.normal(6, 3), 0, 20))
            leave_days_due = int(np.clip(np.random.normal(20, 8), 5, 60))
            transfers_last_2yrs = int(np.random.choice([0, 1, 2, 3], p=[0.4, 0.4, 0.15, 0.05]))
            overtime_hours = int(np.clip(np.random.normal(35, 12), 10, 90))
        else:  # high_stress posting
            continuous_duty_days = int(np.clip(np.random.exponential(scale=40), 14, 120))
            leave_days_taken = int(np.clip(np.random.normal(3, 2), 0, 15))
            leave_days_due = int(np.clip(np.random.normal(32, 10), 10, 75))
            transfers_last_2yrs = int(np.random.choice([1, 2, 3, 4], p=[0.3, 0.4, 0.2, 0.1]))
            overtime_hours = int(np.clip(np.random.normal(55, 15), 20, 120))

        # 4. Optional Voluntary Self-Assessment Score (Section 5)
        # Opt-in probability: 70%. Score range: 5 to 25 (higher = better morale/energy)
        opted_in = np.random.rand() < 0.70
        if opted_in:
            # Degrades under prolonged duty and excessive overtime
            base_self_score = 25 - (continuous_duty_days * 0.1) - (overtime_hours * 0.08)
            self_assessment_score = int(np.clip(np.random.normal(base_self_score, 3), 5, 25))
        else:
            self_assessment_score = -1  # Sentinel value for non-submission

        # 5. Optional Authorized Biometric Summaries (Section 5)
        # Pre-aggregated buckets, not raw streams
        if continuous_duty_days > 45 or overtime_hours > 60:
            sleep_hours_band = np.random.choice(["<5h", "5-7h", ">7h"], p=[0.55, 0.35, 0.10])
            resting_hr_band = np.random.choice(["normal", "elevated", "high"], p=[0.20, 0.50, 0.30])
        else:
            sleep_hours_band = np.random.choice(["<5h", "5-7h", ">7h"], p=[0.15, 0.60, 0.25])
            resting_hr_band = np.random.choice(["normal", "elevated", "high"], p=[0.70, 0.25, 0.05])

        # 6. Documented Ground-Truth Risk Label Construction (Section 6)
        # Normalized weighted linear combination
        w_duty = min(continuous_duty_days / 60.0, 1.5) * 0.30
        w_overtime = min(overtime_hours / 80.0, 1.5) * 0.20
        w_leave = min(leave_days_due / 45.0, 1.5) * 0.15
        w_transfers = min(transfers_last_2yrs / 3.0, 1.5) * 0.10
        w_deployment = 0.15 if deployment_type == "high_stress" else (0.08 if deployment_type == "field" else 0.0)
        
        # Biometric contribution
        w_bio = 0.0
        if sleep_hours_band == "<5h":
            w_bio += 0.05
        if resting_hr_band in ["elevated", "high"]:
            w_bio += 0.05

        # Self-assessment offset (if submitted)
        w_survey = 0.0
        if self_assessment_score != -1:
            # Low scores (5-12) add risk; high scores (18-25) reduce risk
            w_survey = ((15.0 - self_assessment_score) / 10.0) * 0.10

        composite_risk_score = w_duty + w_overtime + w_leave + w_transfers + w_deployment + w_bio + w_survey
        composite_risk_score += np.random.normal(0, 0.03)  # Add minor natural variance

        # Binary label cutoff: 0.55 threshold
        elevated_welfare_risk = 1 if composite_risk_score >= 0.55 else 0

        records.append({
            "personnel_id": personnel_id,
            "deployment_type": deployment_type,
            "continuous_duty_days": continuous_duty_days,
            "leave_days_taken_last_90d": leave_days_taken,
            "leave_days_due": leave_days_due,
            "transfers_last_2yrs": transfers_last_2yrs,
            "overtime_hours_last_30d": overtime_hours,
            "self_assessment_score": self_assessment_score,
            "sleep_hours_band": sleep_hours_band,
            "resting_hr_band": resting_hr_band,
            "ground_truth_composite_score": round(float(composite_risk_score), 3),
            "elevated_welfare_risk": elevated_welfare_risk
        })

    return pd.DataFrame(records)

if __name__ == "__main__":
    df = generate_welfare_dataset(num_samples=500, random_seed=42)
    output_filename = "synthetic_personnel_welfare_data.csv"
    df.to_csv(output_filename, index=False)
    
    print(f"Generated {len(df)} records -> Saved to {output_filename}")
    print(f"Elevated Risk Distribution:\n{df['elevated_welfare_risk'].value_counts(normalize=True)}")