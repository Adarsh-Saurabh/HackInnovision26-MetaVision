"""MetaVision / Second Brain: Streamlit demo UI for scenario S1-main-demo.

Run: uv run --locked streamlit run app.py
Theme (white / black / grey) lives in .streamlit/config.toml.
"""

from __future__ import annotations

import html
import json
import re
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
STATUS_LABEL = {"pending": "Waiting", "committed": "Done", "reused": "Already done", "conflict": "Clash, stopped",
                "stopped": "Stopped", "blocked": "Blocked", "not_approved": "Not approved", "failed": "Failed"}
DELTA_LABEL = {"reuse": "Already done, not repeated", "covered": "Unchanged, already approved",
               "needs_approval": "New or changed, needs OK"}
# Which part of the problem statement each step proves (shown above the step title).
OBJECTIVE = {
    "ready": "Brief: a key sponsor changes their commitment mid-way",
    "ingested": "Objective 1 · pull out sponsor, amount and deadline from the email",
    "awaiting_approval": "Objectives 1-3 · dependencies traced across apps, plan written, human approval",
    "approved": "Objective 3 · tool failures handled with safe retries",
    "awaiting_delta_approval": "Objective 3 · adaptive replanning when conditions change",
    "executed": "Objective 3 · verification checks",
    "verified": "Objective 3 · idempotency: repeats cause no duplicate changes",
}
DISPOSITION_LABEL = {"flag_human": "a person must decide", "satisfied": "already fine",
                     "cancel": "cancel it", "over_delivery": "promised too much"}

