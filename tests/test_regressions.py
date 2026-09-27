"""Regression tests for bugs fixed in commits 5d862d4, d724d53 and 3e12a36.

Each test was confirmed to fail with its fix temporarily reverted before
being committed.
"""

from __future__ import annotations

import pandas as pd

import dashboard
from src.formatting import money
from src.metrics import forecast_completion_date, load_milestones

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
