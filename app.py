"""MetaVision / Second Brain: Streamlit demo UI for scenario S1-main-demo.

Run: uv run --locked streamlit run app.py
Theme lives in .streamlit/config.toml.
"""

from __future__ import annotations

import html
import json
import time

import streamlit as st

from second_brain import llm
from second_brain.agents import compute_financials, inr
from second_brain.tools import APP_NAMES
from second_brain.workflow import Workflow

st.set_page_config(page_title="Second Brain · MetaVision", layout="wide")

# ---------------------------------------------------------------- plain-English vocabulary
AGENTS = [
    ("Communication", "Reads emails and chats and pulls out the facts: who, what, how much, by when."),
    ("Knowledge", "Knows how records are linked, so it can find everything one change affects."),
    ("Planning", "Writes the list of changes needed, and marks which ones a person must decide."),
    ("Execution", "Makes the approved changes. Retries safely if an app fails."),
    ("Verification", "Reads every changed record again to prove the change really happened."),
    ("Coordinator", "Decides which helper works next, and stops the run when something looks wrong."),
]
GLOSSARY = [
    ("Plan v1 / v2", "The first list of changes, and the updated list made after something changed mid-way."),
    ("Approval group", "Changes are grouped so a person can allow some (update records) and not others "
                       "(email the sponsor)."),
    ("Version conflict", "Someone else edited the same record first. We stop instead of overwriting their work."),
    ("Replay", "Sending the same email again on purpose, to prove nothing gets done twice."),
    ("Duplicate effects", "Changes made twice by mistake. This should always be 0."),
    ("Action key", "A fingerprint of one change. If the same fingerprint comes back, the change is skipped."),
]
# Timeline: which event kinds get a word tag, and which are important enough to stand out.
KIND_TAG = {"error": "Problem", "conflict": "Clash", "retry": "Retry", "write": "Changed",
            "reuse": "Skipped, already done", "approval": "Approval", "verified": "Checked",
            "verify": "Checked", "external": "Outside event", "flag": "Needs a person",
            "trigger": "New message", "blocked": "Stopped", "replay": "Repeat test",
            "inference": "Guessed link", "llm": "AI read"}
KIND_STRONG = {"error", "conflict", "blocked", "approval", "external", "trigger", "flag"}
STEPS = [("Email arrives", {"ready"}),
         ("AI reads it", {"ingested"}),
         ("Person approves", {"awaiting_approval"}),
         ("Changes made", {"approved", "executing"}),
         ("Plan updated", {"awaiting_delta_approval"}),
         ("Double-check", {"executed"}),
         ("Repeat test", {"verified"})]
SCOPE_LABEL = {"business_records": "Business records", "internal_notifications": "Internal notifications",
               "sponsor_send": "Send to sponsor"}
SCENARIOS = {
    "S1-main-demo": ("Full demo: retry + teammate edit", "A temporary failure is retried; a concurrent edit requires plan v2 and fresh approval."),
    "S1-approved": ("Normal approval", "One confirmed sponsor change → plan → human approval → execution → verification."),
    "S1-authorized-conflict": ("Two sponsor contacts disagree", "Priya says INR 60,000; Neil says INR 80,000. Both are authorised. Pause for clarification, with no writes."),
    "S1-conflict-clarified": ("Contact conflict → confirmation → resume", "Pause on the two claims, then deliver a confirmation replacing both. A fresh plan still needs approval."),
    "S1-unauthorized-whatsapp": ("Unverified competing message", "An unregistered sender claims INR 80,000. It cannot override Priya's authorised request."),
    "S1-tracker-failure": ("Recovery: temporary tracker failure", "The tracker fails before writing. Retry the same operation safely, then verify."),
    "S1-timeout-after-write": ("Recovery: timeout after a write", "The response is lost after a write. Read the record back to confirm success instead of writing twice."),
    "S1-gmail-unavailable": ("Blocked: email unavailable", "The trigger cannot be read. Stop without substituting an unrelated chat message."),
    "S1-privacy-agent-failure": ("Blocked: privacy check unavailable", "The privacy check fails. Stop before releasing context or planning changes."),
}
STATUS_LABEL = {"pending": "Waiting", "committed": "Done", "reused": "Already done", "conflict": "Clash, stopped",
                "stopped": "Stopped", "blocked": "Blocked", "not_approved": "Not approved", "failed": "Failed"}
DELTA_LABEL = {"reuse": "Already done, not repeated", "covered": "Unchanged, already approved",
               "needs_approval": "New or changed, needs OK"}
DISPOSITION_LABEL = {"flag_human": "a person must decide", "satisfied": "already fine",
                     "cancel": "cancel it", "over_delivery": "promised too much"}

