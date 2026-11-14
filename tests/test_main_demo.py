"""End-to-end check of S1-main-demo against the test-only expected outcome profile.

expected_outcomes.json is read here (test oracle) and never by runtime code.
"""

import json
from pathlib import Path

import pytest

from second_brain.agents import compute_financials
from second_brain.workflow import Workflow

FIX = Path(__file__).resolve().parent.parent / "data" / "fixtures"


@pytest.fixture(scope="module")
def oracle():
    data = json.loads((FIX / "expected_outcomes.json").read_text(encoding="utf-8"))
    outcome = next(o for o in data["outcomes"] if o["scenario_id"] == "S1-main-demo")
    return next(p for p in data["outcome_profiles"] if p["profile_id"] == outcome["profile_id"])


@pytest.fixture(scope="module")
def wf():
    return Workflow("S1-main-demo").run_scripted()


def test_reaches_verified_with_two_plans(wf):
    assert wf.stage == "verified", wf.verification
    assert [p["version"] for p in wf.plans] == [1, 2]
    assert wf.plans[1]["parent_plan_id"] == wf.plans[0]["plan_id"]
    assert wf.verification["failed"] == 0


def test_financials(wf, oracle):
    fin = compute_financials(wf.store)
    for k, v in oracle["financials"].items():
        assert fin[k] == v, k


def test_sponsors(wf, oracle):
    for eff in oracle["sponsor_effects"]:
        rec = wf.store.get("sponsor", eff["sponsor_id"])
        assert rec["commitment_paise"] == eff["commitment_paise"]
        assert rec["cash_received_paise"] == eff["cash_received_paise"]
        assert rec["tier"] == eff["tier"]


def test_deliverables(wf, oracle):
    for eff in oracle["deliverable_effects"]:
        rec = wf.store.get("deliverable", eff["deliverable_id"])
        assert rec["status"] == eff["status"], eff["deliverable_id"]
        assert wf.plan["dispositions"][eff["deliverable_id"]] == eff["disposition"]
        writers = {h["actor"] for h in wf.store.history("deliverable", eff["deliverable_id"])}
        expected = {"none": set(), "agent": {"Execution"}, "injected_external": {"person-social"}}
        assert writers == expected[eff["mutation_actor"]], eff["deliverable_id"]
    run_sheet = wf.store.get("document", "doc-run-sheet")
    ids = [e["entry_id"] for e in run_sheet["entries"]]
    assert "entry-run-D4" not in ids
    assert ids == ["entry-run-welcome", "entry-run-housekeeping", "entry-run-closing"]


def test_decisions(wf, oracle):
    for eff in oracle["decision_effects"]:
        rec = wf.store.get("decision", eff["decision_id"])
        assert rec["status"] == eff["status"]
        assert rec.get("superseded_by") == eff["superseded_by"]
        if eff["replacement_status"]:
            assert wf.store.get("decision", eff["superseded_by"])["status"] == eff["replacement_status"]
        if eff["condition_satisfied"] is not None:
            assert rec["condition_evaluation"]["satisfied"] is eff["condition_satisfied"]


def test_review_meeting(wf, oracle):
    rev = oracle["review"]
    items = [c for c in wf.store.list("calendar") if c["logical_key"] == rev["logical_key"]]
    assert len(items) == rev["logical_count"]
    assert (items[0]["starts_at"], items[0]["ends_at"]) == (rev["starts_at"], rev["ends_at"])
    assert wf.store.get("calendar", "cal-volunteer-briefing")["version"] == 1


def test_preserved_records_untouched(wf, oracle):
    touched = {h["id"] for h in wf.store.history()}
    for rid in ("sponsor-brightline", "sponsor-corvex", "doc-budget", "doc-brightline-benefits",
                "cal-volunteer-briefing", "D1", "D2", "policy-tiers-v1"):
        assert rid in oracle["preserved_ids"]
        assert rid not in touched, rid


def test_tracker_retry_happened_once(wf):
    sponsor_ops = [o for o in wf.store.ops() if o["target_id"] == "sponsor-aster"]
    assert len(sponsor_ops) == 1
    assert sponsor_ops[0]["status"] == "committed" and sponsor_ops[0]["attempts"] == 2
    writes = [h for h in wf.store.history("sponsor", "sponsor-aster")]
    assert len(writes) == 1


def test_delta_approval_only_for_changed_actions(wf):
    v1_keys = {a["op_key"] for a in wf.plans[0]["actions"]}
    needs = {k for k, v in wf.delta.items() if v == "needs_approval"}
    assert needs and not (needs & v1_keys)
    assert any(v == "reuse" for v in wf.delta.values())
    assert [a["stage"] for a in wf.approvals] == ["initial", "delta"]
    assert "D3" in {a["target_id"] for a in wf.plans[0]["actions"]}
    assert "D3" not in {a["target_id"] for a in wf.plans[1]["actions"]}


def test_sponsor_reply_is_draft_not_sent(wf):
    drafts = wf.store.list("draft")
    assert len(drafts) == 1 and drafts[0]["sent"] is False
    assert "over" in json.dumps(drafts[0]).lower() or "published" in json.dumps(drafts[0]).lower()


def test_internal_posts_reflect_v2(wf, oracle):
    posts = wf.store.list("post")
    assert {p["recipient_id"] for p in posts} == {
        "person-design", "person-social", "person-events", "person-finance"}
    assert all(p["version"] == 1 for p in posts)


def test_replay_zero_duplicates(wf):
    before_ops = len(wf.store.ops())
    result = wf.replay(10)
    assert result["new_effects"] == 0
    assert result["duplicates_ignored"] == 10
    assert len(wf.store.ops()) == before_ops


def test_no_faults_path_single_plan():
    w = Workflow("S1-main-demo", inject_faults=False).run_scripted()
    assert w.stage == "verified"
    assert len(w.plans) == 1
    assert w.store.get("deliverable", "D3")["status"] == "cancelled"
