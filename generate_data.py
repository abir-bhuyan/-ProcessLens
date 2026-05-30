"""
ProcessLens - synthetic data generator.

Creates a realistic order-to-cash dataset for a fictional facilities-services
company ("Brightway Facilities Services"). Each row is one job moving through:
    lead -> quoted -> scheduled -> completed -> invoiced -> paid

The data is intentionally messy (rework loops, delays, drop-offs) so the
analysis has something real to find. No real company data is used.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
DATA_DIR = Path(__file__).parent / "data"
N_JOBS = 1200
SERVICE_TYPES = ["Office Clean", "Carpet Clean", "Window Clean", "Strip & Seal", "Builders Clean"]
REGIONS = ["North", "South", "East", "CBD"]


def _business_hours(delta_days: float) -> float:
    """Round a duration in days to 2 dp (kept simple for portfolio use)."""
    return round(float(delta_days), 2)


def generate() -> pd.DataFrame:
    start = pd.Timestamp("2023-01-02")
    rows = []
    for i in range(N_JOBS):
        service = RNG.choice(SERVICE_TYPES, p=[0.40, 0.20, 0.20, 0.10, 0.10])
        region = RNG.choice(REGIONS)
        lead_dt = start + pd.Timedelta(days=int(RNG.integers(0, 540))) \
            + pd.Timedelta(hours=int(RNG.integers(0, 24)))

        # Stage durations (days). Quoting is the suspected bottleneck.
        t_quote = RNG.gamma(2.0, 1.6)               # lead -> quoted
        quoted_dt = lead_dt + pd.Timedelta(days=t_quote)

        # ~22% of leads never convert past quote (lost / no decision).
        converted = RNG.random() > 0.22
        if not converted:
            rows.append([f"JOB{i:05d}", service, region, lead_dt, quoted_dt,
                         pd.NaT, pd.NaT, pd.NaT, pd.NaT, 0, "lost"])
            continue

        t_sched = RNG.gamma(1.5, 0.9)               # quoted -> scheduled
        scheduled_dt = quoted_dt + pd.Timedelta(days=t_sched)

        t_complete = RNG.gamma(1.2, 1.1)            # scheduled -> completed
        completed_dt = scheduled_dt + pd.Timedelta(days=t_complete)

        # Rework: job redone because of a quality issue (adds delay + cost).
        rework = 1 if RNG.random() < 0.11 else 0
        if rework:
            completed_dt = completed_dt + pd.Timedelta(days=RNG.gamma(2.0, 1.0))

        t_invoice = RNG.gamma(3.0, 1.4)             # completed -> invoiced (admin lag)
        invoiced_dt = completed_dt + pd.Timedelta(days=t_invoice)

        # Payment delay; larger jobs pay slower.
        base_pay = RNG.gamma(4.0, 4.0)
        invoiced_dt_pay = invoiced_dt + pd.Timedelta(days=base_pay)
        paid = RNG.random() > 0.06                  # ~6% still unpaid
        paid_dt = invoiced_dt_pay if paid else pd.NaT

        rows.append([f"JOB{i:05d}", service, region, lead_dt, quoted_dt,
                     scheduled_dt, completed_dt, invoiced_dt, paid_dt, rework,
                     "paid" if paid else "invoiced"])

    df = pd.DataFrame(rows, columns=[
        "job_id", "service_type", "region", "lead_dt", "quoted_dt",
        "scheduled_dt", "completed_dt", "invoiced_dt", "paid_dt",
        "rework_flag", "status"])
    return df


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    df = generate()
    df.to_csv(DATA_DIR / "jobs.csv", index=False)

    # Also save to SQLite so the repo demonstrates SQL skills.
    con = sqlite3.connect(DATA_DIR / "processlens.db")
    df.to_sql("jobs", con, if_exists="replace", index=False)
    con.close()

    print(f"Wrote {len(df)} jobs to data/jobs.csv and data/processlens.db")


if __name__ == "__main__":
    main()
