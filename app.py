"""MetaVision / Second Brain: Streamlit demo UI for scenario S1-main-demo.

Run: uv run --locked streamlit run app.py
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

st.set_page_config(page_title="MetaVision · Second Brain", page_icon="🧠", layout="wide")

AGENT_ICON = {"Communication": "📨", "Knowledge": "🧠", "Planning": "🗺️", "Execution": "⚙️",
              "Verification": "🔍", "Coordinator": "🧭", "External": "👤"}
KIND_COLOR = {"error": "#d9534f", "conflict": "#e8590c", "retry": "#f0ad4e", "write": "#2f9e44",
              "reuse": "#868e96", "approval": "#1c7ed6", "verified": "#2f9e44", "verify": "#2f9e44",
              "external": "#c2255c", "flag": "#f08c00", "trigger": "#7048e8", "blocked": "#d9534f",
              "replay": "#0c8599", "inference": "#7048e8", "llm": "#7048e8"}
STEPS = [("Message in", {"ready"}),
         ("Agents analyse", {"ingested"}),
         ("Human approval", {"awaiting_approval"}),
         ("Execute", {"approved", "executing"}),
         ("Re-plan + delta approval", {"awaiting_delta_approval"}),
         ("Verify", {"executed"}),
         ("Replay test", {"verified"})]
STATUS_BADGE = {"pending": "⏳ pending", "committed": "✅ done", "reused": "♻️ reused", "conflict": "⛔ conflict",
                "stopped": "⏸ stopped", "blocked": "🚫 blocked", "not_approved": "— not approved",
                "failed": "❌ failed"}
DELTA_BADGE = {"reuse": "♻️ already done, reused", "covered": "☑️ unchanged, v1 approval",
               "needs_approval": "🆕 changed, needs approval"}

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 1rem;}
.tl {font-size: 0.86rem; line-height: 1.35; padding: 6px 8px; margin: 3px 0; border-radius: 6px;
     background: rgba(127,127,127,0.07); border-left: 4px solid #adb5bd;}
.tl b {font-weight: 600;}
.step {text-align:center; padding: 6px 4px; border-radius: 8px; font-size: 0.82rem;
       border: 1px solid rgba(127,127,127,0.25);}
.step.done {background: rgba(47,158,68,0.15); border-color: #2f9e44;}
.step.now {background: rgba(28,126,214,0.18); border-color: #1c7ed6; font-weight: 700;}
.msg {padding: 10px 12px; border-radius: 8px; background: rgba(127,127,127,0.08); margin-bottom: 8px;
      white-space: pre-wrap; font-size: 0.9rem;}
.msg.trigger {border: 2px solid #7048e8;}
</style>
""", unsafe_allow_html=True)


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
    st.header("🧠 Second Brain")
    st.caption("HackInnovision 2026 · Track B · scenario S1-main-demo (synthetic data)")
    st.toggle("Inject faults (tracker failure + teammate edit)", value=True, key="faults",
              help="Applies on reset.")
    st.toggle("Animate agent timeline", value=True, key="animate")
    st.toggle(f"Live Gemini extraction ({llm.model_name()})", value=llm.live_default(), key="llm",
              disabled=not llm.live_available(),
              help="Gemini interprets the email; its answer is only used if it is grounded in the message "
                   "text and matches the rule-based extraction. Off = rules only, no API calls."
                   + ("" if llm.live_available() else " No GEMINI_API_KEY in .env."))
    if wf.stage in ("ready", "ingested"):
        wf.use_llm = bool(st.session_state.get("llm")) and llm.live_available()
    if st.button("↺ Reset demo", width="stretch"):
        new_workflow()
        st.rerun()
    st.divider()
    st.markdown("**Agents**")
    for name, icon in AGENT_ICON.items():
        if name != "External":
            st.markdown(f"{icon} {name}")
    st.divider()
    st.caption(f"Simulated now: {store.demo_now.replace('T', ' ')[:16]} IST · stage `{wf.stage}`")

# ---------------------------------------------------------------- header + stepper
st.title("MetaVision · Second Brain")
st.caption("One sponsor email → six AI agents trace the impact across tracker, budget, decisions, docs, "
           "calendar and chat → a human approves → changes are executed, recovered, verified and audited.")

