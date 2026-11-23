"""Regression tests for bugs fixed in commits 5d862d4, d724d53 and 3e12a36, and in 1.2.2.

Each test was confirmed to fail with its fix temporarily reverted before
being committed.
"""

from __future__ import annotations

import pandas as pd

import dashboard
from src.formatting import money
from src.metrics import (
    change_impact_summary,
    forecast_completion_date,
    load_change_register,
    load_milestones,
    load_risk_register,
)

# --- 5d862d4 -----------------------------------------------------------------

def test_negative_money_puts_the_sign_before_the_symbol():
    assert money(-120000) == "-$120,000"
    assert money(120000) == "$120,000"


# --- d724d53 -----------------------------------------------------------------

def test_forecast_rounds_to_the_nearest_day():
    """10 planned days at SPI 0.6 stretch to 16.67 days. The forecast has to
    land on day 17, not carry a fractional day that later floors to 16."""
    forecast = forecast_completion_date(
        spi=0.6, project_start="2026-01-01", planned_finish="2026-01-11"
    )
    assert forecast == pd.Timestamp("2026-01-18")


# --- 3e12a36 -----------------------------------------------------------------

def test_milestone_with_missing_date_is_flagged_not_called_delayed(tmp_path):
    csv = tmp_path / "milestones.csv"
    csv.write_text(
        "milestone,planned_date,current_date,date_type,status\n"
        "Has dates,2026-03-01,2026-03-05,Actual,Complete\n"
        "No current date,2026-04-01,,Forecast,Open\n",
        encoding="utf-8",
    )
    statuses = load_milestones(str(csv)).set_index("milestone")["milestone_status"]
    assert statuses["Has dates"] == "At Risk"
    assert statuses["No current date"] == "Date Missing"


def test_free_text_cannot_break_the_markdown_table():
    assert dashboard._escape_md_cell("a|b\nc") == r"a\|b c"
    assert dashboard._escape_md_cell(None) == ""


# --- 1.2.2 -------------------------------------------------------------------

def test_risk_status_matching_ignores_case_and_whitespace(tmp_path):
    """A " closed" or "CLOSED" risk used to count as open and could be flagged overdue."""
    csv = tmp_path / "risks.csv"
    csv.write_text(
        "risk_id,description,category,probability,impact,status,mitigation_owner,mitigation_due_date\n"
        "R1,a,Tech,3,3, closed ,PM,2026-01-01\n"
        "R2,b,Tech,2,2,CLOSED,PM,2026-01-01\n"
        "R3,c,Tech,1,1,open,PM,2026-01-01\n",
        encoding="utf-8",
    )
    risks = load_risk_register(str(csv), "2026-06-01").set_index("risk_id")
    assert list(risks.loc[["R1", "R2", "R3"], "status"]) == ["Closed", "Closed", "Open"]
    assert list(risks.loc[["R1", "R2", "R3"], "overdue"]) == [False, False, True]


def test_change_status_matching_ignores_case_and_whitespace(tmp_path):
    csv = tmp_path / "changes.csv"
    csv.write_text(
        "change_id,description,category,cost_impact,schedule_impact_days,status,date_raised\n"
        "C1,a,Scope,100,1,approved,2026-01-01\n"
        "C2,b,Scope,200,2, Pending ,2026-01-02\n",
        encoding="utf-8",
    )
    changes = load_change_register(str(csv))
    assert sorted(changes["status"]) == ["Approved", "Pending"]

    raw = pd.DataFrame({"status": ["approved", " Pending "], "cost_impact": [100, 200],
                        "schedule_impact_days": [1, 2]})
    summary = change_impact_summary(raw, bac=1000)
    assert summary["approved_cost_impact"] == 100
    assert summary["pending_count"] == 1


def test_money_does_not_print_minus_zero():
    assert money(-0.4) == "$0"
    assert money(-0.6) == "-$1"
