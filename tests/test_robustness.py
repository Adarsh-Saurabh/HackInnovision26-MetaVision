"""Robustness tests for the S1-main-demo workflow: gates, scopes, rejection, identity, isolation.

Happy-path outcomes live in test_main_demo.py; these cover the edges around them.
"""

import json
from pathlib import Path

import pytest

from second_brain.agents import _op_key
from second_brain.workflow import Workflow

PKG = Path(__file__).resolve().parent.parent / "second_brain"
BOTH = ["business_records", "internal_notifications"]


def _to_approval(wf: Workflow) -> Workflow:
    wf.ingest()
    wf.analyze()
    assert wf.stage == "awaiting_approval"
    return wf


def _run_until_delta(wf: Workflow, scopes=BOTH) -> Workflow:
    _to_approval(wf)
    wf.approve(scopes)
    assert wf.execute() == "awaiting_delta_approval"
    return wf


# 1 ---------------------------------------------------------------------------
def test_initial_rejection_writes_nothing():
    wf = _to_approval(Workflow())
    wf.reject()
    assert wf.stage == "rejected"
    assert wf.store.effect_count() == 0
    assert wf.store.ops() == []
    assert wf.store.get("sponsor", "sponsor-aster")["commitment_paise"] == 10000000
    with pytest.raises(RuntimeError):
        wf.execute()


# 2 ---------------------------------------------------------------------------
def test_business_only_scope_creates_no_posts():
    wf = _to_approval(Workflow())
    wf.approve(["business_records"])
    for _ in range(5):
        if wf.execute() != "awaiting_delta_approval":
            break
        wf.approve_delta(["business_records"])
    assert wf.stage == "executed"
    assert wf.store.list("post") == []
    assert not wf.store.history("post")
    drafts = wf.store.list("draft")
    assert len(drafts) == 1 and drafts[0]["sent"] is False
    post_keys = {a["op_key"] for p in wf.plans for a in p["actions"] if a["kind"] == "post"}
    assert post_keys and not (post_keys & wf.approved_keys)
    assert wf.verify()["ok"] is True
    assert wf.stage == "verified"


# 3 ---------------------------------------------------------------------------
def test_reject_at_delta_keeps_committed_v1_effects():
    wf = _run_until_delta(Workflow())
    effects_before = wf.store.effect_count()
    wf.reject()
    assert wf.stage == "rejected"
    st = wf.store
    assert st.get("sponsor", "sponsor-aster")["commitment_paise"] == 6000000
    # D3 is cancelled first, so the conflict stops the run before D4 (oracle profile-s1-rejected-delta)
    assert st.get("deliverable", "D4")["status"] == "planned"
    assert any(e["deliverable_id"] == "D4" for e in st.get("document", "doc-run-sheet")["entries"])
    d3 = st.get("deliverable", "D3")
    assert d3["status"] == "done"
    assert {h["actor"] for h in st.history("deliverable", "D3")} == {"person-social"}
    assert st.get("document", "doc-aster-benefits")["version"] == 1
    assert st.list("post") == []
    assert st.effect_count() == effects_before
    for step in (wf.execute, wf.verify, wf.approve_delta):
        with pytest.raises(RuntimeError):
            step()


# 4 ---------------------------------------------------------------------------
def test_step_order_guards():
    wf = Workflow()
    with pytest.raises(RuntimeError):
        wf.analyze()  # before ingest
    wf.ingest()
    for step in (wf.approve, wf.execute, wf.verify, wf.reject, wf.approve_delta, wf.replay):
        with pytest.raises(RuntimeError):
            step()
    wf.analyze()
    with pytest.raises(RuntimeError):
        wf.analyze()
    with pytest.raises(RuntimeError):
        wf.ingest()
    assert len(wf.plans) == 1
    assert wf.store.effect_count() == 0


# 5 ---------------------------------------------------------------------------
def test_two_runs_produce_identical_op_keys():
    a = Workflow().run_scripted()
    b = Workflow().run_scripted()
    assert len(a.plans) == len(b.plans) == 2
    for pa, pb in zip(a.plans, b.plans):
        assert [x["op_key"] for x in pa["actions"]] == [x["op_key"] for x in pb["actions"]]


# 6 ---------------------------------------------------------------------------
def test_op_key_tracks_changes_payload():
    wf = Workflow().run_scripted()
    v1 = {(a["tool"], a["target_id"]): a for a in wf.plans[0]["actions"]}
    v2 = {(a["tool"], a["target_id"]): a for a in wf.plans[1]["actions"]}
    same = changed = 0
    for k in v1.keys() & v2.keys():
        if v1[k]["changes"] == v2[k]["changes"]:
            assert v1[k]["op_key"] == v2[k]["op_key"], k
            same += 1
        else:
            assert v1[k]["op_key"] != v2[k]["op_key"], k
            changed += 1
    assert same and changed
    assert ("update_document", "doc-aster-benefits") in v1.keys() & v2.keys()
    assert v1[("update_document", "doc-aster-benefits")]["op_key"] != \
        v2[("update_document", "doc-aster-benefits")]["op_key"]
    # Direct: same payload -> same key; any change in `changes` -> new key.
    k1 = _op_key(wf.store, wf.proposal, "update_sponsor", "sponsor-aster", {"commitment_paise": 1})
    k2 = _op_key(wf.store, wf.proposal, "update_sponsor", "sponsor-aster", {"commitment_paise": 1})
    k3 = _op_key(wf.store, wf.proposal, "update_sponsor", "sponsor-aster", {"commitment_paise": 2})
    assert k1 == k2 != k3


