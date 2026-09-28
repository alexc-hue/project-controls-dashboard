"""Per-item charts cap themselves at CHART_TOP_N items; the reports don't."""

from __future__ import annotations

import pandas as pd

import dashboard


def test_change_chart_keeps_the_largest_changes_either_way():
    changes = pd.DataFrame({"change_id": [f"C{i}" for i in range(100)],
                            "cost_impact": [(-1) ** i * i * 1000 for i in range(100)]})
    shown = dashboard._largest_changes(changes)
    assert len(shown) == dashboard.CHART_TOP_N
    assert set(shown["cost_impact"].abs()) == {i * 1000 for i in range(70, 100)}


def test_risk_matrix_labels_the_highest_exposure():
    risks = pd.DataFrame({"risk_id": [f"R{i}" for i in range(80)], "exposure": list(range(80))})
    labelled = dashboard._labelled_risks(risks)
    assert set(labelled["exposure"]) == set(range(50, 80))


def test_small_registers_are_charted_in_full():
    small = pd.DataFrame({"cost_impact": [1, -2], "exposure": [3, 4]})
    assert dashboard._largest_changes(small).equals(small)
    assert dashboard._labelled_risks(small).equals(small)


def test_milestone_chart_keeps_the_most_slipped_in_order():
    milestones = pd.DataFrame({"milestone": [f"M{i}" for i in range(60)],
                               "slip_days": [float(i) if i % 7 else float("nan") for i in range(60)]})
    shown = dashboard._charted_milestones(milestones)
    assert len(shown) == dashboard.CHART_TOP_N
    assert shown["slip_days"].notna().all()
    assert list(shown.index) == sorted(shown.index)
