"""UI smoke tests for the Streamlit demo (app.py) using streamlit.testing.v1.AppTest."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def start(faults: bool = True) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["animate"] = False
    at.session_state["faults"] = faults
    at.run()
    assert not at.exception, at.exception
    return at


def click(at: AppTest, text: str) -> AppTest:
    matches = [b for b in at.button if text in b.label]
    assert len(matches) == 1, f"{text!r} matched {[b.label for b in at.button]}"
    matches[0].click().run()
    assert not at.exception, at.exception
    assert not at.error or all("Error" not in e.value for e in at.error), [e.value for e in at.error]
    return at


def stage(at: AppTest) -> str:
    return at.session_state.wf.stage


def metrics(at: AppTest) -> dict[str, tuple[str, str | None]]:
    return {m.label: (m.value, m.delta) for m in at.metric}


def full_path(at: AppTest) -> AppTest:
    for label in ("Deliver", "Run the agents", "Approve as organiser", "Execute approved",
                  "Approve 6", "Execute approved", "Verify", "Replay"):
        click(at, label)
    return at


# ---------------------------------------------------------------- tests
def test_full_demo_path():
    at = full_path(start())
    assert stage(at) == "verified"
    assert len(at.session_state.wf.plans) == 2
    m = metrics(at)
    flat = {s for pair in m.values() for s in pair if s}
    assert "INR 60,000" in flat
    assert "Silver" in flat
    assert "-INR 10,000" in flat
    assert m["Duplicate effects"][0] == "0"


def test_reject_first_approval():
    at = start()
    click(at, "Deliver")
    click(at, "Run the agents")
    click(at, "Reject")
    assert stage(at) == "rejected"
    assert at.session_state.wf.store.effect_count() == 0


def test_reject_v2_at_delta_stage():
    at = start()
    for label in ("Deliver", "Run the agents", "Approve as organiser", "Execute approved"):
        click(at, label)
    assert stage(at) == "awaiting_delta_approval"
    click(at, "Reject v2")
    assert stage(at) == "rejected"


def test_untick_internal_notifications_sends_no_posts():
    at = start()
    click(at, "Deliver")
    click(at, "Run the agents")
    box = next(c for c in at.checkbox if c.label == "Internal notifications")
    box.uncheck().run()
    assert not at.exception
    click(at, "Approve as organiser")
    click(at, "Execute approved")
    if stage(at) == "awaiting_delta_approval":
        click(at, "changed actions")
        click(at, "Execute approved")
    click(at, "Verify")
    assert stage(at) == "verified"
    assert at.session_state.wf.store.list("post") == []


def test_faults_off_single_plan_verified():
    at = start()
    at.session_state["faults"] = False
    click(at, "Reset demo")
    for label in ("Deliver", "Run the agents", "Approve as organiser", "Execute approved", "Verify"):
        click(at, label)
    assert stage(at) == "verified"
    assert len(at.session_state.wf.plans) == 1


def test_every_tab_renders_after_full_path():
    at = full_path(start())
    assert len(at.tabs) >= 6 + 7
    assert len(at.dataframe) > 0
    assert len(at.get("graphviz_chart")) == 2
    assert len(at.get("json")) >= 1          # replay result in Verification tab
    captions = [c.value for c in at.caption]
    assert "Run the agents to see the impact graph." not in captions
    assert "No plan yet." not in captions
    assert "Not verified yet." not in captions
    assert "No operations yet." not in captions


def test_reset_midway_returns_to_ready():
    at = start()
    for label in ("Deliver", "Run the agents", "Approve as organiser"):
        click(at, label)
    assert stage(at) == "approved"
    click(at, "Reset demo")
    assert stage(at) == "ready"
    assert at.session_state.wf.store.effect_count() == 0
    assert at.session_state.seen == len(at.session_state.wf.store.logs())


def test_no_deprecated_use_container_width():
    assert "use_container_width" not in Path(APP).read_text(encoding="utf-8")


def test_run2_recalls_run1_from_long_term_memory():
    at = full_path(start())
    click(at, "Start run 2")
    wf = at.session_state.wf
    assert wf.stage == "ready" and wf.store.inherited_from == "S1-main-demo"
    assert at.selectbox(key="scenario").value == "S2-brightline-inherited"
    click(at, "Reset demo")
    assert at.session_state.wf.store.inherited_from == "S1-main-demo"
    for label in ("Deliver", "Run the agents", "Approve as organiser", "Execute approved", "Verify"):
        click(at, label)
    assert stage(at) == "verified"
    m = metrics(at)
    assert m["Aster's sponsorship"][0] == "INR 60,000"      # recalled from run 1, not the baseline
    assert m["Money left after costs"][0] == "INR 0"


def select_scenario(at: AppTest, scenario: str) -> AppTest:
    at.selectbox(key="scenario").select(scenario).run()
    assert not at.exception, at.exception
    assert stage(at) == "ready"
    assert at.session_state.wf.store.effect_count() == 0
    click(at, "Deliver")
    click(at, "Run the agents")
    return at


def test_two_authorised_contacts_pause_with_evidence_and_no_writes():
    at = select_scenario(start(), "S1-authorized-conflict")
    assert stage(at) == "needs_clarification"
    assert at.session_state.wf.store.effect_count() == 0
    assert at.session_state.wf.plan is None
    assert any("Human attention required" in w.value for w in at.warning)
    text = " ".join(x.value for x in at.markdown)
    assert "Neil" in text and "INR 80,000" in text and "INR 60,000" in text
    assert not any("Approve as organiser" in b.label for b in at.button)
    assert "Human clarification" in str(at.get("graphviz_chart")[0].proto)


def test_sponsor_confirmation_resumes_through_fresh_approval():
    at = select_scenario(start(), "S1-conflict-clarified")
    assert stage(at) == "needs_clarification"
    click(at, "Deliver sponsor confirmation")
    assert stage(at) == "awaiting_approval"
    assert at.session_state.wf.store.effect_count() == 0
    assert at.session_state.wf.trigger_id == "mail-aster-clarification"
    assert at.session_state.wf.store.on_log is None
    for label in ("Approve as organiser", "Execute approved", "Verify"):
        click(at, label)
    assert stage(at) == "verified"
    assert any("business decisions remain open" in w.value for w in at.warning)


@pytest.mark.parametrize("scenario", ["S1-approved", "S1-unauthorized-whatsapp", "S1-tracker-failure",
                                     "S1-timeout-after-write"])
def test_selected_workflow_completes_and_shows_recovery(scenario):
    at = select_scenario(start(), scenario)
    assert stage(at) == "awaiting_approval"
    for label in ("Approve as organiser", "Execute approved", "Verify", "Replay"):
        click(at, label)
    wf = at.session_state.wf
    assert wf.stage == "verified"
    assert wf.replay_result["new_effects"] == 0
    assert "Verified result" in str(at.get("graphviz_chart")[0].proto)
    if scenario == "S1-tracker-failure":
        assert any("Confirmed outcome" in x.value and "2 attempt(s)" in x.value for x in at.markdown)
    if scenario == "S1-timeout-after-write":
        assert any("confirmed by read-back; no repeated write" in x.value for x in at.markdown)


@pytest.mark.parametrize("scenario", ["S1-gmail-unavailable", "S1-privacy-agent-failure"])
def test_failed_source_or_privacy_gate_is_visible_and_blocks_planning(scenario):
    at = select_scenario(start(), scenario)
    assert stage(at) == "blocked"
    assert at.session_state.wf.store.effect_count() == 0
    assert any("Human attention required" in e.value for e in at.error)
    assert "Human investigation" in str(at.get("graphviz_chart")[0].proto)


def test_switching_scenarios_clears_previous_plan_and_approvals():
    at = start()
    for label in ("Deliver", "Run the agents", "Approve as organiser"):
        click(at, label)
    at.selectbox(key="scenario").select("S1-authorized-conflict").run()
    assert not at.exception
    assert stage(at) == "ready"
    assert at.session_state.wf.plan is None
    assert at.session_state.wf.approvals == []


def test_live_graph_highlights_real_agents_and_current_record(monkeypatch):
    import streamlit as st
    from streamlit.delta_generator import DeltaGenerator

    diagrams = []
    original_chart = st.graphviz_chart
    original_placeholder_chart = DeltaGenerator.graphviz_chart

    def capture_chart(dot, **kwargs):
        diagrams.append(dot)
        return original_chart(dot, **kwargs)

    monkeypatch.setattr(st, "graphviz_chart", capture_chart)

    def capture_placeholder_chart(self, dot, **kwargs):
        diagrams.append(dot)
        return original_placeholder_chart(self, dot, **kwargs)

    monkeypatch.setattr(DeltaGenerator, "graphviz_chart", capture_placeholder_chart)
    at = start()
    click(at, "Deliver")
    click(at, "Run the agents")
    for agent in ("Communication", "Knowledge", "Planning"):
        assert any(f'{agent}\\nActive' in dot for dot in diagrams)
    click(at, "Approve as organiser")
    click(at, "Execute approved")
    assert stage(at) == "awaiting_delta_approval"
    assert any("Execution\\nActive" in dot for dot in diagrams)
    assert at.session_state.wf.store.on_log is None
    assert any("current operation" in dot and "sponsor-aster" in dot for dot in diagrams)
    assert "Human approval\\nCurrent" in at.get("graphviz_chart")[0].proto.spec
