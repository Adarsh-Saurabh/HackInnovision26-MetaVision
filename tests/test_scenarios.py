"""Every dataset scenario the prototype simulates must match its expected outcome (scripts/run_scenarios.py)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_scenarios as rs  # noqa: E402

SCENARIOS = {s["scenario_id"]: s for s in rs.load("scenarios.json")["scenarios"]}
EO = rs.load("expected_outcomes.json")
PROFILES = {p["profile_id"]: p for p in EO["outcome_profiles"]}
# Features the prototype does not implement; reported as NOT TESTED / FAIL by the runner.
OUT_OF_SCOPE = {"S1-calendar-outage", "S1-short-term-approval-resume", "S1-short-term-partial-resume",
                "S2-brightline-inherited"}


@pytest.mark.parametrize("outcome", [o for o in EO["outcomes"] if o["scenario_id"] not in OUT_OF_SCOPE],
                         ids=lambda o: o["scenario_id"])
def test_scenario_matches_expected_outcome(outcome):
    sc = SCENARIOS[outcome["scenario_id"]]
    wf = rs.run(sc)
    assert rs.evaluate(wf, sc, outcome, PROFILES.get(outcome["profile_id"])) == []
    assert rs.gaps(sc) == []