st.markdown("""
<style>
.block-container {padding-top: 3.2rem; padding-bottom: 2rem; max-width: 1480px;}
h1, h2, h3 {letter-spacing: -0.015em;}
.eyebrow {font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; color: #6b6b6b; margin: 0;}
.title {font-size: 2.1rem; font-weight: 700; letter-spacing: -0.03em; margin: 2px 0 4px 0; line-height: 1.15;}
.lede {font-size: 1rem; color: #3a3a3a; max-width: 62rem; margin-bottom: 18px;}
.steps {display: flex; gap: 0; margin: 4px 0 22px 0; border: 1px solid #dadada;}
.steps div {flex: 1; padding: 9px 10px; font-size: .82rem; color: #8a8a8a; border-right: 1px solid #dadada;
            background: #fff;}
.steps div:last-child {border-right: none;}
.steps div span {display: block; font-size: .68rem; letter-spacing: .08em; text-transform: uppercase;}
.steps div.done {color: #111; background: #f4f4f4;}
.steps div.now {color: #fff; background: #111; font-weight: 600;}
[data-testid="stMetric"] {border: 1px solid #dadada; padding: 10px 14px; background: #fff;}
[data-testid="stMetricLabel"] p {font-size: .78rem; color: #555;}
[data-testid="stMetricValue"] {font-size: 1.45rem; font-weight: 600;}
.note {padding: 11px 14px; margin: 8px 0; background: #f4f4f4; border-left: 3px solid #111; font-size: .92rem;
       line-height: 1.45;}
.note.soft {border-left-color: #b5b5b5;}
.note ul {margin: 4px 0 0 0; padding-left: 18px;}
.label {font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; color: #6b6b6b; margin: 14px 0 4px 0;}
.msg {padding: 11px 13px; border: 1px solid #dadada; margin-bottom: 8px; white-space: pre-wrap;
      font-size: .9rem; line-height: 1.45; background: #fff;}
.msg.trigger {border: 2px solid #111;}
.msg .meta {font-size: .76rem; color: #6b6b6b; display: block; margin-bottom: 6px;}
.tl {font-size: .85rem; line-height: 1.4; padding: 7px 10px; margin: 0 0 6px 0; border-left: 2px solid #d0d0d0;}
.tl.strong {border-left: 3px solid #111; background: #f6f6f6;}
.tl .who {font-weight: 600;}
.tl .when {color: #8a8a8a; font-size: .74rem; font-family: "IBM Plex Mono", monospace; margin-left: 6px;}
.tag {display: inline-block; font-size: .64rem; letter-spacing: .06em; text-transform: uppercase;
      border: 1px solid #9a9a9a; color: #444; padding: 0 5px; margin-left: 6px; vertical-align: 1px;}
.tl.strong .tag {background: #111; color: #fff; border-color: #111;}
.check {font-size: .9rem; padding: 6px 0; border-bottom: 1px solid #ececec;}
.check b.pass, .check b.fail {display: inline-block; width: 44px; font-size: .7rem; letter-spacing: .08em;}
.check b.fail {background: #111; color: #fff; text-align: center;}
.agent {font-size: .86rem; margin: 0 0 9px 0; line-height: 1.35;}
.agent b {display: block;}
.agent span {color: #555;}
code {color: #111 !important; background: #f1f1f1 !important;}
[data-testid="stHeaderActionElements"] {display: none;}
[data-testid="stAlertContainer"] {background: #f4f4f4 !important; color: #111 !important;
                                  border-left: 3px solid #111; border-radius: 0;}
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
    st.session_state.wf = Workflow("S1-main-demo", inject_faults=st.session_state.get("faults", True))
    st.session_state.seen = 0


if "wf" not in st.session_state:
    new_workflow()
wf: Workflow = st.session_state.wf
store = wf.store


def run_step(fn, *args) -> None:
    try:
        fn(*args)
    except Exception as exc:  # keep the demo alive; show the problem instead of a stack trace
        st.session_state.error = f"{type(exc).__name__}: {exc}"
    st.rerun()


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown('<div class="eyebrow">HackInnovision 2026 · Track B</div>', unsafe_allow_html=True)
    st.markdown("### Second Brain")
    st.caption("A college fest team works across email, chat, a sponsor tracker, a budget sheet, docs and a "
               "calendar. This demo shows what happens when one sponsor changes their deal. All data is made up.")
    if st.button("Reset demo", width="stretch"):
        new_workflow()
        st.rerun()
    st.toggle("Simulate problems", value=True, key="faults",
              help="An app fails once, and a teammate edits a record at the same moment we do. "
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
    st.caption(f"Demo clock: {store.demo_now.replace('T', ' ')[11:16]} IST, {store.demo_now[:10]}")

# ---------------------------------------------------------------- header + steps
st.markdown('<div class="eyebrow">MetaVision · Second Brain</div>'
            '<div class="title">One email changes a sponsor deal. What else has to change?</div>'
            '<div class="lede">The AI helpers read the email, find every record it affects, and write a plan. '
            'A person approves the plan. The helpers make the changes, handle failures, and then check '
            'their own work.</div>', unsafe_allow_html=True)

current = next((i for i, (_, stages) in enumerate(STEPS) if wf.stage in stages), len(STEPS))
all_done = wf.stage == "verified" and bool(wf.replay_result)
cells = []
for i, (name, _) in enumerate(STEPS):
    cls = "done" if (all_done or i < current) else ("now" if i == current else "")
    state = "done" if cls == "done" else ("now" if cls == "now" else f"step {i + 1}")
    cells.append(f'<div class="{cls}"><span>{state}</span>{name}</div>')
st.markdown(f'<div class="steps">{"".join(cells)}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- numbers
aster = store.get("sponsor", "sponsor-aster")
base_aster = store.baseline("sponsor", "sponsor-aster")
fin = compute_financials(store)
dec07 = store.get("decision", "DEC-07")
k = st.columns(6)
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
k[3].metric("DJ upgrade decision", dec07["status"].replace("_", " "),
            help="A decision that only goes ahead if there is enough money left.")
k[4].metric("Records changed", store.effect_count(), help="How many records the helpers have written to.")
k[5].metric("Duplicate effects", wf.replay_result["new_effects"] if wf.replay_result else "–",
            help="Changes made twice by mistake when the same email arrives again. Should be 0.")

if err := st.session_state.pop("error", None):
    st.error(err)


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


def record_name(a: dict) -> str:
    """Human name for an action's target record, falling back to its ID."""
    rec = store.get(a["kind"], a["target_id"]) or a["changes"]
    if a["kind"] == "post":
        person = store.get("person", rec.get("recipient_id", "")) or {}
        return f"Message to {person.get('name', rec.get('recipient_id'))}"
    if a["kind"] == "deliverable":
        return f"{a['target_id']} {rec.get('kind', '').replace('_', ' ')}"
    if a["kind"] == "decision":
        return f"{a['target_id']}: {rec.get('title', '')}"
    for f in ("name", "title", "subject"):
        if rec.get(f):
            return str(rec[f])
    return a["target_id"]


def plan_rows(plan: dict, show_delta: bool) -> list[dict]:
    rows = []
    for a in plan["actions"]:
        row = {"Step": a["action_id"]}
        if show_delta:
            row["Compared with v1"] = DELTA_LABEL.get(wf.delta.get(a["op_key"], ""), "")
        row.update({"Status": STATUS_LABEL.get(wf.action_status.get(a["op_key"], "pending"), ""),
                    "App": APP_NAMES.get(a["kind"], a["kind"]), "Record": record_name(a),
                    "What changes": change_text(a), "Approval group": SCOPE_LABEL.get(a["scope"], a["scope"]),
                    "Can undo?": "yes" if a["reversible"] else "NO"})
        rows.append(row)
    return rows


def graph_dot() -> str:
    """Grayscale impact graph. Meaning is carried by fill, border weight and a word in the label."""
    imp = wf.impact
    disp = wf.plan["dispositions"] if wf.plan else {}
    lines = ['digraph G { rankdir=LR; bgcolor="transparent"; nodesep=0.25; ranksep=0.55;',
             'node [shape=box, style="filled", fontname="Helvetica", fontsize=14, margin="0.16,0.08"];',
             'edge [fontname="Helvetica", fontsize=10, color="#9a9a9a", fontcolor="#7a7a7a", arrowsize=0.6];']
    for n in imp["nodes"]:
        nid = n["id"]
        attrs = {"fillcolor": "#f1f1f1", "color": "#c4c4c4", "fontcolor": "#7a7a7a", "penwidth": "1"}
        if n["affected"]:
            attrs.update(fillcolor="#ffffff", color="#111111", fontcolor="#111111", penwidth="1.4")
        note_txt = None
        if n["type"] == "Deliverable":
            d = disp.get(nid)
            note_txt = DISPOSITION_LABEL.get(d) or (store.get("deliverable", nid) or {}).get("status")
            if d in ("cancel", "over_delivery"):
                attrs.update(fillcolor="#5a5a5a", color="#5a5a5a", fontcolor="#ffffff")
            elif d == "flag_human":
                attrs.update(peripheries="2", penwidth="1.6")
        elif n["type"] == "Decision":
            note_txt = ((store.get("decision", nid) or {}).get("status") or "").replace("_", " ") or None
            if nid == "DEC-07":
                attrs.update(peripheries="2", penwidth="1.6")
                note_txt = f"{note_txt}, a person must decide"
        elif nid == "budget-innovision-2026":
            attrs.update(fillcolor="#5a5a5a", color="#5a5a5a", fontcolor="#ffffff")
            note_txt = "money short"
        elif n["type"] == "SourceMessage":
            attrs.update(fillcolor="#111111", color="#111111", fontcolor="#ffffff")
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
        st.graphviz_chart(graph_dot(), width="stretch")
        st.caption("Black box = the email. White box with dark border = affected. Double border = a person "
                   "must decide. Dark grey = to be cancelled, or money is short. Light grey = related but not "
                   "affected. Dashed line = a link the AI guessed from a chat message.")

left, right = st.columns([3, 2], gap="large")

# ---------------------------------------------------------------- left: next step + details
with left:
    box = st.container(border=True)
    stage = wf.stage
    with box:
        if stage in OBJECTIVE:
            label(OBJECTIVE[stage])
        if stage == "ready":
            st.subheader("Step 1. An email is about to arrive")
            st.write("Aster Labs is one of the fest's main sponsors. Their contact, Priya, is about to email "
                     "the organisers. Right now every app (tracker, budget, docs, chat, calendar) shows the "
                     "situation *before* her email.")
            if st.button("Deliver Priya's email", type="primary", width="stretch"):
                run_step(wf.ingest)
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
            st.subheader(f"Step 4. Make the approved changes (plan v{p['version']})")
            st.write("The Execution helper makes the changes one at a time. Before each write it checks that "
                     "nobody else changed the record. With 'Simulate problems' on, one app will fail once "
                     "and a teammate will edit a post at the same moment.")
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
        else:
            msgs = {"rejected": "Plan rejected. No business records were changed by it.",
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
            st.caption("Each line is one chain of links, from the sponsor to something that has to change. "
                       "The same chains are drawn in the impact map above.")
            names = {n["id"]: n["label"] for n in wf.impact["nodes"]}
            pattern = re.compile("|".join(re.escape(i) for i in sorted(names, key=len, reverse=True)))
            st.markdown("\n".join(
                "- " + html.escape(pattern.sub(lambda m: names[m.group(0)], p)) for p in wf.impact["paths"]),
                unsafe_allow_html=True)
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
        st.caption("Emails and chat messages the helpers are allowed to read. The new email has a black border.")
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
            st.caption("Each changed record is opened again and compared with what the plan said. "
                       "Then the budget is recalculated and unrelated records are checked for accidental changes.")
            summaries = {a["action_id"]: a.get("summary") for p in wf.plans for a in p["actions"]}

            def check_name(name: str) -> str:
                aid = name.split(" ", 1)[0]
                return f"Step {aid}: {summaries[aid]}" if summaries.get(aid) else name

            st.markdown("".join(
                f'<div class="check"><b class="{"pass" if c["ok"] else "fail"}">{"PASS" if c["ok"] else "FAIL"}</b>'
                f'<b>{html.escape(check_name(c["name"]))}</b> · {html.escape(str(c["detail"]))}</div>'
                for c in wf.verification["checks"]), unsafe_allow_html=True)
        else:
            st.caption("Not verified yet.")
        if wf.replay_result:
            with st.expander("Repeat test, raw numbers"):
                st.json(wf.replay_result)
    with tabs[5]:
        ops = store.ops()
        if ops:
            st.dataframe([{"App": APP_NAMES.get(o["kind"], o["kind"]), "Record": o["target_id"],
                           "Result": o["status"], "Tries": o["attempts"], "Action key": o["op_key"]} for o in ops],
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
        cls = "tl strong" if kind in KIND_STRONG else "tl"
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