st.markdown("""
<style>
.block-container {padding-top: 3.2rem; padding-bottom: 2rem; max-width: 1480px;}
[data-testid="stMain"] {background: linear-gradient(180deg, #f0f4ff 0, #f8fafc 340px);}
[data-testid="stHeader"] {background: #f8fafc;}
[data-testid="stSidebar"] {border-right: 1px solid #dfe6f0;}
h1, h2, h3 {letter-spacing: -0.02em; color: #172b4d;}
.eyebrow {font-size: .7rem; font-weight: 600; letter-spacing: .14em; text-transform: uppercase;
           color: #4f46e5; margin: 0 0 8px 0;}
.title {font-size: 2.1rem; font-weight: 700; color: #172b4d; letter-spacing: -0.03em;
        margin: 2px 0 8px 0; line-height: 1.18;}
.lede {font-size: 1rem; color: #52627a; max-width: 62rem; margin-bottom: 18px; line-height: 1.65;}
.steps {display: flex; gap: 0; margin: 4px 0 22px 0; border: 1px solid #dfe6f0;
        border-radius: 12px; overflow: hidden; box-shadow: 0 3px 12px #172b4d05;}
.steps div {flex: 1; min-width: 0; padding: 11px 10px; font-size: .82rem; color: #64748b;
            border-right: 1px solid #e5eaf2; background: #fff;}
.steps div:last-child {border-right: none;}
.steps div span {display: block; font-size: .64rem; font-weight: 600; letter-spacing: .08em;
                text-transform: uppercase; margin-bottom: 4px;}
.steps div.done {color: #0f6b60; background: #edf8f5;}
.steps div.now {color: #fff; background: linear-gradient(120deg, #4f46e5, #6366f1); font-weight: 600;}
[data-testid="stMetric"] {border: 1px solid #dfe6f0; border-top: 3px solid #a5b4fc; border-radius: 12px;
                         padding: 13px 16px; background: #fff; box-shadow: 0 3px 12px #172b4d05;}
[data-testid="stMetricLabel"] p {font-size: .78rem; color: #52627a;}
[data-testid="stMetricValue"] {font-size: 1.45rem; font-weight: 600; color: #172b4d;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 14px; background: #fff;}
[data-testid="stExpander"] {background: #fff; border-radius: 12px;}
[data-testid="stGraphVizChart"] {background: #fff; border: 1px solid #e5eaf2; border-radius: 12px; padding: 12px;}
[data-testid="stBaseButton-primary"] {box-shadow: 0 3px 8px #4f46e51a; font-weight: 600;}
button:focus-visible, [role="tab"]:focus-visible {outline: 3px solid #818cf8 !important; outline-offset: 3px;}
.note {padding: 13px 16px; margin: 10px 0; background: #eef2ff; color: #303d68;
       border-left: 3px solid #6366f1; border-radius: 0 10px 10px 0; font-size: .92rem; line-height: 1.6;}
.note.soft {background: #fffbeb; color: #78460c; border-left-color: #d97706;}
.note ul {margin: 4px 0 0 0; padding-left: 18px;}
.label {font-size: .7rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase;
        color: #52627a; margin: 14px 0 6px 0;}
.msg {padding: 13px 16px; border: 1px solid #dfe6f0; border-radius: 10px; margin-bottom: 10px;
      white-space: pre-wrap; font-size: .9rem; line-height: 1.6; background: #fff;}
.msg.trigger {border: 1px solid #a5b4fc; border-left: 4px solid #4f46e5; background: #f8f9ff;}
.msg .meta {font-size: .76rem; color: #52627a; display: block; margin-bottom: 8px;}
.tl {font-size: .85rem; line-height: 1.55; padding: 10px 13px; margin: 0 0 9px 0;
     border-left: 3px solid #cbd5e1; border-radius: 0 10px 10px 0; background: #fff;}
.tl.strong {border-left-color: #6366f1; background: #eef2ff;}
.tl .who {font-weight: 600;}
.tl .when {color: #64748b; font-size: .74rem; font-family: "IBM Plex Mono", monospace; margin-left: 6px;}
.tag {display: inline-block; font-size: .64rem; letter-spacing: .06em; text-transform: uppercase;
      border: 1px solid #c7d2fe; border-radius: 5px; color: #4338ca; background: #eef2ff;
      padding: 1px 6px; margin-left: 6px; vertical-align: 1px; font-weight: 600;}
.tl.event-error, .tl.event-conflict, .tl.event-blocked {border-left-color: #dc2626; background: #fff1f2;}
.tl.event-error .tag, .tl.event-conflict .tag, .tl.event-blocked .tag {color: #991b1b; background: #fee2e2; border-color: #fecaca;}
.tl.event-flag, .tl.event-approval, .tl.event-retry {border-left-color: #d97706; background: #fffbeb;}
.tl.event-flag .tag, .tl.event-approval .tag, .tl.event-retry .tag {color: #92400e; background: #fef3c7; border-color: #fde68a;}
.tl.event-write, .tl.event-verified, .tl.event-verify {border-left-color: #0d9488; background: #f0fdfa;}
.tl.event-write .tag, .tl.event-verified .tag, .tl.event-verify .tag {color: #115e59; background: #ccfbf1; border-color: #99f6e4;}
.check {font-size: .9rem; padding: 9px 0; border-bottom: 1px solid #e5eaf2;}
.check b.pass, .check b.fail {display: inline-block; width: 44px; font-size: .7rem; letter-spacing: .08em;
                            border-radius: 4px; text-align: center; margin-right: 8px;}
.check b.pass {background: #ccfbf1; color: #115e59;}
.check b.fail {background: #fee2e2; color: #991b1b;}
.agent {font-size: .86rem; margin: 0 0 9px 0; line-height: 1.35;}
.agent b {display: block; color: #303d68;}
.agent span {color: #52627a;}
code {color: #4338ca !important; background: #eef2ff !important;}
[data-testid="stHeaderActionElements"] {display: none;}
@media (max-width: 700px) {
    .title {font-size: 1.75rem;}
    .steps div {padding: 8px 5px; font-size: .72rem;}
}
</style>
""", unsafe_allow_html=True)


def note(body_html: str, soft: bool = False) -> None:
    st.markdown(f'<div class="note{" soft" if soft else ""}">{body_html}</div>', unsafe_allow_html=True)


def label(text: str) -> None:
    st.markdown(f'<div class="label">{html.escape(text)}</div>', unsafe_allow_html=True)


def bullet_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>"


# ---------------------------------------------------------------- state
def new_workflow() -> None:
    old = st.session_state.get("wf")
    if old is not None:
        old.close()
    st.session_state.wf = Workflow(st.session_state.get("scenario", "S1-main-demo"),
                                   inject_faults=st.session_state.get("faults", True))
    st.session_state.seen = 0
    st.session_state.pop("error", None)


if "wf" not in st.session_state:
    new_workflow()
wf: Workflow = st.session_state.wf
store = wf.store


