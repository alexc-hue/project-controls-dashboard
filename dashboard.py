"""
Project Controls Dashboard
---------------------------
Reads a fictional infrastructure project's cost/schedule timeseries, milestone
log, risk register, and change register, computes standard project controls
metrics (EVM, milestone slippage, risk exposure, change impact), prints a
status report, and saves charts.

Run:
    pip install -r requirements.txt
    python dashboard.py
"""

import math
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from src import chart_style, metrics
from src.formatting import money

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

# Edit these to match your own project -- see README ("point this at your
# own data"). They aren't read from the CSVs: BAC/PROJECT_START/
# PLANNED_FINISH/STATUS_DATE are this fictional project's assumptions, and
# swapping in your own CSVs without also updating these will compute a real
# schedule/cost against the wrong budget, dates, and status cutoff.
BAC = 1_200_000  # Budget at Completion
PROJECT_START = "2026-02-01"
PLANNED_FINISH = "2027-01-31"
STATUS_DATE = "2026-10-31"


def _forecast_str(forecast_finish) -> str:
    return forecast_finish.date().isoformat() if forecast_finish is not None else "not yet forecastable"


def _slip_str(slip_days) -> str:
    """Format a milestone's slip in days, or 'n/a' if the date data was incomplete
    (slip_days is NaN -- see metrics.load_milestones' "Date Missing" status)."""
    return f"{int(slip_days):+d}d" if pd.notna(slip_days) else "n/a"


def _escape_md_cell(value) -> str:
    """Escape/normalize a free-text value so it can't corrupt a markdown table.

    A raw `|` splits into extra columns, a backslash can escape the delimiter
    that follows it, and embedded newlines break the row onto multiple lines.
    """
    if value is None or value != value:  # covers None and NaN (NaN != NaN)
        return ""
    text = str(value)
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


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
    print(f"Forecast completion (SPI-adjusted): {_forecast_str(forecast_finish)} "
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
              f"({_slip_str(row['slip_days'])})")


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


def print_changes(changes, change_summary: dict) -> None:
    print()
    print("-" * 60)
    print("CHANGE REGISTER")
    print("-" * 60)
    for _, row in changes.iterrows():
        print(f"{row['change_id']}  {money(row['cost_impact']):>10}  "
              f"{row['schedule_impact_days']:+3d}d  ({row['category']}, {row['status']})  "
              f"{row['description']}")
    print()
    print(f"Approved changes: {money(change_summary['approved_cost_impact'])}  "
          f"({change_summary['approved_schedule_days']:+d} days)")
    print(f"Revised budget (BAC + approved changes): {money(change_summary['revised_budget'])}")
    print(f"Pending: {change_summary['pending_count']} change(s), "
          f"{money(change_summary['pending_cost_exposure'])} exposure, "
          f"{change_summary['pending_schedule_exposure_days']:+d} days exposure")


def chart_change_register(changes) -> None:
    ranked = changes.sort_values("cost_impact")
    colors = [chart_style.STATUS_GOOD if s == "Approved" else chart_style.STATUS_WARNING for s in ranked["status"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(ranked["change_id"] + " - " + ranked["category"], ranked["cost_impact"], color=colors)
    ax.axvline(0, color=chart_style.INK, linewidth=0.8, alpha=0.6)
    ax.set_xlabel("Cost impact ($)")
    ax.set_title("Change Register: Cost Impact by Change")
    handles = [plt.Rectangle((0, 0), 1, 1, color=chart_style.STATUS_GOOD, label="Approved"),
               plt.Rectangle((0, 0), 1, 1, color=chart_style.STATUS_WARNING, label="Pending")]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    ax.grid(color=chart_style.GRID, linewidth=0.6, axis="x")
    chart_style.apply_chrome(fig, ax)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "change_register.png"), dpi=140)
    plt.close(fig)


