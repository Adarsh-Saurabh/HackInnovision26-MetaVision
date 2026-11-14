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