current = next((i for i, (_, stages) in enumerate(STEPS) if wf.stage in stages), len(STEPS))
cols = st.columns(len(STEPS))
for i, (label, _) in enumerate(STEPS):
    if wf.stage == "verified" and wf.replay_result:
        cls = "done"
    else:
        cls = "done" if i < current else ("now" if i == current else "")
    mark = "✓ " if cls == "done" else ("● " if cls == "now" else "")
    cols[i].markdown(f'<div class="step {cls}">{mark}{label}</div>', unsafe_allow_html=True)
st.write("")

# ---------------------------------------------------------------- KPIs
aster = store.get("sponsor", "sponsor-aster")
base_aster = store.baseline("sponsor", "sponsor-aster")
fin = compute_financials(store)
dec07 = store.get("decision", "DEC-07")
k = st.columns(6)
k[0].metric("Aster commitment", inr(aster["commitment_paise"]),
            delta=inr(aster["commitment_paise"] - base_aster["commitment_paise"])
            if aster["commitment_paise"] != base_aster["commitment_paise"] else None)
k[1].metric("Aster tier", aster["tier"], delta="downgraded" if aster["tier"] != base_aster["tier"] else None,
            delta_color="inverse")
k[2].metric("Forecast balance", inr(fin["forecast_balance_paise"]),
            delta=inr(fin["forecast_balance_paise"] - 3000000) if fin["forecast_balance_paise"] != 3000000 else None)
k[3].metric("DEC-07 (DJ upgrade)", dec07["status"].replace("_", " "))
k[4].metric("Records changed", store.effect_count())
k[5].metric("Duplicate effects", wf.replay_result["new_effects"] if wf.replay_result else "–")

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
        return f"satisfied={v.get('satisfied')} (balance {inr(v.get('observed_paise'))})"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)[:60]
    s = str(v)
    return s if len(s) < 70 else s[:67] + "…"


def change_text(a: dict) -> str:
    if a["op"] == "create":
        return "create " + (a["changes"].get("title") or a["changes"].get("subject")
                            or a["changes"].get("recipient_id") or a["target_id"])
    return "; ".join(f"{f}: {fmt_val(f, a['before'].get(f))} → {fmt_val(f, v)}" for f, v in a["changes"].items())


def plan_rows(plan: dict, show_delta: bool) -> list[dict]:
    rows = []
    for a in plan["actions"]:
        row = {"#": a["action_id"], "App": APP_NAMES.get(a["kind"], a["kind"]), "Target": a["target_id"],
               "Change": change_text(a), "Scope": a["scope"].replace("_", " "),
               "Reversible": "yes" if a["reversible"] else "NO",
               "Status": STATUS_BADGE.get(wf.action_status.get(a["op_key"], "pending"), "")}
        if show_delta:
            row["v2 delta"] = DELTA_BADGE.get(wf.delta.get(a["op_key"], ""), "")
        rows.append(row)
    return rows


def graph_dot() -> str:
    imp = wf.impact
    disp = wf.plan["dispositions"] if wf.plan else {}
    lines = ['digraph G { rankdir=LR; bgcolor="transparent"; nodesep=0.25; ranksep=0.5;',
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=12, color="#495057"];',
             'edge [fontname="Helvetica", fontsize=9, color="#868e96", fontcolor="#868e96"];']
    for n in imp["nodes"]:
        nid = n["id"]
        fill = "#e9ecef"
        if n["affected"]:
            fill = "#d0ebff"
        rec_status = None
        if n["type"] == "Deliverable":
            rec_status = (store.get("deliverable", nid) or {}).get("status")
            d = disp.get(nid)
            fill = {"flag_human": "#ffe066", "satisfied": "#b2f2bb", "cancel": "#ffc9c9",
                    "over_delivery": "#ffa8a8"}.get(d, fill)
        elif n["type"] == "Decision":
            rec_status = (store.get("decision", nid) or {}).get("status")
            if nid == "DEC-07":
                fill = "#ffe066"
        elif nid == "budget-innovision-2026":
            fill = "#ffc9c9"
        elif n["type"] == "SourceMessage":
            fill = "#e5dbff"
        label = n["label"] + (f"\\n[{rec_status}]" if rec_status else "")
        label = label.replace('"', "'")
        pen = "2" if n["affected"] else "1"
        lines.append(f'"{nid}" [label="{label}", fillcolor="{fill}", penwidth={pen}];')
    for e in imp["edges"]:
        style = 'style=dashed, color="#7048e8", fontcolor="#7048e8"' if e["inferred"] else ""
        lines.append(f'"{e["from"]}" -> "{e["to"]}" [label="{e["relation"]}" {style}];')
    lines.append("}")
    return "\n".join(lines)


