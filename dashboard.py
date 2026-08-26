"""
Project Controls Dashboard
---------------------------
Reads a fictional infrastructure project's cost/schedule timeseries, milestone
log, and risk register, computes standard project controls metrics (EVM,
milestone slippage, risk exposure), prints a status report, and saves charts.

Run:
    pip install -r requirements.txt
    python dashboard.py
"""

import math
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from src import metrics

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

BAC = 1_200_000  # Budget at Completion
PROJECT_START = "2026-02-01"
PLANNED_FINISH = "2027-01-31"
STATUS_DATE = "2026-10-31"


def money(x: float) -> str:
    return f"${x:,.0f}"


def print_summary(summary: dict, forecast_finish) -> None:
    print("=" * 60)
    print(f"PROJECT STATUS REPORT — as of {summary['status_period']}")
    print("=" * 60)
    print(f"Percent complete (earned):  {summary['percent_complete']:.1f}%")
    print()
    print(f"Planned Value (PV):         {money(summary['pv'])}")
    print(f"Earned Value (EV):          {money(summary['ev'])}")
    print(f"Actual Cost (AC):           {money(summary['ac'])}")
    print()
    print(f"Schedule Variance (SV):     {money(summary['sv'])}  ({summary['sv_pct']:+.1f}%)")
    print(f"Cost Variance (CV):         {money(summary['cv'])}  ({summary['cv_pct']:+.1f}%)")
    print(f"SPI (schedule performance): {summary['spi']:.2f}")
    print(f"CPI (cost performance):     {summary['cpi']:.2f}")
    print()
    print(f"Estimate at Completion (EAC):  {money(summary['eac'])}")
    print(f"Estimate to Complete (ETC):    {money(summary['etc'])}")
    print(f"Variance at Completion (VAC):  {money(summary['vac'])}  "
          f"({'over' if summary['vac'] < 0 else 'under'} budget)")
    print(f"To-Complete Perf. Index (TCPI): {summary['tcpi']:.2f}")
    print()
    print(f"Forecast completion (SPI-adjusted): {forecast_finish.date()} "
          f"(planned: {PLANNED_FINISH})")


def print_milestones(milestones) -> None:
    print()
    print("-" * 60)
    print("MILESTONES")
    print("-" * 60)
    for _, row in milestones.iterrows():
        tag = "actual" if row["date_type"] == "Actual" else "forecast"
        print(f"[{row['milestone_status']:>8}] {row['milestone']:<34} "
              f"planned {row['planned_date'].date()}  {tag} {row['current_date'].date()} "
              f"({row['slip_days']:+d}d)")


def print_risks(risks) -> None:
    print()
    print("-" * 60)
    print("TOP RISKS BY EXPOSURE (probability x impact)")
    print("-" * 60)
    for _, row in risks.head(5).iterrows():
        overdue_flag = "  [MITIGATION OVERDUE]" if row["overdue"] else ""
        print(f"{row['risk_id']}  exposure={row['exposure']:>2}  "
              f"({row['category']})  {row['description']}{overdue_flag}")

    overdue_count = int(risks["overdue"].sum())
    open_count = int((risks["status"] != "Closed").sum())
    print()
    print(f"Open risks: {open_count}   Overdue mitigations: {overdue_count}")


def chart_s_curve(ts, summary, forecast_finish) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(ts["period_label"].to_numpy(), ts["planned_value_cum"].to_numpy(),
            label="Planned Value (PV)", color="#4C72B0", linewidth=2)
    actuals = metrics.actuals_only(ts)
    ax.plot(actuals["period_label"].to_numpy(), actuals["earned_value_cum"].to_numpy(),
            label="Earned Value (EV)", color="#55A868", linewidth=2, marker="o", markersize=4)
    ax.plot(actuals["period_label"].to_numpy(), actuals["actual_cost_cum"].to_numpy(),
            label="Actual Cost (AC)", color="#C44E52", linewidth=2, marker="o", markersize=4)
    ax.scatter([forecast_finish], [BAC], color="#C44E52", marker="x", s=80,
               label=f"Forecast completion cost (EAC {money(summary['eac'])})", zorder=5)
    ax.set_title("Cost & Schedule Performance (S-Curve)")
    ax.set_ylabel("Cumulative value ($)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x/1000:.0f}k"))
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "s_curve.png"), dpi=140)
    plt.close(fig)