def run_step(fn, *args) -> None:
    last_agent = None

    def progress(entry: dict) -> None:
        nonlocal last_agent
        agent = entry["agent"]
        render_flow("Execution" if agent == "External" else agent, entry["message"])
        data = entry.get("data") or {}
        target = data.get("target_id")
        if not target and data.get("op_key") and wf.plan:
            target = next((a["target_id"] for a in wf.plan["actions"] if a["op_key"] == data["op_key"]), None)
        if wf.impact and target:
            impact_slot.graphviz_chart(graph_dot(target), width="stretch")
        if st.session_state.get("animate", True) and agent != last_agent:
            time.sleep(0.35)
        last_agent = agent

    store.on_log = progress
    try:
        fn(*args)
    except Exception as exc:  # keep the demo alive; show the problem instead of a stack trace
        st.session_state.error = f"{type(exc).__name__}: {exc}"
    finally:
        store.on_log = None
    if wf.stage in ("awaiting_approval", "awaiting_delta_approval", "needs_clarification", "blocked",
                    "failed", "verification_failed"):
        st.session_state.notification = "Human attention required. Review the evidence and checklist before continuing."
    st.rerun()


def deliver_messages() -> None:
    wf.ingest()
    for act in sorted(store.scenario["activation"], key=lambda a: a["order"]):
        if act["phase"] == "trigger" and act["source_id"] != wf.trigger_id:
            store.deliver(act["source_id"])


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown('<div class="eyebrow">HackInnovision 2026 · Track B</div>', unsafe_allow_html=True)
    st.markdown("### Second Brain")
    st.caption("A college fest team works across email, chat, a sponsor tracker, a budget sheet, docs and a "
               "calendar. This demo shows what happens when one sponsor changes their deal. All data is made up.")
    st.selectbox("Demo workflow", list(SCENARIOS), key="scenario",
                 format_func=lambda sid: SCENARIOS[sid][0], on_change=new_workflow,
                 help="Switching workflow starts a fresh synthetic workspace.")
    if st.button("Reset demo", width="stretch"):
        new_workflow()
        st.rerun()
    st.toggle("Simulate problems", value=True, key="faults",
              help="Enable the selected workflow's scripted failure (retry, concurrent edit, timeout, or outage). "
                   "Takes effect after Reset.")
    st.toggle("Show timeline step by step", value=True, key="animate")
    st.toggle("Let Gemini AI read the email", value=llm.live_default(), key="llm",
              disabled=not llm.live_available(),
              help=f"Uses {llm.model_name()}. Its answer is only used if it quotes the email and matches "
                   "the rule-based reading. Off = rules only, no internet needed."
                   + ("" if llm.live_available() else " No GEMINI_API_KEY in .env."))
    if wf.stage in ("ready", "ingested"):
        wf.use_llm = bool(st.session_state.get("llm")) and llm.live_available()
    st.divider()
    label("The six AI helpers")
    for name, role in AGENTS:
        st.markdown(f'<div class="agent"><b>{name}</b><span>{role}</span></div>', unsafe_allow_html=True)
    st.divider()
    with st.expander("Words used on this screen"):
        for term, meaning in GLOSSARY:
            st.markdown(f"**{term}**: {meaning}")
    st.caption(f"Demo clock: {store.demo_now.replace('T', ' ')[:16]} IST · stage `{wf.stage}`")

# ---------------------------------------------------------------- header + steps
st.markdown('<div class="eyebrow">MetaVision · Second Brain</div>'
            '<div class="title">One email changes a sponsor deal. What else has to change?</div>'
            '<div class="lede">The AI helpers read the email, find every record it affects, and write a plan. '
            'A person approves the plan. The helpers make the changes, handle failures, and then check '
            'their own work.</div>', unsafe_allow_html=True)
st.caption(SCENARIOS[store.scenario["scenario_id"]][1])
if notification := st.session_state.pop("notification", None):
    st.toast(notification, icon="⚠️")
if not wf.tools.faults and store.scenario["faults"]:
    st.info("Simulated problems are off for this run. Turn them on and Reset demo to demonstrate this failure path.")

current = next((i for i, (_, stages) in enumerate(STEPS) if wf.stage in stages),
               {"needs_clarification": 1, "blocked": 1, "failed": 3, "verification_failed": 5,
                "rejected": 4 if len(wf.plans) > 1 else 2}.get(wf.stage, 0))
all_done = wf.stage == "verified" and bool(wf.replay_result)
cells = []
for i, (name, _) in enumerate(STEPS):
    cls = "done" if (all_done or i < current) else ("now" if i == current else "")
    state = "done" if cls == "done" else ("now" if cls == "now" else f"step {i + 1}")
    cells.append(f'<div class="{cls}"><span>{state}</span>{name}</div>')
st.markdown(f'<div class="steps">{"".join(cells)}</div>', unsafe_allow_html=True)