def record_table(kind: str, fields: list[str]) -> None:
    rows = []
    for r in store.list(kind):
        rid = next(r[f] for f in (f"{kind}_id", "calendar_id", "post_id", "draft_id") if f in r)
        writes = store.history(kind, rid)
        row = {f: fmt_val(f, r.get(f)) for f in fields}
        row["version"] = r["version"]
        row["last changed by"] = writes[-1]["actor"] if writes else "baseline"
        rows.append(row)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.caption("Nothing here yet.")


# ---------------------------------------------------------------- full-width impact graph
if wf.impact:
    with st.expander("🕸 Impact graph: what this one email touches", expanded=True):
        st.graphviz_chart(graph_dot(), width="stretch")
        st.caption("Blue = affected · yellow = needs human · red = cancelled / deficit / over-delivery · "
                   "green = satisfied · dashed purple = link inferred from chat · grey = context, not affected")

left, right = st.columns([3, 2], gap="large")

# ---------------------------------------------------------------- left: next step + details
with left:
    box = st.container(border=True)
    stage = wf.stage
    with box:
        if stage == "ready":
            st.subheader("1 · A message arrives")
            st.write("Aster Labs' sponsor contact is about to email the organiser. Everything else in the "
                     "workspace (tracker, budget, docs, chat, calendar) is in its *before* state.")
            if st.button("📩 Deliver Priya's email", type="primary", width="stretch"):
                run_step(wf.ingest)
        elif stage == "ingested":
            src = store.source(wf.trigger_id)
            st.subheader("2 · New email received")
            st.markdown(f'<div class="msg trigger"><b>From:</b> Priya Nair (Aster Labs) · Gmail · '
                        f'{src["occurred_at"][:16].replace("T", " ")}<br><br>{html.escape(src["body"])}</div>',
                        unsafe_allow_html=True)
            if st.button("🧠 Run the agents", type="primary", width="stretch"):
                with st.spinner("Agents reading the message and tracing the impact…"):
                    run_step(wf.analyze)
        elif stage == "awaiting_approval":
            p = wf.plan
            st.subheader(f"3 · Plan v1 needs your approval ({len(p['actions'])} actions)")
            st.info(f"**{wf.proposal['summary']}**  \nNothing has been changed yet.")
            info = wf.proposal.get("llm")
            if info is None:
                st.caption("🔎 Extracted by deterministic rules (live Gemini off)")
            elif info["status"] == "agree":
                st.caption(f"✨ Read by Gemini `{info['model']}`, checked against the message text and the "
                           "rule-based extraction: they agree")
            elif info["status"] == "skipped":
                st.caption("🔒 Gemini skipped (sender not verified); rule-based extraction used")
            else:
                st.caption(f"⚠️ Gemini result not used ({info['status']}); grounded rule-based extraction kept")
            for f in p["flags"]:
                st.warning(f, icon="⚠️")
            st.dataframe(plan_rows(p, False), hide_index=True, width="stretch")
            c1, c2, c3 = st.columns(3)
            s1 = c1.checkbox("Business records", value=True)
            s2 = c2.checkbox("Internal notifications", value=True)
            s3 = c3.checkbox("Send to sponsor", value=False, help="Unchecked: the sponsor reply stays a draft.")
            scopes = [s for s, on in (("business_records", s1), ("internal_notifications", s2),
                                      ("sponsor_send", s3)) if on]
            b1, b2 = st.columns([3, 1])
            if b1.button("✅ Approve as organiser (Kavya)", type="primary", width="stretch"):
                run_step(wf.approve, scopes)
            if b2.button("Reject", width="stretch"):
                run_step(wf.reject)
        elif stage == "approved":
            p = wf.plan
            st.subheader(f"4 · Execute {p['plan_id']}")
            st.write("The Execution agent applies approved actions one by one, with version checks and "
                     "idempotency keys. Faults are injected on purpose.")
            if st.button("▶ Execute approved plan", type="primary", width="stretch"):
                run_step(wf.execute)
        elif stage == "awaiting_delta_approval":
            p = wf.plan
            v1_scopes = wf.approvals[0]["scopes"] if wf.approvals else ["business_records", "internal_notifications"]
            n_new = sum(1 for a in p["actions"] if wf.delta.get(a["op_key"]) == "needs_approval"
                        and a["scope"] in v1_scopes)
            st.subheader("5 · The world changed mid-run: plan v2")
            st.error("Rohan published D3 directly in the social tool while we were about to cancel it. "
                     "Our write was refused (version conflict), nothing was overwritten, and the agents "
                     "re-planned from fresh state.", icon="⛔")
            st.write(f"Only the **{n_new} changed actions** need fresh approval; work already done is reused, "
                     "never repeated.")
            for f in p["flags"]:
                st.warning(f, icon="⚠️")
            st.dataframe(plan_rows(p, True), hide_index=True, width="stretch")
            b1, b2 = st.columns([3, 1])
            if b1.button(f"✅ Approve {n_new} changed actions", type="primary", width="stretch"):
                run_step(wf.approve_delta, v1_scopes)
            if b2.button("Reject v2", width="stretch"):
                run_step(wf.reject)
        elif stage == "executed":
            st.subheader("6 · Verify by reading everything back")
            st.write("A tool saying OK is not proof. The Verification agent re-reads each changed record "
                     "and recomputes the money from scratch.")
            if st.button("🔍 Verify", type="primary", width="stretch"):
                run_step(wf.verify)
        elif stage == "verified":
            v = wf.verification
            st.subheader(f"✅ Verified: {v['passed']} checks passed, {v['failed']} failed")
            if wf.replay_result:
                r = wf.replay_result
                st.success(f"Replay: the same email delivered {r['deliveries']} more times → "
                           f"{r['duplicates_ignored']} recognised as duplicates, {r['actions_reused']} actions "
                           f"reused from the ledger, **{r['new_effects']} new effects**.")
            else:
                st.write("7 · Reliability test: deliver the same email again, many times.")
                if st.button("🔁 Replay the email ×10", type="primary", width="stretch"):
                    run_step(wf.replay, 10)
            st.markdown("**Still needs a human (flagged, not silently fixed):**")
            for f in wf.plan["flags"]:
                st.markdown(f"- {f}")
        else:
            msgs = {"rejected": ("info", "Plan rejected. Business records were not changed by the rejected plan."),
                    "blocked": ("warning", "Sender not authorised: clarification needed, nothing changed."),
                    "failed": ("error", "Execution stopped safely; see the timeline."),
                    "verification_failed": ("error", "Verification found problems; see the Verification tab.")}
            kind, text = msgs.get(stage, ("info", f"Stage: {stage}"))
            getattr(st, kind)(text)
            if stage in ("failed",) and st.button("🔍 Verify anyway"):
                run_step(wf.verify)
            if st.button("↺ Start again", type="primary"):
                new_workflow()
                st.rerun()

    tabs = st.tabs(["🧭 Dependency paths", "🗺 Plan", "🗂 Workspace apps", "📥 Inbox", "🔍 Verification",
                    "📒 Ledger"])
    with tabs[0]:
        if wf.impact:
            for p in wf.impact["paths"]:
                st.markdown(f"- `{p}`")
        else:
            st.caption("Run the agents to see how the change spreads.")
    with tabs[1]:
        if wf.plans:
            for p in reversed(wf.plans):
                st.markdown(f"**{p['plan_id']}**" + (f" (replaces {p['parent_plan_id']})" if p["parent_plan_id"] else ""))
                st.dataframe(plan_rows(p, p["version"] > 1), hide_index=True, width="stretch")
                st.caption("Dispositions: " + ", ".join(f"{k}: {v.replace('_', ' ')}"
                                                      for k, v in p["dispositions"].items()))
        else:
            st.caption("No plan yet.")
    with tabs[2]:
        at = st.tabs(["Sponsor tracker", "Deliverables", "Decisions", "Docs", "Calendar", "Team chat", "Email drafts"])
        with at[0]:
            record_table("sponsor", ["name", "commitment_paise", "tier", "cash_received_paise"])
            st.caption(f"Budget: commitments {inr(fin['total_commitments_paise'])} − expenses "
                       f"{inr(fin['planned_expenses_paise'])} = forecast **{inr(fin['forecast_balance_paise'])}**")
        with at[1]:
            record_table("deliverable", ["deliverable_id", "kind", "status", "reversible", "owner_id", "external_ref"])
        with at[2]:
            record_table("decision", ["decision_id", "title", "status", "superseded_by", "condition_evaluation"])
        with at[3]:
            for did in ("doc-aster-benefits", "doc-run-sheet"):
                d = store.get("document", did)
                st.markdown(f"**{d['title']}** · v{d['version']}")
                for e in d["entries"]:
                    st.markdown(f"- {e['text']}")
        with at[4]:
            record_table("calendar", ["title", "starts_at", "ends_at", "owner_id"])
        with at[5]:
            posts = store.list("post")
            for p in posts:
                person = store.get("person", p["recipient_id"]) or {}
                st.markdown(f'<div class="msg"><b>→ {person.get("name", p["recipient_id"])}</b> '
                            f'({person.get("role", "")})<br>{html.escape(p["text"])}</div>', unsafe_allow_html=True)
            if not posts:
                st.caption("No internal posts yet.")
        with at[6]:
            for d in store.list("draft"):
                st.markdown(f"**{d['subject']}** · {'SENT' if d.get('sent') else '📝 draft, not sent'}")
                st.markdown(f'<div class="msg">{html.escape(d["body"])}</div>', unsafe_allow_html=True)
            if not store.list("draft"):
                st.caption("No drafts yet.")
    with tabs[3]:
        srcs = [s for s in store.visible_sources() if s["source_system"] in ("mail", "team_chat")]
        for s in sorted(srcs, key=lambda s: s["occurred_at"], reverse=True):
            sender = store.get("person", s["sender_id"]) or {}
            trig = " trigger" if s["source_id"] == wf.trigger_id else ""
            st.markdown(f'<div class="msg{trig}"><b>{s["provider"].title()}</b> · '
                        f'{html.escape(sender.get("name", s["sender_id"] or "unknown"))} · '
                        f'{s["occurred_at"][:16].replace("T", " ")} · <code>{s["source_id"]}</code><br>'
                        f'{html.escape(s["body"])}</div>', unsafe_allow_html=True)
    with tabs[4]:
        if wf.verification:
            for c in wf.verification["checks"]:
                st.markdown(f"{'✅' if c['ok'] else '❌'} **{c['name']}** · {c['detail']}")
        else:
            st.caption("Not verified yet.")
        if wf.replay_result:
            st.json(wf.replay_result)
    with tabs[5]:
        ops = store.ops()
        if ops:
            st.dataframe([{"op_key": o["op_key"], "tool": o["tool"], "target": o["target_id"],
                           "status": o["status"], "attempts": o["attempts"]} for o in ops],
                         hide_index=True, width="stretch")
            st.caption("Each action has an idempotency key derived from its exact content. "
                       "A committed key is never executed twice.")
        else:
            st.caption("No operations yet.")

# ---------------------------------------------------------------- right: agent timeline
with right:
    st.subheader("Agent timeline")
    logs = store.logs()
    seen = st.session_state.get("seen", 0)
    feed = st.container(height=760)
    st.caption("Newest first · every agent step, tool call, retry, conflict and approval")
    display = list(reversed(logs))
    new_count = len(logs) - seen if (seen > 0 and st.session_state.get("animate", True)) else 0

    def render(slot, entry: dict) -> None:
        color = KIND_COLOR.get(entry["kind"], "#adb5bd")
        icon = AGENT_ICON.get(entry["agent"], "•")
        slot.markdown(
            f'<div class="tl" style="border-left-color:{color}">{icon} <b>{entry["agent"]}</b> '
            f'<span style="opacity:.6;font-size:.75rem">{entry["at"][11:19]}</span><br>'
            f'{html.escape(entry["message"])}</div>', unsafe_allow_html=True)

    with feed:
        slots = [st.empty() for _ in display]
        for i in range(new_count, len(display)):
            render(slots[i], display[i])
        for i in range(new_count - 1, -1, -1):   # new entries appear one by one, oldest first
            time.sleep(0.18)
            render(slots[i], display[i])
    st.session_state.seen = len(logs)