def chart_spi_cpi_trend(ts) -> None:
    scored = metrics.add_performance_indices(metrics.actuals_only(ts))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(scored["period_label"].to_numpy(), scored["spi"].to_numpy(), label="SPI",
            color="#4C72B0", linewidth=2, marker="o")
    ax.plot(scored["period_label"].to_numpy(), scored["cpi"].to_numpy(), label="CPI",
            color="#DD8452", linewidth=2, marker="o")
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax.set_title("SPI / CPI Trend")
    ax.set_ylabel("Index (1.0 = on plan)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "spi_cpi_trend.png"), dpi=140)
    plt.close(fig)


def chart_milestones(milestones) -> None:
    colors = {"On Track": "#55A868", "At Risk": "#DD8452", "Delayed": "#C44E52"}
    fig, ax = plt.subplots(figsize=(9, 5))
    y = range(len(milestones))
    for i, row in milestones.iterrows():
        xs = pd.to_datetime([row["planned_date"], row["current_date"]]).to_numpy()
        ax.plot(xs, [i, i], color=colors[row["milestone_status"]], linewidth=3,
                solid_capstyle="round")
        ax.scatter(row["planned_date"], i, color="black", marker="|", s=100, zorder=3)
    ax.set_yticks(list(y))
    ax.set_yticklabels(milestones["milestone"], fontsize=8)
    ax.invert_yaxis()
    ax.set_title("Milestones: Planned vs Actual/Forecast (black tick = planned date)")
    handles = [plt.Line2D([0], [0], color=c, linewidth=3, label=s) for s, c in colors.items()]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    ax.grid(alpha=0.3, axis="x")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "milestones.png"), dpi=140)
    plt.close(fig)


def _spread_overlapping_points(risks):
    """Nudge risks that share the same (probability, impact) cell so labels don't overlap."""
    risks = risks.copy()
    risks["plot_probability"] = risks["probability"].astype(float)
    risks["plot_impact"] = risks["impact"].astype(float)
    for _, idx in risks.groupby(["probability", "impact"]).groups.items():
        idx = list(idx)
        if len(idx) <= 1:
            continue
        for j, i in enumerate(idx):
            angle = 2 * math.pi * j / len(idx)
            risks.loc[i, "plot_probability"] += 0.22 * math.cos(angle)
            risks.loc[i, "plot_impact"] += 0.22 * math.sin(angle)
    return risks


def chart_risk_matrix(risks) -> None:
    risks = _spread_overlapping_points(risks)
    fig, ax = plt.subplots(figsize=(6.5, 6))
    open_risks = risks[risks["status"] != "Closed"]
    closed_risks = risks[risks["status"] == "Closed"]
    ax.scatter(open_risks["plot_probability"].to_numpy(), open_risks["plot_impact"].to_numpy(),
               s=(open_risks["exposure"] * 60).to_numpy(), color="#C44E52", alpha=0.7,
               edgecolor="white", label="Open / Mitigating")
    ax.scatter(closed_risks["plot_probability"].to_numpy(), closed_risks["plot_impact"].to_numpy(),
               s=(closed_risks["exposure"] * 60).to_numpy(), color="#8C8C8C", alpha=0.5,
               edgecolor="white", label="Closed")
    for _, row in risks.iterrows():
        ax.annotate(row["risk_id"], (row["plot_probability"], row["plot_impact"]),
                    fontsize=7, ha="center", va="center", color="white", weight="bold")
    ax.set_xlim(0.5, 5.5)
    ax.set_ylim(0.5, 5.5)
    ax.set_xlabel("Probability (1-5)")
    ax.set_ylabel("Impact (1-5)")
    ax.set_title("Risk Matrix (bubble size = exposure)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "risk_matrix.png"), dpi=140)
    plt.close(fig)


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)

    ts = metrics.load_timeseries(os.path.join(DATA_DIR, "cost_schedule_timeseries.csv"))
    milestones = metrics.load_milestones(os.path.join(DATA_DIR, "milestones.csv"))
    risks = metrics.load_risk_register(os.path.join(DATA_DIR, "risk_register.csv"), STATUS_DATE)

    summary = metrics.project_summary(ts, BAC)
    forecast_finish = metrics.forecast_completion_date(
        milestones, summary["spi"], PROJECT_START, PLANNED_FINISH
    )

    print_summary(summary, forecast_finish)
    print_milestones(milestones)
    print_risks(risks)

    chart_s_curve(ts, summary, forecast_finish)
    chart_spi_cpi_trend(ts)
    chart_milestones(milestones)
    chart_risk_matrix(risks)

    print()
    print("-" * 60)
    print(f"Charts saved to {ASSETS_DIR}")


if __name__ == "__main__":
    main()