def flow_dot(active: str | None = None) -> str:
    """Agent progress follows actual log events; waiting humans are never shown as running agents."""
    nodes = ["Coordinator", "Communication", "Knowledge", "Planning", "Human", "Execution", "Verification", "Done"]
    edges = [("Coordinator", "Communication"), ("Communication", "Knowledge"), ("Knowledge", "Planning"),
             ("Planning", "Human"), ("Human", "Execution"), ("Execution", "Verification"), ("Verification", "Done")]
    if wf.stage == "needs_clarification" or "conflict" in store.scenario["scenario_id"]:
        nodes.append("Clarification")
        edges += [("Communication", "Clarification"), ("Clarification", "Communication")]
    if any(f["kind"] == "concurrent_publish" for f in wf.tools.faults):
        edges.append(("Execution", "Knowledge"))
    if any(f["kind"] in ("transient_before_write", "timeout_after_write") for f in wf.tools.faults):
        nodes.append("Recovery")
        edges += [("Execution", "Recovery"), ("Recovery", "Execution")]
    if wf.stage in ("blocked", "failed", "verification_failed") or any(
            f["kind"] in ("permanent_outage", "agent_failure") for f in wf.tools.faults):
        nodes.append("Stopped")
        edges.append(("Coordinator", "Stopped"))
    visited = {e["agent"] for e in store.logs()}
    if wf.approvals:
        visited.add("Human")
    if any(e["kind"] == "retry" or "read-back shows" in e["message"] for e in store.logs()):
        visited.add("Recovery")
    if wf.trigger_id != store.scenario["trigger_source_id"]:
        visited.add("Clarification")
    if active is None:
        active = {"ready": "Coordinator", "ingested": "Communication", "awaiting_approval": "Human",
                  "awaiting_delta_approval": "Human", "needs_clarification": "Clarification",
                  "approved": "Execution", "executed": "Verification", "verified": "Done",
                  "blocked": "Stopped", "failed": "Stopped", "verification_failed": "Stopped",
                  "rejected": "Human"}.get(wf.stage)
    lines = ['digraph flow { rankdir=LR; bgcolor="transparent"; nodesep=.2; ranksep=.3;',
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=15, margin=".16,.12"];',
             'edge [color="#94a3b8", fontcolor="#52627a", fontname="Helvetica", fontsize=10];']
    for node in nodes:
        color, fill, status = "#cbd5e1", "#ffffff", "Next"
        if node in visited:
            fill, status = "#f1f5f9", "Visited"
        if node == active:
            waiting = node in ("Human", "Clarification", "Stopped")
            color, fill = ("#b45309", "#fef3c7") if waiting else ("#4f46e5", "#eef2ff")
            status = ("Waiting" if waiting else "Active") if store.on_log else "Current"
            if node == "Done":
                color, fill = "#0f766e", "#ccfbf1"
                status = "Verified"
            elif node == "Stopped":
                color, fill = "#b91c1c", "#fee2e2"
        title = {"Human": "Human approval", "Clarification": "Human clarification",
                 "Recovery": "Retry / read-back", "Done": "Verified result", "Stopped": "Human investigation"}.get(node, node)
        lines.append(f'{json.dumps(node)} [label={json.dumps(title + chr(10) + status)}, '
                     f'color="{color}", fillcolor="{fill}", penwidth={3 if node == active else 1}];')
    for source, target in edges:
        edge_label = {("Execution", "Knowledge"): "version conflict → replan",
                      ("Execution", "Recovery"): "tool failure", ("Recovery", "Execution"): "recovered",
                      ("Communication", "Clarification"): "claims disagree",
                      ("Clarification", "Communication"): "confirmed evidence"}.get((source, target), "")
        lines.append(f'{json.dumps(source)} -> {json.dumps(target)} [label={json.dumps(edge_label, ensure_ascii=False)}];')
    return "\n".join(lines + ["}"])


def render_flow(agent: str | None = None, message: str = "") -> None:
    with flow_slot.container():
        if agent:
            st.markdown(f"**Active agent: {agent}**")
            st.caption(message)
        else:
            status = {"ready": "Ready to receive a message", "ingested": "Next: Communication",
                      "awaiting_approval": "Waiting for human approval — no agent is running",
                      "awaiting_delta_approval": "Waiting for delta approval — no agent is running",
                      "needs_clarification": "Paused for human clarification — no agent is running",
                      "approved": "Next: Execution", "executed": "Next: Verification",
                      "verified": "Verified — no agent is running", "rejected": "Stopped by organiser",
                      "blocked": "Blocked — human investigation needed", "failed": "Execution stopped",
                      "verification_failed": "Verification failed — human investigation needed"}.get(wf.stage, wf.stage)
            st.markdown(f"**{status}**")
        st.graphviz_chart(flow_dot(agent), width="stretch")


st.subheader("Live agent workflow")
flow_slot = st.empty()
render_flow()
st.caption("Indigo = current agent or next step. Amber = human attention. Teal = verified. Red = stopped. Grey = agent visited. "
           "Highlights update from real events while a step runs. Coordinator manages the whole run.")

# ---------------------------------------------------------------- numbers
aster = store.get("sponsor", "sponsor-aster")
base_aster = store.baseline("sponsor", "sponsor-aster")
fin = compute_financials(store)
dec07 = store.get("decision", "DEC-07")
k = st.columns(3) + st.columns(3)
k[0].metric("Aster's sponsorship", inr(aster["commitment_paise"]),
            delta=inr(aster["commitment_paise"] - base_aster["commitment_paise"])
            if aster["commitment_paise"] != base_aster["commitment_paise"] else None,
            delta_color="off", help="How much money Aster Labs has promised.")
k[1].metric("Aster's sponsor level", aster["tier"],
            delta="downgraded" if aster["tier"] != base_aster["tier"] else None, delta_color="off",
            help="Gold, Silver, etc. The level decides what logos and posts Aster gets.")
k[2].metric("Money left after costs", inr(fin["forecast_balance_paise"]),
            delta=inr(fin["forecast_balance_paise"] - 3000000) if fin["forecast_balance_paise"] != 3000000 else None,
            delta_color="off", help="All sponsor money promised, minus all planned expenses.")
k[3].metric("DJ upgrade (DEC-07)", dec07["status"].replace("_", " "),
            help="A decision that only goes ahead if there is enough money left.")
k[4].metric("Records changed", store.effect_count(), help="How many records the helpers have written to.")
k[5].metric("Duplicate effects", wf.replay_result["new_effects"] if wf.replay_result else "–",
            help="Changes made twice by mistake when the same email arrives again. Should be 0.")

if err := st.session_state.pop("error", None):
    st.error(err)

# Human notifications stay visible after approval: approval does not resolve a business exception.
if wf.stage == "needs_clarification":
    st.warning("**Human attention required — conflicting or unclear instructions.** "
               "Owner: organiser (Kavya), with the sponsor's authorised contacts. "
               "Planning is paused; no business records have changed.")
    for question in wf.clarification_questions:
        st.markdown(f"- {question}")
    st.info("Verify the sender's authority, the final INR amount, and an explicit confirmation replacing "
            "the conflicting proposals. Email does not automatically outrank another authorised person's WhatsApp. "
            "The confirmation must be analysed and its plan approved before execution.")
elif wf.stage in ("blocked", "failed", "verification_failed"):
    st.error("**Human attention required — workflow stopped.** Owner: organiser / operator. "
             "Do not assume pending changes succeeded.")
    problems = [e for e in store.logs() if e["kind"] in ("blocked", "error")]
    for entry in problems[-3:]:
        st.write(entry["message"])
    if wf.stage == "verification_failed":
        for check in wf.verification["checks"]:
            if not check["ok"]:
                st.write(f"Verify {check['name']}: {check['detail']}")
    st.caption(f"Already committed writes: {store.effect_count()}. Inspect the action log and source access; "
               "do not bypass privacy checks. Reset starts a fresh demo, not a recovery of this run.")