def write_report_markdown(summary: dict, forecast_finish, milestones, risks, changes, change_summary: dict) -> None:
    lines = [
        f"# Project Status Report — as of {summary['status_period']}",
        "",
        f"**Percent complete (earned):** {summary['percent_complete']:.1f}%",
        "",
        "## Earned Value",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Planned Value (PV) | {money(summary['pv'])} |",
        f"| Earned Value (EV) | {money(summary['ev'])} |",
        f"| Actual Cost (AC) | {money(summary['ac'])} |",
        f"| Schedule Variance (SV) | {money(summary['sv'])} ({summary['sv_pct']:+.1f}%) |",
        f"| Cost Variance (CV) | {money(summary['cv'])} ({summary['cv_pct']:+.1f}%) |",
        f"| SPI | {summary['spi']:.2f} |",
        f"| CPI | {summary['cpi']:.2f} |",
        f"| Estimate at Completion (EAC) | {money(summary['eac'])} |",
        f"| Estimate to Complete (ETC) | {money(summary['etc'])} |",
        f"| Variance at Completion (VAC) | {money(summary['vac'])} "
        f"({'over' if summary['vac'] < 0 else 'under'} budget) |",
        f"| To-Complete Performance Index (TCPI) | {summary['tcpi']:.2f} |",
        "",
        f"**Forecast completion (SPI-adjusted):** {_forecast_str(forecast_finish)} "
        f"(planned: {PLANNED_FINISH})",
        "",
        "## Milestones",
        "",
        "| Status | Milestone | Planned | Actual/Forecast | Slip |",
        "|---|---|---|---|---|",
    ]
    for _, row in milestones.iterrows():
        tag = "actual" if row["date_type"] == "Actual" else "forecast"
        lines.append(
            f"| {row['milestone_status']} | {_escape_md_cell(row['milestone'])} | {row['planned_date'].date()} "
            f"| {row['current_date'].date()} ({tag}) | {_slip_str(row['slip_days'])} |"
        )

    lines += ["", "## Top Risks by Exposure (probability x impact)", "",
              "| Risk | Category | Exposure | Description | Overdue |",
              "|---|---|---|---|---|"]
    for _, row in risks.head(5).iterrows():
        overdue_flag = "Yes" if row["overdue"] else ""
        lines.append(
            f"| {row['risk_id']} | {_escape_md_cell(row['category'])} | {row['exposure']} "
            f"| {_escape_md_cell(row['description'])} | {overdue_flag} |"
        )

    overdue_count = int(risks["overdue"].sum())
    open_count = int((risks["status"] != "Closed").sum())
    lines += ["", f"**Open risks:** {open_count}   **Overdue mitigations:** {overdue_count}", ""]

    lines += ["", "## Change Register", "",
              "| Change | Cost Impact | Schedule Impact | Category | Status | Description |",
              "|---|---|---|---|---|---|"]
    for _, row in changes.iterrows():
        lines.append(
            f"| {row['change_id']} | {money(row['cost_impact'])} "
            f"| {row['schedule_impact_days']:+d}d | {_escape_md_cell(row['category'])} | {row['status']} "
            f"| {_escape_md_cell(row['description'])} |"
        )
    lines += [
        "",
        f"**Approved changes:** {money(change_summary['approved_cost_impact'])} "
        f"({change_summary['approved_schedule_days']:+d} days)  ",
        f"**Revised budget (BAC + approved changes):** {money(change_summary['revised_budget'])}  ",
        f"**Pending:** {change_summary['pending_count']} change(s), "
        f"{money(change_summary['pending_cost_exposure'])} exposure, "
        f"{change_summary['pending_schedule_exposure_days']:+d} days exposure",
        "",
    ]

    with open(os.path.join(ASSETS_DIR, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def chart_s_curve(ts, summary, forecast_finish) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(ts["period_label"].to_numpy(), ts["planned_value_cum"].to_numpy(),
            label="Planned Value (PV)", color=chart_style.SERIES_1, linewidth=2)
    actuals = metrics.actuals_only(ts)
    ax.plot(actuals["period_label"].to_numpy(), actuals["earned_value_cum"].to_numpy(),
            label="Earned Value (EV)", color=chart_style.SERIES_2, linewidth=2, marker="o", markersize=4)
    ax.plot(actuals["period_label"].to_numpy(), actuals["actual_cost_cum"].to_numpy(),
            label="Actual Cost (AC)", color=chart_style.SERIES_3, linewidth=2, marker="o", markersize=4)
    if forecast_finish is not None:
        ax.scatter([forecast_finish], [BAC], color=chart_style.SERIES_3, marker="x", s=80,
                   label=f"Forecast completion cost (EAC {money(summary['eac'])})", zorder=5)
    ax.set_title("Cost & Schedule Performance (S-Curve)")
    ax.set_ylabel("Cumulative value ($)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x/1000:.0f}k"))
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(color=chart_style.GRID, linewidth=0.6)
    chart_style.apply_chrome(fig, ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "s_curve.png"), dpi=140)
    plt.close(fig)


