"""Run every dataset scenario through the agents and compare with the test-only expected outcomes.

Usage: uv run python scripts/run_scenarios.py
Exit code 0 only if every scenario passes.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from second_brain.agents import compute_financials  # noqa: E402
from second_brain.workflow import Workflow  # noqa: E402

FIX = ROOT / "data" / "fixtures"
# Fresh long-term memory per script run: S2 can only recall what S1 actually verified here.
MEMORY = str(Path(tempfile.mkdtemp(prefix="sb-memory-")) / "memory.sqlite")
SUPPORTED_FAULTS = {("transient_before_write", None), ("concurrent_publish", None), ("timeout_after_write", None),
                    ("permanent_outage", "read_source"), ("agent_failure", None)}
NO_CHANGE = {"baseline_preserved", "clarification_required", "fail_closed"}


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def run(scenario: dict) -> Workflow:
    wf = Workflow(scenario["scenario_id"], memory_path=MEMORY)
    st = wf.store
    if wf.stage == "blocked":
        return wf
    choices = {c["stage"]: c for c in scenario["human_choices"]}
    wf.ingest()
    for act in sorted(scenario["activation"], key=lambda a: a["order"]):
        if act["phase"] == "trigger" and act["source_id"] != wf.trigger_id:
            st.deliver(act["source_id"])
    wf.analyze()
    clarifications = [a["source_id"] for a in sorted(scenario["activation"], key=lambda a: a["order"])
                      if a["phase"] == "clarification"]
    if wf.stage == "needs_clarification" and clarifications:
        wf.paused_for_clarification = True
        for sid in clarifications:
            wf.clarify(sid)
    if wf.stage != "awaiting_approval":
        return wf
    first = choices.get("initial") or choices.get("after_clarification")
    if not first:
        return wf      # no human choice scripted: the system should have paused before planning
    if first["decision"] != "approve":
        wf.reject()
        return wf
    wf.approve(first["approved_scopes"], first["approver_id"])
    while wf.execute() == "awaiting_delta_approval":
        delta = choices.get("delta")
        if not delta or delta["decision"] != "approve":
            wf.reject()
            return wf
        wf.approve_delta(delta["approved_scopes"], delta["approver_id"])
    if wf.stage == "executed":
        wf.verify()
    if scenario["replay"]["additional_deliveries"] and wf.stage == "verified":
        r = wf.replay(scenario["replay"]["additional_deliveries"])
        wf.replay_new_effects = r["new_effects"]
    return wf


def evaluate(wf: Workflow, scenario: dict, outcome: dict, profile: dict | None) -> list[str]:
    st, fails = wf.store, []
    exp = outcome["expectation"]
    if exp in NO_CHANGE:
        if st.effect_count() != 0:
            fails.append(f"expected no business changes ({exp}) but {st.effect_count()} records were written "
                         f"(stage {wf.stage})")
        if exp != "baseline_preserved" and wf.stage not in ("blocked", "needs_clarification"):
            fails.append(f"expected a pause (clarification / fail closed), got stage {wf.stage}")
    if any(a["phase"] == "clarification" for a in scenario["activation"]) \
            and not getattr(wf, "paused_for_clarification", False):
        fails.append("conflicting claims were not paused for clarification before approval")
    if profile:
        fin = compute_financials(st)
        for k, v in profile["financials"].items():
            if fin.get(k) != v:
                fails.append(f"financials.{k}: got {fin.get(k)}, expected {v}")
        for e in profile["sponsor_effects"]:
            r = st.get("sponsor", e["sponsor_id"])
            for k in ("commitment_paise", "tier", "cash_received_paise"):
                if r.get(k) != e[k]:
                    fails.append(f"{e['sponsor_id']}.{k}: got {r.get(k)}, expected {e[k]}")
        for e in profile["deliverable_effects"]:
            r = st.get("deliverable", e["deliverable_id"])
            if r["status"] != e["status"]:
                fails.append(f"{e['deliverable_id']}.status: got {r['status']}, expected {e['status']}")
            if e["run_sheet_present"] is not None:
                rs = st.get("document", "doc-run-sheet")
                present = any(x.get("deliverable_id") == e["deliverable_id"] for x in rs["entries"])
                if present != e["run_sheet_present"]:
                    fails.append(f"{e['deliverable_id']} run-sheet entry present={present}, "
                                 f"expected {e['run_sheet_present']}")
        for e in profile["decision_effects"]:
            r = st.get("decision", e["decision_id"]) or {}
            if r.get("status") != e["status"]:
                fails.append(f"{e['decision_id']}.status: got {r.get('status')}, expected {e['status']}")
            if e["superseded_by"] and r.get("superseded_by") != e["superseded_by"]:
                fails.append(f"{e['decision_id']}.superseded_by: got {r.get('superseded_by')}")
            if e["condition_satisfied"] is not None:
                ev = r.get("condition_evaluation")
                if ev:
                    sat = ev.get("satisfied")
                else:  # not re-evaluated by the run: the condition still holds on the current numbers
                    cond = r["condition"]
                    sat = compute_financials(st)[cond["metric"]] >= cond["threshold_paise"]
                if sat is not e["condition_satisfied"]:
                    fails.append(f"{e['decision_id']} condition_satisfied: got {sat}")
        if profile["review"]:
            n = sum(1 for c in st.list("calendar") if c["logical_key"] == profile["review"]["logical_key"])
            if n != profile["review"]["logical_count"]:
                fails.append(f"review meetings: got {n}, expected {profile['review']['logical_count']}")
        for rid in profile["preserved_ids"]:
            if any(h["id"] == rid for h in st.history()):
                fails.append(f"{rid} should be preserved but was modified")
    comm = outcome["communication"]
    sent = st.list("outbox")
    if sent and not comm["sponsor_send_allowed"]:
        fails.append("sponsor email sent without sponsor_send approval")
    if comm["sponsor_send_allowed"] and exp == "approved_effects" and not sent:
        fails.append("sponsor_send was approved but the sponsor reply was only drafted, not sent")
    if not comm["internal_posts_allowed"] and st.list("post"):
        fails.append("internal posts sent when not allowed")
    if getattr(wf, "replay_new_effects", 0):
        fails.append(f"replay produced {wf.replay_new_effects} new effects")
    denied = scenario["privacy"]["denied_source_ids"]
    if denied:
        logs = json.dumps(st.logs(), ensure_ascii=False) + json.dumps(wf.plans, ensure_ascii=False)
        for sid in denied:
            ev = [e for e in load("sources.json")["evidence"] if e["source_id"] == sid]
            for e in ev:
                if e["quote"] in logs:
                    fails.append(f"denied content from {sid} leaked into logs/plans")
    return fails


def gaps(scenario: dict) -> list[str]:
    g = [f"fault '{f['kind']}' on {f['target_tool']} not simulated" for f in scenario["faults"]
         if (f["kind"], None) not in SUPPORTED_FAULTS and (f["kind"], f["target_tool"]) not in SUPPORTED_FAULTS]
    if scenario["memory"]["pause_at"]:
        g.append(f"restart/resume at {scenario['memory']['pause_at']} not simulated")
    if any(c["stage"] == "fallback" for c in scenario["human_choices"]):
        g.append("fallback approval stage not implemented")
    return g


def main() -> int:
    scenarios = {s["scenario_id"]: s for s in load("scenarios.json")["scenarios"]}
    eo = load("expected_outcomes.json")
    profiles = {p["profile_id"]: p for p in eo["outcome_profiles"]}
    rows, n_pass = [], 0
    for out in eo["outcomes"]:
        sid = out["scenario_id"]
        sc = scenarios[sid]
        try:
            wf = run(sc)
            fails = evaluate(wf, sc, out, profiles.get(out["profile_id"]))
            stage = wf.stage
        except Exception as exc:
            fails, stage = [f"CRASH {type(exc).__name__}: {exc}"], "crash"
        g = gaps(sc)
        verdict = "FAIL" if fails else ("NOT TESTED" if g else "PASS")
        n_pass += verdict == "PASS"
        rows.append((sid, sc["priority"], out["expectation"], stage, verdict, fails, g))
    for sid, pri, exp, stage, verdict, fails, g in rows:
        print(f"{verdict:<10} {pri} {sid:<30} expect={exp:<22} stage={stage}")
        for f in fails[:4]:
            print(f"        - {f}")
        if len(fails) > 4:
            print(f"        - ... {len(fails) - 4} more")
        for x in g:
            print(f"        * not tested: {x}")
    n_nt = sum(1 for r in rows if r[4] == "NOT TESTED")
    print(f"\n{n_pass}/{len(rows)} PASS, {sum(1 for r in rows if r[4] == 'FAIL')} FAIL, {n_nt} NOT TESTED "
          "(a scripted fault/feature is not simulated by the prototype, so the result proves nothing)")
    return 0 if n_pass == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