elif wf.plan and wf.stage != "rejected":
    waiting = wf.stage in ("awaiting_approval", "awaiting_delta_approval")
    st.warning("**Human attention required — " + ("approval needed.**" if waiting else "business decisions remain open.**")
               + " Approving the plan does not resolve these exceptions.")
    tasks = []
    disp = wf.plan["dispositions"]
    if disp.get("D1") == "flag_human":
        tasks.append("Design + organiser: verify print order PH-2231 with the vendor; decide how to handle the irreversible main-stage banner.")
    if disp.get("D3") == "over_delivery":
        tasks.append("Social + organiser: verify D3's published post; decide how to handle the extra benefit already delivered. Do not cancel a published post automatically.")
    if wf.plan["financials"]["forecast_balance_paise"] < 0:
        tasks.append(f"Finance: verify sponsor commitments and costs; decide how to cover the {inr(-wf.plan['financials']['forecast_balance_paise'])} deficit. No expense cuts are invented.")
    tasks.append("Finance + organiser: verify DEC-07's required surplus before deciding on the DJ upgrade; an at-risk flag is not a rejection.")
    tasks.append("Design + organiser: verify Silver sponsor-wall logo coverage; the main-stage banner is not a substitute.")
    if waiting:
        tasks.append("Organiser: review the exact changes, permissions and sponsor reply before approving. Sponsor send is a separate permission.")
    for task in tasks:
        st.markdown(f"- {task}")

# Show competing evidence together, only after it has been delivered and cleared by source access.
messages = [store.source(a["source_id"]) for a in store.scenario["activation"]
            if a["phase"] in ("trigger", "clarification")]
messages = [s for s in messages if s is not None]
if len(messages) > 1:
    with st.expander("Sponsor messages and authority — compare the evidence", expanded=True):
        for source in messages:
            sender = store.get("person", source["sender_id"]) or {}
            contacts = [c for c in store.list("contact") if c["person_id"] == source["sender_id"]
                        and c["sponsor_id"] == "sponsor-aster" and c["authority"] == "commitment_contact"]
            st.markdown(f"**{sender.get('name', 'Unknown sender')} · {source['provider'].title()}** — "
                        + ("authorised commitment contact" if contacts else "not an authorised commitment contact"))
            st.caption(f"{source['source_id']} · {source['occurred_at']}")
            st.write(source["body"])
        if wf.stage == "needs_clarification":
            st.caption("Both claims remain contested. No amount has been selected and no write is authorised.")
        elif wf.trigger_id != store.scenario["trigger_source_id"]:
            st.caption("The confirmation replaces both earlier proposals. A plan still requires organiser approval.")
        elif store.scenario["scenario_id"] == "S1-unauthorized-whatsapp":
            st.caption("The unverified competing claim is ignored as an instruction; Priya's request still needs normal approval.")

recovery = [e for e in store.logs() if e["kind"] in ("error", "retry", "conflict", "external")
            or (e["kind"] == "verify" and "read-back shows" in e["message"])]
if recovery:
    with st.expander("Failure and recovery — what actually happened", expanded=True):
        st.caption("Temporary failure → retry. Unknown write outcome → read-back. Concurrent edit → replan and fresh approval.")
        for event in recovery:
            st.write(f"**{KIND_TAG.get(event['kind'], event['kind']).upper()} · {event['agent']}** — {event['message']}")
        for op in store.ops():
            if op["attempts"] > 1 or (op["receipt"] or {}).get("reconciled"):
                st.write(f"**Confirmed outcome:** {op['target_id']} · {op['status']} · {op['attempts']} attempt(s)"
                         + (" · confirmed by read-back; no repeated write" if (op["receipt"] or {}).get("reconciled") else ""))


# ---------------------------------------------------------------- helpers
def fmt_val(field: str, v) -> str:
    if v is None:
        return "–"
    if field.endswith("_paise") and isinstance(v, int):
        return inr(v)
    if field == "entries" and isinstance(v, list):
        return f"{len(v)} entries"
    if field == "condition_evaluation" and isinstance(v, dict):
        return f"{'met' if v.get('satisfied') else 'not met'} (money left {inr(v.get('observed_paise'))})"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)[:60]
    s = str(v)
    return s if len(s) < 70 else s[:67] + "…"


def change_text(a: dict) -> str:
    if a["op"] == "create":
        return "Create: " + (a["changes"].get("title") or a["changes"].get("subject")
                             or a["changes"].get("recipient_id") or a["target_id"])
    return "; ".join(f"{f.replace('_paise', '').replace('_', ' ')}: {fmt_val(f, a['before'].get(f))} → "
                     f"{fmt_val(f, v)}" for f, v in a["changes"].items())


def plan_rows(plan: dict, show_delta: bool) -> list[dict]:
    rows = []
    for a in plan["actions"]:
        row = {"Step": a["action_id"]}
        if show_delta:
            row["Compared with v1"] = DELTA_LABEL.get(wf.delta.get(a["op_key"], ""), "")
        row.update({"Status": STATUS_LABEL.get(wf.action_status.get(a["op_key"], "pending"), ""),
                    "App": APP_NAMES.get(a["kind"], a["kind"]), "Record": a["target_id"],
                    "What changes": change_text(a), "Approval group": SCOPE_LABEL.get(a["scope"], a["scope"]),
                    "Can undo?": "yes" if a["reversible"] else "NO"})
        rows.append(row)
    return rows


