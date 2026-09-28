"""_spread_overlapping_points was rewritten in 1.2.0 to work in one pass.
The plotted positions have to be exactly what the previous loop produced."""

from __future__ import annotations

import math
import random

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from dashboard import _spread_overlapping_points


def _reference(risks):
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


@pytest.mark.parametrize(("n", "seed"), [(1, 0), (10, 1), (60, 2), (400, 3)])
def test_positions_match_the_previous_loop_exactly(n, seed):
    rng = random.Random(seed)
    risks = pd.DataFrame({"risk_id": [f"R{i}" for i in range(n)],
                          "probability": [rng.randint(1, 5) for _ in range(n)],
                          "impact": [rng.randint(1, 5) for _ in range(n)]})
    risks["exposure"] = risks["probability"] * risks["impact"]
    risks = risks.sort_values("exposure", ascending=False).reset_index(drop=True)
    assert_frame_equal(_spread_overlapping_points(risks), _reference(risks), check_exact=True)
