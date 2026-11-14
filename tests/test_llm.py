"""Live-extraction reconciliation, tested offline with fake extractors (no network)."""

from second_brain.llm import CommitmentChange, cross_check
from second_brain.workflow import Workflow


def _proposal():
    wf = Workflow()
    wf.ingest()
    from second_brain.agents import communication_agent
    return wf.store, communication_agent(wf.store, wf.trigger_id)


def _fake(**kw):
    base = dict(sponsor_name="Aster Labs", old_amount_inr=100000, new_amount_inr=60000, currency="INR",
                is_firm_request=True, deadline_phrase="by 18:00 IST tomorrow")
    base.update(kw)
    return lambda body: CommitmentChange(**base)


def test_agreeing_model_output_is_accepted():
    store, prop = _proposal()
    out = cross_check(store, prop, _fake())
    assert out["llm"]["status"] == "agree" and out["method"].startswith("gemini:")
    assert out["new_paise"] == 6000000


def test_hallucinated_amount_is_rejected_and_rules_kept():
    store, prop = _proposal()
    out = cross_check(store, prop, _fake(new_amount_inr=65000))
    assert out["llm"]["status"] == "disagree"
    assert out["new_paise"] == 6000000 and out["method"] == prop["method"]


def test_api_error_falls_back_to_rules():
    store, prop = _proposal()

    def boom(body):
        raise TimeoutError("slow")
    out = cross_check(store, prop, boom)
    assert out["llm"]["status"] == "error" and out["new_paise"] == 6000000


def test_workflow_default_makes_no_llm_calls():
    wf = Workflow().run_scripted()
    assert wf.use_llm is False and "llm" not in wf.proposal and wf.stage == "verified"


def test_partial_number_is_not_grounded():
    from second_brain.llm import _in_text
    body = "from INR 100,000 to INR 60,000."
    assert _in_text(60000, body) and _in_text(100000, body)
    assert not _in_text(60, body) and not _in_text(6000, body) and not _in_text(0, body)


def test_indian_grouping_and_superstrings():
    from second_brain.llm import _in_text
    assert _in_text(600000, "INR 6,00,000 now") and not _in_text(60000, "INR 160,000")


def test_wrong_sponsor_or_missing_old_amount_rejected():
    store, prop = _proposal()
    assert cross_check(store, prop, _fake(sponsor_name="Brightline Foods"))["llm"]["status"] == "disagree"
    assert cross_check(store, prop, _fake(old_amount_inr=None))["llm"]["status"] == "disagree"
    assert cross_check(store, prop, _fake(sponsor_name=""))["llm"]["status"] == "disagree"
    assert cross_check(store, prop, _fake(deadline_phrase="by Friday"))["llm"]["status"] == "disagree"


def test_unverified_sender_text_never_sent():
    store, prop = _proposal()
    calls = []
    out = cross_check(store, {**prop, "authorized": False}, lambda b: calls.append(b))
    assert out["llm"]["status"] == "skipped" and calls == []


def test_network_guard_blocks_real_calls():
    store, prop = _proposal()
    assert cross_check(store, prop)["llm"]["status"] == "error"   # conftest blocks gemini_extract