def graph_dot(active_target: str | None = None) -> str:
    """Status colours supplement border styles and the words in each record label."""
    imp = wf.impact
    disp = wf.plan["dispositions"] if wf.plan else {}
    lines = ['digraph G { rankdir=LR; bgcolor="transparent"; nodesep=0.25; ranksep=0.55;',
             'node [shape=box, style="filled", fontname="Helvetica", fontsize=14, margin="0.16,0.08"];',
             'edge [fontname="Helvetica", fontsize=10, color="#94a3b8", fontcolor="#64748b", arrowsize=0.6];']
    for n in imp["nodes"]:
        nid = n["id"]
        attrs = {"fillcolor": "#f1f5f9", "color": "#d7e0eb", "fontcolor": "#64748b", "penwidth": "1"}
        if n["affected"]:
            attrs.update(fillcolor="#ffffff", color="#818cf8", fontcolor="#172b4d", penwidth="1.4")
        note_txt = None
        if n["type"] == "Deliverable":
            d = disp.get(nid)
            note_txt = DISPOSITION_LABEL.get(d) or (store.get("deliverable", nid) or {}).get("status")
            if d in ("cancel", "over_delivery"):
                attrs.update(fillcolor="#fff1f2", color="#e11d48", fontcolor="#9f1239")
            elif d == "flag_human":
                attrs.update(fillcolor="#fffbeb", color="#d97706", fontcolor="#92400e", peripheries="2", penwidth="1.6")
            elif d == "satisfied":
                attrs.update(fillcolor="#f0fdfa", color="#0d9488", fontcolor="#115e59")
        elif n["type"] == "Decision":
            note_txt = ((store.get("decision", nid) or {}).get("status") or "").replace("_", " ") or None
            if nid == "DEC-07":
                attrs.update(fillcolor="#fffbeb", color="#d97706", fontcolor="#92400e", peripheries="2", penwidth="1.6")
                note_txt = f"{note_txt}, a person must decide"
        elif nid == "budget-innovision-2026":
            attrs.update(fillcolor="#fff1f2", color="#e11d48", fontcolor="#9f1239")
            note_txt = "money short"
        elif n["type"] == "SourceMessage":
            attrs.update(fillcolor="#4f46e5", color="#4f46e5", fontcolor="#ffffff")
        if nid == active_target:
            attrs.update(color="#175cd3", fillcolor="#eaf2ff", fontcolor="#111111", penwidth="3")
            note_txt = "current operation · " + (note_txt or "record update")
        text = n["label"] + (f"\\n({note_txt})" if note_txt else "")
        text = text.replace('"', "'")
        attr_s = ", ".join(f'{k}="{v}"' for k, v in attrs.items())
        lines.append(f'"{nid}" [label="{text}", {attr_s}];')
    for e in imp["edges"]:
        style = ', style=dashed' if e["inferred"] else ""
        lines.append(f'"{e["from"]}" -> "{e["to"]}" [label="{e["relation"].lower().replace("_", " ")}"{style}];')
    lines.append("}")
    return "\n".join(lines)


def record_table(kind: str, fields: list[tuple[str, str]]) -> None:
    rows = []
    for r in store.list(kind):
        rid = next(r[f] for f in (f"{kind}_id", "calendar_id", "post_id", "draft_id") if f in r)
        writes = store.history(kind, rid)
        row = {name: fmt_val(f, r.get(f)) for f, name in fields}
        row["Version"] = r["version"]
        row["Last changed by"] = writes[-1]["actor"] if writes else "original data"
        rows.append(row)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.caption("Nothing here yet.")


# ---------------------------------------------------------------- full-width impact graph
if wf.impact:
    with st.expander("Impact map: everything this one email touches", expanded=True):
        impact_slot = st.empty()
        impact_slot.graphviz_chart(graph_dot(), width="stretch")
        st.caption("Indigo box = source message. Indigo border = affected. Amber double border = human decision. "
                   "Rose = cancellation, over-delivery or shortage. Teal = already satisfied. Grey = context. "
                   "Dashed line = inferred link. Blue outline during execution = current record.")
else:
    impact_slot = st.empty()

left, right = st.columns([3, 2], gap="large")

