"""Size test for project-controls-dashboard: run by hand, not part of CI or the test suite.

Builds generated risk and change registers of the given size, and a milestone list a tenth that size at each size, runs `dashboard.py` end to end on it in a fresh
Python process, and prints the wall time and peak memory. Everything runs in
a temporary copy of the repo, so assets/ and data/ here are never touched.
Inputs are generated with fixed seeds: the same size always gives the same
files.

    python benchmarks/size_test.py
    python benchmarks/size_test.py --sizes 100 1000

Peak memory needs psutil (pip install psutil) on Windows; without it only
time is shown there. Timings depend on the machine. The measured numbers in
the README's Limitations section say which machine they came from.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIZES = [100, 1000, 10000, 50000]
UNIT = "risks and changes each"

CATEGORIES = ["Client Request", "Design", "Environmental", "Logistics", "Procurement", "Engineering"]

def _write(df: pd.DataFrame, data_dir: str, name: str) -> None:
    df.to_csv(os.path.join(data_dir, name), index=False)

def risk_register(n: int, seed: int = 3) -> pd.DataFrame:
    rng = random.Random(seed)
    return pd.DataFrame([{
        "risk_id": f"R{i:05d}", "description": f"Synthetic risk {i}",
        "category": rng.choice(CATEGORIES), "probability": rng.randint(1, 5),
        "impact": rng.randint(1, 5), "status": rng.choice(["Open", "Mitigating", "Closed"]),
        "mitigation_owner": "Owner", "mitigation_due_date":
            (pd.Timestamp("2026-03-01") + pd.Timedelta(days=rng.randint(0, 300))).date().isoformat(),
    } for i in range(n)])

def change_log(n: int, seed: int = 2, decided_col: bool = True) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        raised = pd.Timestamp("2026-01-05") + pd.Timedelta(days=rng.randint(0, 200))
        status = rng.choices(["Approved", "Rejected", "Pending"], [60, 15, 25])[0]
        row = {
            "change_id": f"CC{i:05d}", "description": f"Synthetic change {i}",
            "category": rng.choice(CATEGORIES),
            "cost_impact": rng.randint(-20, 80) * 1000,
            "schedule_impact_days": rng.randint(-5, 20),
            "date_raised": raised.date().isoformat(), "status": status,
        }
        if decided_col:
            decided = raised + pd.Timedelta(days=rng.randint(2, 40))
            row["date_decided"] = decided.date().isoformat() if status != "Pending" else ""
        rows.append(row)
    return pd.DataFrame(rows)

def milestones(n: int, seed: int = 5) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        planned = pd.Timestamp("2026-03-01") + pd.Timedelta(days=rng.randint(0, 330))
        cur = planned + pd.Timedelta(days=rng.randint(-5, 40))
        rows.append({
            "milestone": f"Milestone {i}", "planned_date": planned.date().isoformat(),
            "current_date": cur.date().isoformat(),
            "date_type": "Actual" if planned < pd.Timestamp("2026-10-01") else "Forecast",
            "status": "Complete" if planned < pd.Timestamp("2026-10-01") else "Open",
        })
    return pd.DataFrame(rows)

def generate(n, data_dir, sample_dir):
    _write(risk_register(n), data_dir, "risk_register.csv")
    _write(change_log(n, decided_col=False), data_dir, "change_register.csv")
    _write(milestones(max(9, n // 10)), data_dir, "milestones.csv")

CHILD = r"""
import contextlib, io, json, os, sys, time
os.environ["MPLBACKEND"] = "Agg"
sys.path.insert(0, __ROOT__); os.chdir(__ROOT__)
mod = __import__("dashboard")
t0 = time.perf_counter()
with contextlib.redirect_stdout(io.StringIO()):
    mod.main()
seconds = time.perf_counter() - t0
peak_mb = None
try:
    import resource
    kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mb = kb / 1024 / (1024 if sys.platform == "darwin" else 1)
except ImportError:
    try:
        import psutil
        info = psutil.Process().memory_info()
        peak_mb = getattr(info, "peak_wset", info.rss) / 2**20
    except ImportError:
        pass
print("RESULT" + json.dumps({"seconds": seconds, "peak_mb": peak_mb}))
"""


def run_once(n: int) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="size-test-"))
    try:
        root = tmp / ROOT.name
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "*.png"))
        generate(n, str(root / "data"), str(ROOT / "data"))
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run([sys.executable, "-c", CHILD.replace("__ROOT__", repr(str(root)))],
                              capture_output=True, text=True, encoding="utf-8", env=env)
        line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT")), None)
        if line is None:
            return {"error": (proc.stderr.strip().splitlines() or ["no output"])[-1]}
        return json.loads(line[len("RESULT"):])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=int, nargs="+", default=DEFAULT_SIZES, help=f"sizes in {UNIT}")
    args = parser.parse_args()
    print(f"{UNIT:>24}  {'seconds':>9}  {'peak MB':>8}")
    for n in args.sizes:
        result = run_once(n)
        if "error" in result:
            print(f"{n:>24,}  failed: {result['error']}")
            continue
        peak = f"{result['peak_mb']:8.0f}" if result["peak_mb"] is not None else "     n/a"
        print(f"{n:>24,}  {result['seconds']:9.2f}  {peak}", flush=True)


if __name__ == "__main__":
    main()
