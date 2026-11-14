"""Long-term memory: a second scenario starts from the first run's verified state, or refuses to run."""

from second_brain.agents import compute_financials
from second_brain.workflow import Workflow


def test_s2_without_parent_memory_is_blocked(tmp_path):
    wf = Workflow("S2-brightline-inherited", memory_path=str(tmp_path / "memory.sqlite"))
    assert wf.stage == "blocked"
    assert wf.store.effect_count() == 0


def test_s2_recalls_verified_s1_state(tmp_path):
    mem = str(tmp_path / "memory.sqlite")
    s1 = Workflow("S1-main-demo", memory_path=mem).run_scripted()
    assert s1.stage == "verified"

    s2 = Workflow("S2-brightline-inherited", memory_path=mem)
    assert s2.stage == "ready"
    aster = s2.store.get("sponsor", "sponsor-aster")
    assert (aster["commitment_paise"], aster["tier"]) == (6000000, "Silver")   # recalled, not baseline
    assert s2.store.effect_count() == 0 and s2.store.inherited_history()      # past kept separately

    s2.run_scripted()
    assert s2.stage == "verified"
    assert compute_financials(s2.store)["forecast_balance_paise"] == 0
    touched = {h["id"] for h in s2.store.history()}
    assert not touched & {"sponsor-aster", "D1", "D2", "D3", "D4", "DEC-05", "cal-sponsor-review"}
    assert any("long-term memory" in f for f in s2.plan["flags"])