# ---------------------------------------------------------------- left: next step + details
with left:
    box = st.container(border=True)
    stage = wf.stage
    with box:
        if stage == "ready":
            st.subheader("Step 1. An email is about to arrive")
            st.write("Aster Labs is one of the fest's main sponsors. Their contact, Priya, is about to email "
                     "the organisers. Right now every app (tracker, budget, docs, chat, calendar) shows the "
                     "situation *before* her email.")
            if st.button("Deliver Priya's email", type="primary", width="stretch"):
                run_step(deliver_messages)
        elif stage == "ingested":
            src = store.source(wf.trigger_id)
            st.subheader("Step 2. The email has arrived")
            st.markdown(f'<div class="msg trigger"><span class="meta">From Priya Nair, Aster Labs · Gmail · '
                        f'{src["occurred_at"][:16].replace("T", " ")}</span>{html.escape(src["body"])}</div>',
                        unsafe_allow_html=True)
            st.write("Next, the AI helpers read it, work out what it means, and find every record it affects.")
            if st.button("Run the agents", type="primary", width="stretch"):
                with st.spinner("Reading the email and tracing what it affects…"):
                    run_step(wf.analyze)
        elif stage == "awaiting_approval":
            p = wf.plan
            st.subheader(f"Step 3. The plan has {len(p['actions'])} changes. Approve it?")
            note(f"<b>What the email says:</b> {html.escape(wf.proposal['summary'])}<br>"
                 "Nothing has been changed yet.")
            info = wf.proposal.get("llm")
            if info is None:
                st.caption("Read by fixed rules (Gemini AI is off).")
            elif info["status"] == "agree":
                st.caption(f"Read by Gemini ({info['model']}) and checked against the email text and the "
                           "fixed rules. Both agree.")
            elif info["status"] == "skipped":
                st.caption("Gemini skipped because the sender could not be confirmed. Fixed rules used.")
            else:
                st.caption(f"Gemini's answer was not used ({info['status']}). The fixed-rule reading is kept.")
            if p["flags"]:
                note("<b>The AI will not decide these. A person has to:</b>" + bullet_list(p["flags"]), soft=True)
            label("Proposed changes")
            st.dataframe(plan_rows(p, False), hide_index=True, width="stretch")
            label("What are the helpers allowed to do?")
            c1, c2, c3 = st.columns(3)
            s1 = c1.checkbox("Business records", value=True, help="Tracker, budget, decisions, docs, calendar.")
            s2 = c2.checkbox("Internal notifications", value=True, help="Messages to teammates in team chat.")
            s3 = c3.checkbox("Send to sponsor", value=False,
                             help="If unticked, the reply to the sponsor is saved as a draft and not sent.")
            scopes = [s for s, on in (("business_records", s1), ("internal_notifications", s2),
                                      ("sponsor_send", s3)) if on]
            b1, b2 = st.columns([3, 1])
            if b1.button("Approve as organiser (Kavya)", type="primary", width="stretch"):
                run_step(wf.approve, scopes)
            if b2.button("Reject", width="stretch"):
                run_step(wf.reject)
        elif stage == "approved":
            p = wf.plan
            st.subheader(f"Step 4. Make the approved changes ({p['plan_id']})")
            st.write("The Execution helper makes the approved changes one at a time, checking record versions "
                     "before each write. Watch the live workflow and recovery panel for this scenario's events.")
            if st.button("Execute approved plan", type="primary", width="stretch"):
                run_step(wf.execute)
        elif stage == "awaiting_delta_approval":
            p = wf.plan
            v1_scopes = wf.approvals[0]["scopes"] if wf.approvals else ["business_records", "internal_notifications"]
            n_new = sum(1 for a in p["actions"] if wf.delta.get(a["op_key"]) == "needs_approval"
                        and a["scope"] in v1_scopes)
            st.subheader("Step 5. Someone changed things mid-way, so the plan was updated")
            note("<b>What happened:</b> while we were about to cancel social post D3, Rohan published it "
                 "himself. Our change was refused, so nothing of his was overwritten. The helpers looked at "
                 "the new situation and wrote plan v2.")
            st.write(f"Only the **{n_new} new or changed steps** need your OK. Steps already done are not "
                     "done again.")
            if p["flags"]:
                note("<b>Still for a person to decide:</b>" + bullet_list(p["flags"]), soft=True)
            label("Plan v2")
            st.dataframe(plan_rows(p, True), hide_index=True, width="stretch")
            b1, b2 = st.columns([3, 1])
            if b1.button(f"Approve {n_new} changed actions", type="primary", width="stretch"):
                run_step(wf.approve_delta, v1_scopes)
            if b2.button("Reject v2", width="stretch"):
                run_step(wf.reject)
        elif stage == "executed":
            st.subheader("Step 6. Double-check by reading everything back")
            st.write("An app saying \"OK\" is not proof. The Verification helper opens every changed record "
                     "again and recalculates the budget from scratch.")
            if st.button("Verify the results", type="primary", width="stretch"):
                run_step(wf.verify)
        elif stage == "verified":
            v = wf.verification
            st.subheader(f"Checked: {v['passed']} passed, {v['failed']} failed")
            if wf.replay_result:
                r = wf.replay_result
                note(f"<b>Repeat test:</b> the same email was delivered {r['deliveries']} more times. "
                     f"{r['duplicates_ignored']} were recognised as repeats, {r['actions_reused']} steps were "
                     f"skipped because they were already done, and <b>{r['new_effects']} records changed "
                     f"again</b>.")
            else:
                st.write("Step 7. Emails sometimes arrive twice. Send the same email 10 more times and check "
                         "that nothing is done twice.")
                if st.button("Replay the email 10 times", type="primary", width="stretch"):
                    run_step(wf.replay, 10)
            if wf.plan["flags"]:
                note("<b>Left for a person on purpose (not quietly fixed by the AI):</b>"
                     + bullet_list(wf.plan["flags"]), soft=True)
        elif stage == "needs_clarification":
            st.subheader("Paused: obtain a confirmed sponsor instruction")
            st.write("Compare the messages above. The organiser must ask the authorised contacts to reconcile "
                     "their proposals; this screen cannot pick a winner on their behalf.")
            clarifications = [a["source_id"] for a in store.scenario["activation"] if a["phase"] == "clarification"]
            if clarifications:
                st.caption("Demo continuation: a prepared follow-up from Priya explicitly replaces both proposals. "
                           "This simulates receiving a sponsor message; it does not send an email.")
                if st.button("Deliver sponsor confirmation", type="primary", width="stretch"):
                    run_step(wf.clarify, clarifications[0])
            else:
                st.info("No confirmation has arrived in this scenario. To demonstrate resuming, select "
                        "'Contact conflict → confirmation → resume' in Demo workflow.")
        else:
            msgs = {"rejected": "Plan rejected. No further changes will run. "
                                + ("Earlier committed changes remain; rejecting a delta does not roll them back."
                                   if store.effect_count() else "No business records were changed."),
                    "blocked": "Stopped safely: the sender could not be confirmed, the message could not be "
                               "read, or a privacy check failed. Nothing was changed. See the timeline.",
                    "needs_clarification": "Paused before planning. Nothing was changed. Questions for the "
                                           "organiser:" + bullet_list(wf.clarification_questions),
                    "failed": "Stopped safely while making changes. See the timeline.",
                    "verification_failed": "The double-check found problems. See the Checks tab."}
            text = msgs.get(stage, f"Stage: {html.escape(stage)}")
            note(text if "<ul>" in text else html.escape(text))
            if stage in ("failed",) and st.button("Verify anyway"):
                run_step(wf.verify)
            if st.button("Start again", type="primary"):
                new_workflow()
                st.rerun()

    tabs = st.tabs(["How it spreads", "Plan", "Workspace apps", "Inbox", "Checks", "Action log"])
    with tabs[0]:
        if wf.impact:
            st.caption("Each line is one chain of links, from the sponsor to something that has to change.")
            st.markdown("\n".join(f"- `{p}`" for p in wf.impact["paths"]))
        else:
            st.caption("Run the agents to see how the change spreads.")
    with tabs[1]:
        if wf.plans:
            for p in reversed(wf.plans):
                st.markdown(f"**{p['plan_id']}**" + (f" (replaces {p['parent_plan_id']})" if p["parent_plan_id"] else ""))
                st.dataframe(plan_rows(p, p["version"] > 1), hide_index=True, width="stretch")
                st.caption("Decision per deliverable: " + ", ".join(
                    f"{k}: {DISPOSITION_LABEL.get(v, v.replace('_', ' '))}" for k, v in p["dispositions"].items()))
        else:
            st.caption("No plan yet.")
    with tabs[2]:
        st.caption("These are the team's apps. Watch them change after you approve and execute.")
        at = st.tabs(["Sponsor tracker", "Deliverables", "Decisions", "Docs", "Calendar", "Team chat", "Email drafts"])
        with at[0]:
            record_table("sponsor", [("name", "Sponsor"), ("commitment_paise", "Promised"), ("tier", "Level"),
                                     ("cash_received_paise", "Received so far")])
            st.caption(f"Budget: money promised {inr(fin['total_commitments_paise'])} − planned costs "
                       f"{inr(fin['planned_expenses_paise'])} = money left **{inr(fin['forecast_balance_paise'])}**")
        with at[1]:
            record_table("deliverable", [("deliverable_id", "ID"), ("kind", "What"), ("status", "Status"),
                                         ("reversible", "Can undo?"), ("owner_id", "Owner"),
                                         ("external_ref", "Vendor ref")])
        with at[2]:
            record_table("decision", [("decision_id", "ID"), ("title", "Decision"), ("status", "Status"),
                                      ("superseded_by", "Replaced by"), ("condition_evaluation", "Condition")])
        with at[3]:
            for did in ("doc-aster-benefits", "doc-run-sheet"):
                d = store.get("document", did)
                st.markdown(f"**{d['title']}** · version {d['version']}")
                st.markdown("\n".join(f"- {e['text']}" for e in d["entries"]))
        with at[4]:
            record_table("calendar", [("title", "Event"), ("starts_at", "Starts"), ("ends_at", "Ends"),
                                      ("owner_id", "Owner")])
        with at[5]:
            posts = store.list("post")
            for p in posts:
                person = store.get("person", p["recipient_id"]) or {}
                st.markdown(f'<div class="msg"><span class="meta">To {html.escape(person.get("name", p["recipient_id"]))}'
                            f' · {html.escape(person.get("role", ""))}</span>{html.escape(p["text"])}</div>',
                            unsafe_allow_html=True)
            if not posts:
                st.caption("No team messages yet.")
        with at[6]:
            for d in store.list("draft"):
                st.markdown(f"**{d['subject']}** · {'sent' if d.get('sent') else 'draft, not sent'}")
                st.markdown(f'<div class="msg">{html.escape(d["body"])}</div>', unsafe_allow_html=True)
            if not store.list("draft"):
                st.caption("No drafts yet.")
    with tabs[3]:
        st.caption("Emails and chat messages the helpers are allowed to read. The new email has an indigo border.")
        srcs = [s for s in store.visible_sources() if s["source_system"] in ("mail", "team_chat")]
        for s in sorted(srcs, key=lambda s: s["occurred_at"], reverse=True):
            sender = store.get("person", s["sender_id"]) or {}
            trig = " trigger" if s["source_id"] == wf.trigger_id else ""
            st.markdown(f'<div class="msg{trig}"><span class="meta">{s["provider"].title()} · '
                        f'{html.escape(sender.get("name", s["sender_id"] or "unknown"))} · '
                        f'{s["occurred_at"][:16].replace("T", " ")} · {s["source_id"]}</span>'
                        f'{html.escape(s["body"])}</div>', unsafe_allow_html=True)
    with tabs[4]:
        if wf.verification:
            st.markdown("".join(
                f'<div class="check"><b class="{"pass" if c["ok"] else "fail"}">{"PASS" if c["ok"] else "FAIL"}</b>'
                f'<b>{html.escape(c["name"])}</b> · {html.escape(str(c["detail"]))}</div>'
                for c in wf.verification["checks"]), unsafe_allow_html=True)
        else:
            st.caption("Not verified yet.")
        if wf.replay_result:
            label("Repeat test, raw result")
            st.json(wf.replay_result)
    with tabs[5]:
        ops = store.ops()
        if ops:
            st.dataframe([{"Action key": o["op_key"], "Tool": o["tool"], "Record": o["target_id"],
                           "Result": o["status"], "Tries": o["attempts"]} for o in ops],
                         hide_index=True, width="stretch")
            st.caption("Every change gets a key made from exactly what it does. If the same key comes up again, "
                       "the helpers know it is already done and skip it. That is how repeats cause no damage.")
        else:
            st.caption("No operations yet.")

