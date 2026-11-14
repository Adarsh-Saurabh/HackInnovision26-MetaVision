"""Simulated workspace apps (tracker, decisions, docs, calendar, chat, email drafts).

Every write goes through `Tools.execute`, which enforces:
- idempotency: an op_key already committed in the ledger is reused, never repeated;
- optimistic concurrency: updates carry the version they expect;
- scripted faults from the scenario (transient failure, concurrent external edit).
"""

from __future__ import annotations

import copy

from .storage import Store, VersionConflict

APP_NAMES = {
    "sponsor": "Sponsor tracker",
    "deliverable": "Deliverables tracker",
    "decision": "Decision log",
    "document": "Docs",
    "calendar": "Calendar",
    "post": "Team chat",
    "draft": "Email drafts",
}


class TransientToolError(Exception):
    """A temporary tool failure that happened before any write; safe to retry."""


class Tools:
    def __init__(self, store: Store, faults: list[dict] | None = None):
        self.store = store
        self.faults = list(store.scenario.get("faults", [])) if faults is None else list(faults)
        self.fired: set[str] = set()

    def execute(self, action: dict) -> dict:
        """Apply one planned action. Returns a receipt; raises TransientToolError or VersionConflict."""
        st = self.store
        key, tool, kind, target = action["op_key"], action["tool"], action["kind"], action["target_id"]
        app = APP_NAMES.get(kind, kind)
        prior = st.op_get(key)
        if prior and prior["status"] == "committed":
            st.log("Execution", f"{app}: {tool} {target} already committed, reused (no new effect)",
                   "reuse", {"op_key": key})
            return {**prior["receipt"], "status": "reused"}

        attempt = (prior["attempts"] if prior else 0) + 1
        st.op_upsert(key, tool, kind, target, action["changes"], "attempting", attempt)

        for f in self.faults:
            if f["fault_id"] in self.fired or f["target_tool"] != tool or f["target_id"] != target:
                continue
            if f["kind"] == "transient_before_write" and f["attempt"] == attempt:
                self.fired.add(f["fault_id"])
                st.op_upsert(key, tool, kind, target, action["changes"], "failed_transient", attempt)
                st.log("Execution", f"{app}: {tool} {target} attempt {attempt} failed "
                       "(503 service unavailable, before write)", "error", {"op_key": key})
                raise TransientToolError(f"{tool} {target}: temporary failure before write")
            if f["kind"] == "concurrent_publish":
                self.fired.add(f["fault_id"])
                self._external_edit(f, kind, target)

        try:
            if action["op"] == "create":
                version = st.put(kind, target, action["changes"], None, "Execution", action.get("reason", ""))
            else:
                cur = st.get(kind, target)
                if cur is None:
                    raise VersionConflict(kind, target, action["expected_version"], None)
                new = {**copy.deepcopy(cur), **copy.deepcopy(action["changes"])}
                version = st.put(kind, target, new, action["expected_version"], "Execution",
                                 action.get("reason", ""))
        except VersionConflict as exc:
            st.op_upsert(key, tool, kind, target, action["changes"], "conflict", attempt)
            st.log("Execution", f"{app}: {tool} {target} refused, record changed underneath "
                   f"(expected v{exc.expected}, found v{exc.actual}); no write made", "conflict",
                   {"op_key": key})
            raise

        receipt = {"op_key": key, "tool": tool, "kind": kind, "target_id": target,
                   "status": "committed", "version": version, "attempt": attempt}
        st.op_upsert(key, tool, kind, target, action["changes"], "committed", attempt, receipt)
        retry_note = f" on attempt {attempt}" if attempt > 1 else ""
        st.log("Execution", f"{app}: {tool} {target} committed{retry_note} (now v{version})",
               "write", receipt)
        return receipt

    def _external_edit(self, fault: dict, kind: str, target: str) -> None:
        """A teammate changes the record directly in the app (not via our agents)."""
        st = self.store
        cur = st.get(kind, target)
        if cur is None:
            return
        effect = {k: v for k, v in (fault.get("effect") or {}).items() if k != "version_increment"}
        new = {**cur, **effect}
        if effect.get("status") == "done":
            new["reversible"] = False
        version = st.put(kind, target, new, cur["version"], fault.get("actor_id") or "external",
                         "external edit in app")
        person = st.get("person", fault.get("actor_id") or "") or {}
        st.log("External", f"{person.get('name', 'A teammate')} changed {target} directly in the app: "
               f"{', '.join(f'{k}={v}' for k, v in effect.items())} (v{cur['version']} → v{version})",
               "external", {"target_id": target, "version": version})
