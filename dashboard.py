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

from src import metrics

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")

BAC = 1_200_000  # Budget at Completion
PROJECT_START = "2026-02-01"
PLANNED_FINISH = "2027-01-31"
STATUS_DATE = "2026-10-31"

# Standardized chart color system (chart chrome, status scale, categorical series, baseline)
CHART_BG = "#fcfcfb"
INK = "#10182b"
GRID = "#e1e0d9"
BASELINE = "#3a4d7a"
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"
SERIES_3 = "#1baf7a"
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_CRITICAL = "#d03b3b"


def _apply_chrome(fig, axes) -> None:
    """Apply the standardized chart chrome (background, ink, gridlines) to a figure."""
    fig.patch.set_facecolor(CHART_BG)
    if hasattr(axes, "flatten"):
        axes = axes.flatten().tolist()
    elif not isinstance(axes, (list, tuple)):
        axes = [axes]
    for ax in axes:
        ax.set_facecolor(CHART_BG)
        ax.title.set_color(INK)
        ax.xaxis.label.set_color(INK)
        ax.yaxis.label.set_color(INK)
        ax.tick_params(colors=INK)
        for spine in ax.spines.values():
            spine.set_color(INK)


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
    colors = [STATUS_GOOD if s == "Approved" else STATUS_WARNING for s in ranked["status"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(ranked["change_id"] + " - " + ranked["category"], ranked["cost_impact"], color=colors)
    ax.axvline(0, color=INK, linewidth=0.8, alpha=0.6)
    ax.set_xlabel("Cost impact ($)")
    ax.set_title("Change Register: Cost Impact by Change")
    handles = [plt.Rectangle((0, 0), 1, 1, color=STATUS_GOOD, label="Approved"),
               plt.Rectangle((0, 0), 1, 1, color=STATUS_WARNING, label="Pending")]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    ax.grid(color=GRID, linewidth=0.6, axis="x")
    _apply_chrome(fig, ax)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "change_register.png"), dpi=140, facecolor=CHART_BG)
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
        f"**Forecast completion (SPI-adjusted):** {forecast_finish.date()} "
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
            f"| {row['milestone_status']} | {row['milestone']} | {row['planned_date'].date()} "
            f"| {row['current_date'].date()} ({tag}) | {row['slip_days']:+d}d |"
        )

    lines += ["", "## Top Risks by Exposure (probability x impact)", "",
              "| Risk | Category | Exposure | Description | Overdue |",
              "|---|---|---|---|---|"]
    for _, row in risks.head(5).iterrows():
        overdue_flag = "Yes" if row["overdue"] else ""
        lines.append(
            f"| {row['risk_id']} | {row['category']} | {row['exposure']} "
            f"| {row['description']} | {overdue_flag} |"
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
            f"| {row['schedule_impact_days']:+d}d | {row['category']} | {row['status']} "
            f"| {row['description']} |"
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
            label="Planned Value (PV)", color=SERIES_1, linewidth=2)
    actuals = metrics.actuals_only(ts)
    ax.plot(actuals["period_label"].to_numpy(), actuals["earned_value_cum"].to_numpy(),
            label="Earned Value (EV)", color=SERIES_2, linewidth=2, marker="o", markersize=4)
    ax.plot(actuals["period_label"].to_numpy(), actuals["actual_cost_cum"].to_numpy(),
            label="Actual Cost (AC)", color=SERIES_3, linewidth=2, marker="o", markersize=4)
    ax.scatter([forecast_finish], [BAC], color=SERIES_3, marker="x", s=80,
               label=f"Forecast completion cost (EAC {money(summary['eac'])})", zorder=5)
    ax.set_title("Cost & Schedule Performance (S-Curve)")
    ax.set_ylabel("Cumulative value ($)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x/1000:.0f}k"))
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(color=GRID, linewidth=0.6)
    _apply_chrome(fig, ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "s_curve.png"), dpi=140, facecolor=CHART_BG)
    plt.close(fig)


def chart_spi_cpi_trend(ts) -> None:
    scored = metrics.add_performance_indices(metrics.actuals_only(ts))
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(scored["period_label"].to_numpy(), scored["spi"].to_numpy(), label="SPI",
            color=SERIES_1, linewidth=2, marker="o")
    ax.plot(scored["period_label"].to_numpy(), scored["cpi"].to_numpy(), label="CPI",
            color=SERIES_2, linewidth=2, marker="o")
    ax.axhline(1.0, color=BASELINE, linestyle="--", linewidth=1)
    ax.set_title("SPI / CPI Trend")
    ax.set_ylabel("Index (1.0 = on plan)")
    ax.legend(fontsize=8)
    ax.grid(color=GRID, linewidth=0.6)
    _apply_chrome(fig, ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "spi_cpi_trend.png"), dpi=140, facecolor=CHART_BG)
    plt.close(fig)


def chart_milestones(milestones) -> None:
    colors = {"On Track": STATUS_GOOD, "At Risk": STATUS_WARNING, "Delayed": STATUS_CRITICAL}
    fig, ax = plt.subplots(figsize=(9, 5))
    y = range(len(milestones))
    for i, row in milestones.iterrows():
        xs = pd.to_datetime([row["planned_date"], row["current_date"]]).to_numpy()
        ax.plot(xs, [i, i], color=colors[row["milestone_status"]], linewidth=3,
                solid_capstyle="round")
        ax.scatter(row["planned_date"], i, color=INK, marker="|", s=100, zorder=3)
    ax.set_yticks(list(y))
    ax.set_yticklabels(milestones["milestone"], fontsize=8)
    ax.invert_yaxis()
    ax.set_title("Milestones: Planned vs Actual/Forecast (ink tick = planned date)")
    handles = [plt.Line2D([0], [0], color=c, linewidth=3, label=s) for s, c in colors.items()]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    ax.grid(color=GRID, linewidth=0.6, axis="x")
    _apply_chrome(fig, ax)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "milestones.png"), dpi=140, facecolor=CHART_BG)
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
               s=(open_risks["exposure"] * 60).to_numpy(), color=STATUS_WARNING, alpha=0.7,
               edgecolor="white", label="Open / Mitigating")
    ax.scatter(closed_risks["plot_probability"].to_numpy(), closed_risks["plot_impact"].to_numpy(),
               s=(closed_risks["exposure"] * 60).to_numpy(), color=STATUS_GOOD, alpha=0.5,
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
    ax.grid(color=GRID, linewidth=0.6)
    _apply_chrome(fig, ax)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "risk_matrix.png"), dpi=140, facecolor=CHART_BG)
    plt.close(fig)


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)

    ts = metrics.load_timeseries(os.path.join(DATA_DIR, "cost_schedule_timeseries.csv"))
    milestones = metrics.load_milestones(os.path.join(DATA_DIR, "milestones.csv"))
    risks = metrics.load_risk_register(os.path.join(DATA_DIR, "risk_register.csv"), STATUS_DATE)
    changes = metrics.load_change_register(os.path.join(DATA_DIR, "change_register.csv"))

    summary = metrics.project_summary(ts, BAC)
    forecast_finish = metrics.forecast_completion_date(
        milestones, summary["spi"], PROJECT_START, PLANNED_FINISH
    )
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