def chart_spi_cpi_trend(ts) -> None:
    scored = metrics.add_performance_indices(metrics.actuals_only(ts))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(scored["period_label"].to_numpy(), scored["spi"].to_numpy(), label="SPI",
            color=chart_style.SERIES_1, linewidth=2, marker="o")
    ax.plot(scored["period_label"].to_numpy(), scored["cpi"].to_numpy(), label="CPI",
            color=chart_style.SERIES_2, linewidth=2, marker="o")
    ax.axhline(1.0, color=chart_style.BASELINE, linestyle="--", linewidth=1)
    ax.set_title("SPI / CPI Trend")
    ax.set_ylabel("Index (1.0 = on plan)")
    ax.legend(fontsize=8)
    ax.grid(color=chart_style.GRID, linewidth=0.6)
    chart_style.apply_chrome(fig, ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "spi_cpi_trend.png"), dpi=140)
    plt.close(fig)


def chart_milestones(milestones) -> None:
    colors = {"On Track": chart_style.STATUS_GOOD, "At Risk": chart_style.STATUS_WARNING,
              "Delayed": chart_style.STATUS_CRITICAL}
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, row in enumerate(milestones.itertuples()):
        xs = pd.to_datetime([row.planned_date, row.current_date]).to_numpy()
        # .get() with a neutral fallback: a "Date Missing" row (see
        # metrics.load_milestones) has no entry in this 3-color status scale,
        # since it isn't a severity reading at all -- it's a data-quality gap.
        ax.plot(xs, [i, i], color=colors.get(row.milestone_status, chart_style.INK), linewidth=3,
                solid_capstyle="round")
        ax.scatter(row.planned_date, i, color=chart_style.INK, marker="|", s=100, zorder=3)
    ax.set_yticks(range(len(milestones)))
    ax.set_yticklabels(milestones["milestone"], fontsize=8)
    ax.invert_yaxis()
    ax.set_title("Milestones: Planned vs Actual/Forecast (ink tick = planned date)")
    handles = [plt.Line2D([0], [0], color=c, linewidth=3, label=s) for s, c in colors.items()]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    ax.grid(color=chart_style.GRID, linewidth=0.6, axis="x")
    chart_style.apply_chrome(fig, ax)
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
    open_mask = risks["status"] != "Closed"
    overdue_risks = risks[open_mask & risks["overdue"]]
    active_risks = risks[open_mask & ~risks["overdue"]]
    closed_risks = risks[~open_mask]
    ax.scatter(active_risks["plot_probability"].to_numpy(), active_risks["plot_impact"].to_numpy(),
               s=(active_risks["exposure"] * 60).to_numpy(), color=chart_style.STATUS_WARNING, alpha=0.7,
               edgecolor="white", label="Open / Mitigating")
    ax.scatter(overdue_risks["plot_probability"].to_numpy(), overdue_risks["plot_impact"].to_numpy(),
               s=(overdue_risks["exposure"] * 60).to_numpy(), color=chart_style.STATUS_CRITICAL, alpha=0.7,
               edgecolor="white", label="Open / Mitigation Overdue")
    ax.scatter(closed_risks["plot_probability"].to_numpy(), closed_risks["plot_impact"].to_numpy(),
               s=(closed_risks["exposure"] * 60).to_numpy(), color=chart_style.STATUS_GOOD, alpha=0.5,
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
    ax.grid(color=chart_style.GRID, linewidth=0.6)
    chart_style.apply_chrome(fig, ax)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "risk_matrix.png"), dpi=140)
    plt.close(fig)


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)

    ts = metrics.load_timeseries(os.path.join(DATA_DIR, "cost_schedule_timeseries.csv"))
    milestones = metrics.load_milestones(os.path.join(DATA_DIR, "milestones.csv"))
    risks = metrics.load_risk_register(os.path.join(DATA_DIR, "risk_register.csv"), STATUS_DATE)
    changes = metrics.load_change_register(os.path.join(DATA_DIR, "change_register.csv"))

    summary = metrics.project_summary(ts, BAC)
    forecast_finish = metrics.forecast_completion_date(summary["spi"], PROJECT_START, PLANNED_FINISH)
    change_summary = metrics.change_impact_summary(changes, BAC)

    print_summary(summary, forecast_finish)
    print_milestones(milestones)
    print_risks(risks)
    print_changes(changes, change_summary)

    chart_s_curve(ts, summary, forecast_finish)
    chart_spi_cpi_trend(ts)
    chart_milestones(milestones)
    chart_risk_matrix(risks)
    chart_change_register(changes)
    write_report_markdown(summary, forecast_finish, milestones, risks, changes, change_summary)

    print()
    print("-" * 60)
    print(f"Charts and report.md saved to {ASSETS_DIR}")


if __name__ == "__main__":
    main()