# 7 ---------------------------------------------------------------------------
def test_source_visibility_respects_activation_and_allowlist():
    wf = Workflow()
    st = wf.store
    assert st.source("mail-aster-002") is None
    assert all(s["source_id"] != "mail-aster-002" for s in st.visible_sources())
    wf.ingest()
    assert st.source("mail-aster-002") is not None
    wf.analyze()
    wf.approve()
    while wf.execute() == "awaiting_delta_approval":
        wf.approve_delta()
    wf.verify()
    allow = set(st.scenario["available_source_ids"])
    visible = {s["source_id"] for s in st.visible_sources()}
    assert visible <= allow
    for sid in ("mail-aster-private", "mail-aster-injection"):
        assert sid not in allow
        assert st.source(sid) is None
        assert st.evidence_for_source(sid) == []
    assert not any(e["source_id"] in ("mail-aster-private", "mail-aster-injection")
                   for e in st.list_evidence())


def test_delivering_out_of_allowlist_source_never_makes_it_visible():
    st = Workflow().store
    assert st.deliver("mail-aster-private") is False
    assert st.source("mail-aster-private") is None
    assert st.evidence_for_source("mail-aster-private") == []


# 8 ---------------------------------------------------------------------------
def test_runtime_never_references_oracle():
    files = sorted(PKG.glob("*.py"))
    assert files
    for f in files:
        assert "expected_outcomes" not in f.read_text(encoding="utf-8"), f.name


# 9 ---------------------------------------------------------------------------
def test_file_backed_db(tmp_path):
    db = tmp_path / "run.db"
    wf = Workflow(db_path=str(db)).run_scripted()
    try:
        assert wf.stage == "verified"
        assert db.exists() and db.stat().st_size > 0
    finally:
        wf.store.db.close()


# 10 --------------------------------------------------------------------------
def test_retry_exhaustion_stops_safely():
    wf = Workflow()
    wf.tools.faults = [
        {"fault_id": f"fault-transient-{n}", "kind": "transient_before_write",
         "target_tool": "update_sponsor", "target_id": "sponsor-aster", "attempt": n,
         "timing": "before_write", "actor_id": None, "effect": None}
        for n in (1, 2, 3)
    ]
    _to_approval(wf)
    wf.approve()
    assert wf.execute() == "failed"
    assert wf.stage == "failed"
    sponsor = wf.store.get("sponsor", "sponsor-aster")
    assert sponsor["commitment_paise"] == 10000000 and sponsor["version"] == 1
    assert wf.store.effect_count() == 0
    sponsor_key = wf.plan["actions"][0]["op_key"]
    assert wf.action_status[sponsor_key] == "failed"
    assert wf.store.op_get(sponsor_key)["attempts"] == 3
    report = wf.verify()  # a stopped run can be verified, and must not report success
    assert not report["ok"] and wf.stage == "verification_failed"


# 11 --------------------------------------------------------------------------
def test_duplicate_trigger_before_approval_has_no_effect():
    wf = Workflow()
    wf.ingest()
    assert wf.store.deliver(wf.trigger_id) is False
    wf.analyze()
    before = wf.store.effect_count()
    assert wf.store.deliver(wf.trigger_id) is False
    assert wf.store.effect_count() == before == 0
    assert wf.stage == "awaiting_approval"
    assert wf.store.ops() == []


# 12 --------------------------------------------------------------------------
def test_logs_are_unicode_and_json_safe():
    wf = Workflow().run_scripted()
    wf.replay(2)
    logs = wf.store.logs()
    assert logs
    for row in logs:
        assert isinstance(row["message"], str) and row["message"]
        assert isinstance(row["agent"], str)
        json.loads(json.dumps(row, ensure_ascii=False))
    assert any("→" in r["message"] for r in logs)


# Reviewer regressions -------------------------------------------------------
def test_replay_never_executes_uncommitted_actions():
    wf = Workflow()
    wf.ingest(); wf.analyze()
    wf.approve(["internal_notifications"])
    assert wf.execute() == "executed"          # posts blocked: business deps never ran
    assert wf.store.effect_count() == 0
    assert wf.replay(1)["new_effects"] == 0


def test_verify_fails_when_approved_actions_blocked():
    wf = Workflow()
    wf.ingest(); wf.analyze()
    wf.approve(["internal_notifications"])
    wf.execute()
    report = wf.verify()
    assert not report["ok"] and wf.stage == "verification_failed"
    assert any(c["name"] == "every approved action executed" and not c["ok"] for c in report["checks"])


def test_verify_passes_for_honest_noop_approval():
    wf = Workflow()
    wf.ingest(); wf.analyze()
    wf.approve([])
    wf.execute()
    assert wf.verify()["ok"] and wf.stage == "verified"


def test_delta_internal_only_is_not_falsely_verified():
    wf = Workflow()
    wf.ingest(); wf.analyze(); wf.approve()
    assert wf.execute() == "awaiting_delta_approval"
    wf.approve_delta(["internal_notifications"])
    wf.execute()
    assert not wf.verify()["ok"]
    assert wf.replay(1)["new_effects"] == 0