# ---------------------------------------------------------------- right: agent timeline
with right:
    st.subheader("What the helpers did")
    st.caption("Newest at the top. Every step, app call, retry, clash and approval is recorded here.")
    logs = store.logs()
    seen = st.session_state.get("seen", 0)
    feed = st.container(height=760, border=False)
    display = list(reversed(logs))
    new_count = len(logs) - seen if (seen > 0 and st.session_state.get("animate", True)) else 0

    def render(slot, entry: dict) -> None:
        kind = entry["kind"]
        tag = f'<span class="tag">{KIND_TAG[kind]}</span>' if kind in KIND_TAG else ""
        cls = ("tl strong" if kind in KIND_STRONG else "tl") + f" event-{html.escape(kind, quote=True)}"
        slot.markdown(
            f'<div class="{cls}"><span class="who">{html.escape(entry["agent"])}</span>'
            f'<span class="when">{entry["at"][11:19]}</span>{tag}<br>'
            f'{html.escape(entry["message"])}</div>', unsafe_allow_html=True)

    with feed:
        slots = [st.empty() for _ in display]
        for i in range(new_count, len(display)):
            render(slots[i], display[i])
        for i in range(new_count - 1, -1, -1):   # new entries appear one by one, oldest first
            time.sleep(0.18)
            render(slots[i], display[i])
    st.session_state.seen = len(logs)
