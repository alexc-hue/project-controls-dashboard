"""Tests for the EVM/forecast calculation functions in src/metrics.py.

Uses small hand-built DataFrames rather than the repo's sample CSVs, so these
stay fast and independent of any future sample-data changes.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.metrics import add_performance_indices, forecast_completion_date, project_summary


def _timeseries(pv, ev, ac):
    """One-period timeseries frame with the given cumulative PV/EV/AC."""
    return pd.DataFrame({
        "period": [1],
        "period_label": [pd.Timestamp("2026-01-01")],
        "planned_value_cum": [pv],
        "earned_value_cum": [ev],
        "actual_cost_cum": [ac],
    })


def test_add_performance_indices_basic():
    df = _timeseries(pv=100.0, ev=90.0, ac=120.0)
    out = add_performance_indices(df)
    assert out.loc[0, "sv"] == pytest.approx(-10.0)
    assert out.loc[0, "cv"] == pytest.approx(-30.0)
    assert out.loc[0, "spi"] == pytest.approx(0.9)
    assert out.loc[0, "cpi"] == pytest.approx(0.75)


def test_add_performance_indices_zero_denominator_guard():
    """A zero planned/actual value must yield NaN, not inf/-inf."""
    df = _timeseries(pv=0.0, ev=90.0, ac=0.0)
    out = add_performance_indices(df)
    assert math.isnan(out.loc[0, "spi"])
    assert math.isnan(out.loc[0, "cpi"])


def test_project_summary_basic_evm_figures():
    df = _timeseries(pv=1000.0, ev=900.0, ac=1200.0)
    summary = project_summary(df, bac=10_000.0)

    assert summary["spi"] == pytest.approx(0.9)
    assert summary["cpi"] == pytest.approx(0.75)
    assert summary["eac"] == pytest.approx(10_000.0 / 0.75)
    assert summary["vac"] == pytest.approx(10_000.0 - 10_000.0 / 0.75)
    assert summary["sv"] == pytest.approx(-100.0)
    assert summary["cv"] == pytest.approx(-300.0)
    assert summary["percent_complete"] == pytest.approx(9.0)


def test_project_summary_sv_pct_cv_pct_zero_guard():
    """sv_pct divides by pv, cv_pct divides by ev: both zero cases must report
    NaN rather than raising or silently producing inf."""
    zero_pv = _timeseries(pv=0.0, ev=100.0, ac=50.0)
    summary_zero_pv = project_summary(zero_pv, bac=1000.0)
    assert math.isnan(summary_zero_pv["sv_pct"])

    # ac=0.0 too (not just ev), so cpi itself is NaN-guarded rather than a
    # literal 0 -- avoids a spurious "divide by zero" warning from the
    # unrelated eac = bac / cpi computation later in the same summary.
    zero_ev = _timeseries(pv=100.0, ev=0.0, ac=0.0)
    summary_zero_ev = project_summary(zero_ev, bac=1000.0)
    assert math.isnan(summary_zero_ev["cv_pct"])


def test_project_summary_raises_on_no_actuals():
    """No period with both EV and AC populated should raise, not silently
    compute against an empty frame."""
    df = pd.DataFrame({
        "period": [1],
        "period_label": [pd.Timestamp("2026-01-01")],
        "planned_value_cum": [1000.0],
        "earned_value_cum": [None],
        "actual_cost_cum": [None],
    })
    with pytest.raises(ValueError):
        project_summary(df, bac=10_000.0)


def test_forecast_completion_date_normal():
    forecast = forecast_completion_date(
        spi=0.5, project_start="2026-01-01", planned_finish="2026-01-11"
    )
    # 10 planned days stretched by 1/0.5 = 20 days from project_start.
    assert forecast == pd.Timestamp("2026-01-21")


@pytest.mark.parametrize("bad_spi", [None, 0, -0.5, float("nan")])
def test_forecast_completion_date_none_on_invalid_spi(bad_spi):
    assert forecast_completion_date(
        spi=bad_spi, project_start="2026-01-01", planned_finish="2026-01-11"
    ) is None
