"""Coordinator and Execution agents: approval gate, retries, conflict replanning, replay.

The workflow is a small state machine driven step by step (by the UI or a test):

    ready -> ingest() -> analyze() -> awaiting_approval -> approve() -> execute()
          -> [conflict] awaiting_delta_approval -> approve_delta() -> execute()
          -> executed -> verify() -> verified -> replay()
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from .agents import communication_agent, inr, knowledge_agent, planning_agent, verification_agent
from .storage import Store, VersionConflict
from .tools import ToolTimeout, Tools, TransientToolError

MAX_ATTEMPTS = 3
DEFAULT_SCOPES = ("business_records", "internal_notifications")


class Workflow:
    def __init__(self, scenario_id: str = "S1-main-demo", inject_faults: bool = True,
                 db_path: str = ":memory:", fixtures_dir: Path | str | None = None, use_llm: bool = False):
        self.store = Store.from_fixtures(scenario_id, fixtures_dir, db_path)
        self.use_llm = use_llm
        self.tools = Tools(self.store, None if inject_faults else [])
        self.stage = "ready"
        self.proposal: dict | None = None
        self.impact: dict | None = None
        self.plans: list[dict] = []
        self.approvals: list[dict] = []
        self.approved_keys: set[str] = set()
        self.receipts: dict[str, dict] = {}
        self.action_status: dict[str, str] = {}   # op_key -> pending/committed/reused/skipped/blocked/conflict
        self.delta: dict[str, str] = {}           # v2 op_key -> reuse/covered/needs_approval
        self.verification: dict | None = None
        self.replay_result: dict | None = None
        self.clarification_questions: list[str] = []
        self._trigger: str | None = None

    # ---------- helpers ----------
    @property
    def plan(self) -> dict | None:
        return self.plans[-1] if self.plans else None

    @property
    def trigger_id(self) -> str:
        return self._trigger or self.store.scenario["trigger_source_id"]

    def clarify(self, source_id: str) -> dict | None:
        """A clarifying message arrives while paused: it becomes the trigger and analysis reruns."""
        self._require("needs_clarification", "blocked")
        self.store.deliver(source_id)
        self._trigger = source_id
        self._log(f"Clarification {source_id} received; re-running analysis on it", "trigger")
        self.stage = "ingested"
        return self.analyze()

    def _log(self, message: str, kind: str = "info", data: dict | None = None) -> None:
        self.store.log("Coordinator", message, kind, data)

    def _require(self, *stages: str) -> None:
        if self.stage not in stages:
            raise RuntimeError(f"Step not allowed in stage '{self.stage}' (needs one of {stages})")

    # ---------- steps ----------
    def ingest(self) -> bool:
        self._require("ready")
        src = self.store._sources[self.trigger_id]
        new = self.store.deliver(self.trigger_id)
        self._log(f"New {src['provider']} message {self.trigger_id} received "
                  f"({src['occurred_at'][11:16]} IST); routing to Communication agent", "trigger")
        self.stage = "ingested"
        return new

    def _fault(self, kind: str, target_id: str) -> dict | None:
        return next((f for f in self.tools.faults if f["kind"] == kind and f["target_id"] == target_id), None)

    def _source_readable(self) -> bool:
        """Fail closed if the mail tool cannot read the trigger (no substitution from other channels)."""
        if self._fault("permanent_outage", self.trigger_id):
            for attempt in range(1, MAX_ATTEMPTS + 1):
                self.store.log("Communication", f"Gmail read of {self.trigger_id} failed "
                               f"(attempt {attempt}/{MAX_ATTEMPTS}: service unavailable)", "error")
            self.stage = "blocked"
            self._log("Cannot read the trigger message, so its content, sender and deadline cannot be "
                      "established. Failing closed: no plan, no changes, and no substitute from chat or "
                      "cached copies.", "blocked")
            return False
        return True

    def _privacy_boundary_ok(self) -> bool:
        """Privacy check inside the Communication/Knowledge roles, before any context is released."""
        denied = self.store.scenario.get("privacy", {}).get("denied_source_ids", [])
        if self._fault("agent_failure", "privacy_boundary"):
            self.stage = "blocked"
            self._log("Privacy-boundary check failed to return a result. Failing closed: no context released "
                      "to Knowledge/Planning, no plan, no changes. Permissions are not broadened.", "blocked")
            return False
        if denied:
            leaked = [s for s in denied if self.store.source(s) is not None]
            if leaked:
                self.stage = "blocked"
                self._log(f"Privacy boundary: denied sources visible ({', '.join(leaked)}); failing closed",
                          "blocked")
                return False
            self._log(f"Privacy boundary checked: {len(denied)} confidential sources excluded from every "
                      "agent context and output", "verify")
        return True

    def _claim_issues(self) -> list[str]:
        """Reasons the change cannot be planned yet (tentative, unclear currency, competing claims)."""
        st, p = self.store, self.proposal
        src = st.source(self.trigger_id) or {}
        body = src.get("body", "")
        issues: list[str] = []
        if p.get("new_paise") is None or p.get("currency") != "INR":
            issues.append("The new amount is not stated in INR (the currency is unnamed); INR will not be assumed.")
        if re.search(r"\b(possibly|not a confirmed|not confirmed|could we discuss|tentative|considering)\b",
                     body, re.I):
            issues.append("The message is tentative, not a confirmed revision.")
        if p.get("old_paise") is not None and p.get("current_paise") is not None \
                and p["old_paise"] != p["current_paise"]:
            issues.append(f"The message's old amount {inr(p['old_paise'])} differs from the tracker's "
                          f"{inr(p['current_paise'])}.")
        trig_at = datetime.fromisoformat(src.get("occurred_at") or st.demo_now)
        known = {p.get("new_paise"), p.get("old_paise"), p.get("current_paise")}
        contacts = {c["person_id"] for c in st.list("contact") if c["sponsor_id"] == p.get("sponsor_id")}
        team = {x["person_id"] for x in st.list("person")
                if x["role"] in ("design", "social", "events", "finance", "organizer")}
        aliases = [a["alias"].lower() for a in st.list("alias") if a["entity_id"] == p.get("sponsor_id")]
        for s in st.visible_sources():
            if s["source_id"] == self.trigger_id or s["source_system"] not in ("mail", "team_chat"):
                continue
            if abs(trig_at - datetime.fromisoformat(s["occurred_at"])) > timedelta(hours=24):
                continue   # historical message: a stale amount is not a current competing instruction
            text = s["body"]
            if not any(a in text.lower() for a in aliases):
                continue
            amounts = {int(float(a.replace(",", "")) * 100) for a in re.findall(r"INR\s*([\d,]+(?:\.\d+)?)", text)}
            other = sorted(amounts - known)
            if not other:
                continue
            who = st.get("person", s["sender_id"]) or {}
            name = who.get("name", s["sender_id"])
            if s["sender_id"] not in contacts | team:
                st.log("Communication", f"Ignored {s['source_id']}: {name} is not a registered contact or team "
                       f"member, so its claim of {inr(other[0])} carries no authority", "info")
                continue
            if re.search(r"\breplac|\bsupersed", body, re.I) and all(f"{x // 100:,}" in body for x in other) \
                    and p.get("authorized"):
                st.log("Communication", f"{s['source_id']} ({inr(other[0])}) is explicitly replaced by "
                       f"{self.trigger_id}", "verify")
                continue
            role = "sponsor contact" if s["sender_id"] in contacts else f"{who.get('role', 'team')} team"
            issues.append(f"{name} ({role}, {s['provider']}) says the current amount is {inr(other[0])}, "
                          f"which conflicts with {inr(p.get('new_paise'))} / tracker {inr(p.get('current_paise'))}; "
                          "nothing says which one is correct.")
        return issues

    def analyze(self) -> dict | None:
        self._require("ingested")
        if not self._source_readable():
            return None
        self.proposal = communication_agent(self.store, self.trigger_id)
        if self.use_llm and self.proposal.get("authorized"):
            from .llm import cross_check
            self.proposal = cross_check(self.store, self.proposal)
        if not self.proposal.get("authorized"):
            self.stage = "blocked"
            self._log("Sender is not an authorised sponsor contact; no changes planned, "
                      "clarification needed", "blocked")
            return self.proposal
        if not self._privacy_boundary_ok():
            return self.proposal
        issues = self._claim_issues()
        if issues:
            self.stage = "needs_clarification"
            self.clarification_questions = issues
            for q in issues:
                self._log(f"Needs clarification: {q}", "blocked")
            self._log("Paused before planning: nothing changed. Asking the organiser to get a confirmed "
                      "amount from an authorised contact.", "blocked")
            return self.proposal
        self._log("Change verified; routing to Knowledge agent for impact analysis", "route")
        self.impact = knowledge_agent(self.store, self.proposal)
        self._log("Impact mapped; routing to Planning agent", "route")
        plan = planning_agent(self.store, self.proposal, self.impact, 1, None)
        self.plans.append(plan)
        for a in plan["actions"]:
            self.action_status[a["op_key"]] = "pending"
        self.stage = "awaiting_approval"
        self._log(f"Plan v1 ready ({len(plan['actions'])} actions, {len(plan['flags'])} flags); "
                  "waiting for organiser approval. Nothing has been changed yet.", "approval")
        return plan

    def approve(self, scopes=DEFAULT_SCOPES, approver_id: str = "person-organizer") -> None:
        self._require("awaiting_approval")
        scopes = list(scopes)
        keys = {a["op_key"] for a in self.plan["actions"] if a["scope"] in scopes}
        self.approved_keys |= keys
        self.approvals.append({"plan_id": self.plan["plan_id"], "stage": "initial", "approver_id": approver_id,
                               "scopes": scopes, "op_keys": sorted(keys)})
        for a in self.plan["actions"]:
            if a["op_key"] not in keys:
                self.action_status[a["op_key"]] = "not_approved"
        self.stage = "approved"
        note = ("" if "sponsor_send" in scopes else
                " Sponsor send not selected, so any sponsor reply stays an unsent draft.")
        self._log(f"Plan v1 approved by organiser for scopes: {', '.join(scopes) or 'none'}.{note}",
                  "approval", {"approved_actions": len(keys)})

    def reject(self, approver_id: str = "person-organizer") -> None:
        self._require("awaiting_approval", "awaiting_delta_approval")
        self.approvals.append({"plan_id": self.plan["plan_id"], "stage": "reject", "approver_id": approver_id,
                               "scopes": [], "op_keys": []})
        self.stage = "rejected"
        self._log(f"{self.plan['plan_id']} rejected by organiser; no further changes will be made. "
                  "Already committed effects are kept, not silently rolled back.", "approval")

    def execute(self) -> str:
        """Run approved actions in order. Returns the resulting stage."""
        self._require("approved")
        plan = self.plan
        self.stage = "executing"
        self._log(f"Execution agent running {plan['plan_id']}", "route")
        done = {a["action_id"] for a in plan["actions"]
                if self.action_status.get(a["op_key"]) in ("committed", "reused")}
        read_back_done = False
        for a in plan["actions"]:
            key = a["op_key"]
            if key not in self.approved_keys:
                continue
            if self.action_status.get(key) in ("committed", "reused"):
                continue
            if a["scope"] == "internal_notifications" and not read_back_done:
                read_back_done = True
                if not self._read_back_business(plan):
                    self.stage = "failed"
                    return self.stage
            missing = [d for d in a.get("depends_on", []) if d not in done]
            if missing:
                self.action_status[key] = "blocked"
                self._log(f"{a['action_id']} {a['tool']} {a['target_id']} blocked: "
                          f"depends on {', '.join(missing)}", "blocked")
                continue
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    receipt = self.tools.execute(a)
                    break
                except TransientToolError:
                    if attempt == MAX_ATTEMPTS:
                        self.action_status[key] = "failed"
                        self._log(f"{a['target_id']}: retries exhausted; stopping safely", "error")
                        self.stage = "failed"
                        return self.stage
                    self._log(f"Transient failure before write on {a['target_id']}: safe to retry the "
                              f"same operation (retry {attempt}/{MAX_ATTEMPTS - 1}, same idempotency key)",
                              "retry")
                except ToolTimeout:
                    rec = self.tools.reconcile(a)
                    if rec:
                        receipt = rec
                        break
                    if attempt == MAX_ATTEMPTS:
                        self.action_status[key] = "failed"
                        self.stage = "failed"
                        self._log(f"{a['target_id']}: outcome still unknown after retries; stopping safely", "error")
                        return self.stage
                    self._log(f"Read-back shows the write to {a['target_id']} did not land; retrying the same "
                              "operation", "retry")
                except VersionConflict as exc:
                    self.action_status[key] = "conflict"
                    return self._handle_conflict(a, exc)
            self.receipts.setdefault(key, receipt)
            self.action_status[key] = receipt["status"]
            done.add(a["action_id"])
        self.stage = "executed"
        self._log(f"{plan['plan_id']} executed; routing to Verification agent", "route")
        return self.stage

    def _read_back_business(self, plan: dict) -> bool:
        """Before notifying people, confirm committed business records really hold the planned values."""
        bad = []
        n = 0
        for a in plan["actions"]:
            if a["scope"] != "business_records" or self.action_status.get(a["op_key"]) not in ("committed", "reused"):
                continue
            n += 1
            rec = self.store.get(a["kind"], a["target_id"]) or {}
            if any(rec.get(k) != v for k, v in a["changes"].items()):
                bad.append(a["target_id"])
        if bad:
            self._log(f"Read-back mismatch on {', '.join(bad)}; internal posts held back", "error")
            return False
        if n:
            self._log(f"Read back {n} committed business records: all match. Releasing internal posts.",
                      "verify")
        else:
            self._log("No business records committed in this plan, so there is nothing to read back; "
                      "posts still wait on their own dependencies.", "verify")
        return True

    def _handle_conflict(self, action: dict, exc: VersionConflict) -> str:
        old = self.plan
        self._log(f"Version conflict on {action['target_id']} (expected v{exc.expected}, found v{exc.actual}). "
                  "This is NOT a transient error, so no retry: stopping dependent actions and re-planning "
                  "from fresh state.", "conflict")
        for a in old["actions"]:
            if self.action_status.get(a["op_key"]) == "pending":
                self.action_status[a["op_key"]] = "stopped"
        self._log("Routing to Knowledge agent to refresh context", "route")
        self.impact = knowledge_agent(self.store, self.proposal)
        plan = planning_agent(self.store, self.proposal, self.impact, len(self.plans) + 1, old["plan_id"])
        self.plans.append(plan)
        self.delta = {}
        for a in plan["actions"]:
            key = a["op_key"]
            prior = self.store.op_get(key)
            if prior and prior["status"] == "committed":
                self.delta[key] = "reuse"
            elif key in self.approved_keys:
                self.delta[key] = "covered"
            else:
                self.delta[key] = "needs_approval"
            self.action_status.setdefault(key, "pending")
            if self.action_status[key] == "stopped":
                self.action_status[key] = "pending"
        prev_scopes = {s for ap in self.approvals for s in ap["scopes"]}
        n_new = sum(1 for a in plan["actions"]
                    if self.delta.get(a["op_key"]) == "needs_approval" and a["scope"] in prev_scopes)
        n_reuse = sum(v == "reuse" for v in self.delta.values())
        self.stage = "awaiting_delta_approval"
        self._log(f"Plan {plan['plan_id']} (parent {old['plan_id']}): {n_reuse} committed actions reused, "
                  f"{n_new} changed actions need fresh approval. Waiting for organiser.", "approval")
        return self.stage

    def approve_delta(self, scopes=DEFAULT_SCOPES, approver_id: str = "person-organizer") -> None:
        self._require("awaiting_delta_approval")
        scopes = list(scopes)
        keys = {a["op_key"] for a in self.plan["actions"]
                if self.delta.get(a["op_key"]) == "needs_approval" and a["scope"] in scopes}
        self.approved_keys |= keys
        self.approvals.append({"plan_id": self.plan["plan_id"], "stage": "delta", "approver_id": approver_id,
                               "scopes": scopes, "op_keys": sorted(keys)})
        for a in self.plan["actions"]:
            if a["op_key"] not in self.approved_keys:
                self.action_status[a["op_key"]] = "not_approved"
        self.stage = "approved"
        self._log(f"Delta approval for {self.plan['plan_id']}: {len(keys)} changed actions approved "
                  f"({', '.join(scopes)})", "approval")

    def verify(self) -> dict:
        self._require("executed", "verified", "failed")
        report =verification_agent(self.store, self.plan, self.receipts)
        not_run = [a["action_id"] for a in self.plan["actions"] if a["op_key"] in self.approved_keys
                   and self.action_status.get(a["op_key"]) not in ("committed", "reused")]
        report["checks"].append({"name": "every approved action executed", "ok": not not_run,
                                 "detail": "all approved actions committed" if not not_run
                                 else f"approved but not executed: {', '.join(not_run)}"})
        report["failed"] = sum(1 for c in report["checks"] if not c["ok"])
        report["passed"] = len(report["checks"]) - report["failed"]
        report["ok"] = report["failed"] == 0
        self.verification = report
        ok = report["ok"]
        self.stage = "verified" if ok else "verification_failed"
        self._log(f"Verification {'passed' if ok else 'FAILED'}: {self.verification['passed']} checks passed, "
                  f"{self.verification['failed']} failed (record read-backs plus one check that every approved "
                  "action ran)", "verified" if ok else "error")
        return self.verification

    def replay(self, deliveries: int = 3) -> dict:
        """Redeliver the trigger message and re-run the approved plan: must add zero effects."""
        self._require("verified", "executed", "verification_failed")
        before = self.store.effect_count()
        ignored = 0
        for _ in range(deliveries):
            if not self.store.deliver(self.trigger_id):
                ignored += 1
        self._log(f"Replay: {self.trigger_id} delivered {deliveries} more times; "
                  f"{ignored} recognised as duplicates", "replay")
        reused = 0
        for a in self.plan["actions"]:
            prior = self.store.op_get(a["op_key"])
            # Only previously committed operations are re-issued; anything never executed stays untouched.
            if a["op_key"] in self.approved_keys and prior and prior["status"] == "committed":
                if self.tools.execute(a)["status"] == "reused":
                    reused += 1
        after = self.store.effect_count()
        self.replay_result = {"deliveries": deliveries, "duplicates_ignored": ignored,
                              "actions_reused": reused, "new_effects": after - before}
        self._log(f"Replay result: {reused} actions reused from ledger, {after - before} new effects", "replay",
                  self.replay_result)
        return self.replay_result

    def close(self) -> None:
        self.store.close()

    # ---------- convenience ----------
    def run_scripted(self) -> "Workflow":
        """Run the scenario's scripted human choices end to end (used by tests and CLI)."""
        choices = {c["stage"]: c for c in self.store.scenario["human_choices"]}
        self.ingest()
        self.analyze()
        if self.stage != "awaiting_approval":
            return self
        first = choices.get("initial")
        if not first or first["decision"] != "approve":
            self.reject()
            return self
        self.approve(first["approved_scopes"], first["approver_id"])
        while self.execute() == "awaiting_delta_approval":
            delta = choices.get("delta")
            if not delta or delta["decision"] != "approve":
                self.reject()
                return self
            self.approve_delta(delta["approved_scopes"], delta["approver_id"])
        if self.stage == "executed":
            self.verify()
        return self
