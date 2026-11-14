"""SQLite-backed state for the simulated workspace.

Holds versioned business records (with full history), the immutable source bank,
the dependency graph, the operations ledger (idempotency) and the action log.
"""

from __future__ import annotations

import copy
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from collections.abc import Callable

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"

# kind -> (fixture file, container, id field)
KINDS: dict[str, tuple[str | None, str | None, str]] = {
    "event": ("sponsors.json", "events", "event_id"),
    "budget": ("sponsors.json", "budgets", "budget_id"),
    "expense": ("sponsors.json", "expenses", "expense_id"),
    "person": ("sponsors.json", "people", "person_id"),
    "contact": ("sponsors.json", "contacts", "contact_id"),
    "alias": ("sponsors.json", "aliases", "alias_id"),
    "sponsor": ("sponsors.json", "sponsors", "sponsor_id"),
    "policy": ("policies.json", "policies", "policy_id"),
    "deliverable": ("deliverables.json", "deliverables", "deliverable_id"),
    "decision": ("decisions.json", "decisions", "decision_id"),
    "document": ("documents.json", "documents", "document_id"),
    "calendar": ("calendar.json", "calendar_items", "calendar_id"),
    "post": (None, None, "post_id"),
    "draft": (None, None, "draft_id"),
    "outbox": (None, None, "message_id"),
}

SCHEMA = """
CREATE TABLE records (kind TEXT, id TEXT, version INTEGER, data TEXT, PRIMARY KEY (kind, id));
CREATE TABLE history (seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, id TEXT, version INTEGER,
                      data TEXT, actor TEXT, reason TEXT, at TEXT);
CREATE TABLE ops (op_key TEXT PRIMARY KEY, tool TEXT, kind TEXT, target_id TEXT, args TEXT,
                  status TEXT, attempts INTEGER, receipt TEXT, updated_at TEXT);
CREATE TABLE deliveries (seq INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, content_hash TEXT,
                         duplicate INTEGER, at TEXT);
CREATE TABLE log (seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, agent TEXT, kind TEXT,
                  message TEXT, data TEXT);
"""


class VersionConflict(Exception):
    """Raised when a write's expected version does not match the stored one."""

    def __init__(self, kind: str, record_id: str, expected: int | None, actual: int | None):
        super().__init__(f"{kind}/{record_id}: expected version {expected}, found {actual}")
        self.kind, self.record_id, self.expected, self.actual = kind, record_id, expected, actual


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _load(fixtures_dir: Path, name: str) -> dict:
    return json.loads((fixtures_dir / name).read_text(encoding="utf-8"))


class Store:
    """Versioned record store plus ledger and log for one scenario run."""

    def __init__(self, path: str = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).unlink(missing_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.scenario: dict = {}
        self.demo_now: str = ""
        self._sources: dict[str, dict] = {}
        self._evidence: dict[str, dict] = {}
        self._active: list[str] = []
        self._allowed: set[str] = set()
        self.graph_nodes: list[dict] = []
        self.graph_edges: list[dict] = []
        self.on_log: Callable[[dict], None] | None = None

    # ---------- seeding ----------
    @classmethod
    def from_fixtures(cls, scenario_id: str = "S1-main-demo", fixtures_dir: Path | str | None = None,
                      path: str = ":memory:") -> "Store":
        fx = Path(fixtures_dir) if fixtures_dir else FIXTURES_DIR
        store = cls(path)
        scenarios = _load(fx, "scenarios.json")
        store.scenario = next(s for s in scenarios["scenarios"] if s["scenario_id"] == scenario_id)
        store.demo_now = store.scenario["demo_now"]
        cache: dict[str, dict] = {}
        for kind, (fname, container, id_field) in KINDS.items():
            if fname is None:
                continue
            data = cache.setdefault(fname, _load(fx, fname))
            for rec in data[container]:
                rec = dict(rec)
                rec.setdefault("version", 1)
                store._insert(kind, rec[id_field], rec, actor="seed", reason="baseline fixture")
        src = _load(fx, "sources.json")
        store._sources = {s["source_id"]: s for s in src["sources"]}
        store._evidence = {e["evidence_id"]: e for e in src["evidence"]}
        dep = _load(fx, "dependencies.json")
        store.graph_nodes, store.graph_edges = dep["nodes"], dep["edges"]
        store._allowed = set(store.scenario["available_source_ids"]) - set(
            store.scenario["privacy"]["denied_source_ids"])
        # Baseline-phase sources are visible from the start; trigger arrives via deliver().
        for act in sorted(store.scenario["activation"], key=lambda a: a["order"]):
            if act["phase"] == "baseline":
                store._active.append(act["source_id"])
        store.db.commit()
        store.log("Coordinator", f"Workspace seeded for scenario {scenario_id} "
                  f"({len(store._active)} baseline sources visible)", "system")
        return store

    def _insert(self, kind: str, rid: str, rec: dict, actor: str, reason: str) -> None:
        blob = json.dumps(rec, ensure_ascii=False)
        self.db.execute("INSERT INTO records VALUES (?,?,?,?)", (kind, rid, rec["version"], blob))
        self.db.execute("INSERT INTO history (kind,id,version,data,actor,reason,at) VALUES (?,?,?,?,?,?,?)",
                        (kind, rid, rec["version"], blob, actor, reason, _now()))

    # ---------- records ----------
    def get(self, kind: str, rid: str) -> dict | None:
        row = self.db.execute("SELECT data FROM records WHERE kind=? AND id=?", (kind, rid)).fetchone()
        return json.loads(row["data"]) if row else None

    def list(self, kind: str) -> list[dict]:
        rows = self.db.execute("SELECT data FROM records WHERE kind=? ORDER BY rowid", (kind,)).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def put(self, kind: str, rid: str, data: dict, expected_version: int | None,
            actor: str, reason: str = "") -> int:
        """Create (expected_version None) or replace a record. Returns the new version."""
        cur = self.get(kind, rid)
        actual = cur["version"] if cur else None
        if expected_version != actual:
            raise VersionConflict(kind, rid, expected_version, actual)
        rec = copy.deepcopy(data)
        rec["version"] = 1 if cur is None else actual + 1
        blob = json.dumps(rec, ensure_ascii=False)
        if cur is None:
            self.db.execute("INSERT INTO records VALUES (?,?,?,?)", (kind, rid, rec["version"], blob))
        else:
            self.db.execute("UPDATE records SET version=?, data=? WHERE kind=? AND id=?",
                            (rec["version"], blob, kind, rid))
        self.db.execute("INSERT INTO history (kind,id,version,data,actor,reason,at) VALUES (?,?,?,?,?,?,?)",
                        (kind, rid, rec["version"], blob, actor, reason, _now()))
        self.db.commit()
        return rec["version"]

    def history(self, kind: str | None = None, rid: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM history WHERE actor != 'seed'", []
        if kind:
            q, args = q + " AND kind=?", args + [kind]
        if rid:
            q, args = q + " AND id=?", args + [rid]
        rows = self.db.execute(q + " ORDER BY seq", args).fetchall()
        return [{**dict(r), "data": json.loads(r["data"])} for r in rows]

    def baseline(self, kind: str, rid: str) -> dict | None:
        """The seeded (pre-run) version of a record, for comparing against unintended changes."""
        row = self.db.execute("SELECT data FROM history WHERE kind=? AND id=? AND actor='seed' "
                              "ORDER BY seq LIMIT 1", (kind, rid)).fetchone()
        return json.loads(row["data"]) if row else None

    def close(self) -> None:
        self.db.close()

    def effect_count(self) -> int:
        """Number of non-seed record writes (used to prove replay adds zero effects)."""
        return self.db.execute("SELECT COUNT(*) FROM history WHERE actor != 'seed'").fetchone()[0]

    # ---------- sources ----------
    def deliver(self, source_id: str) -> bool:
        """Deliver a message. Returns False (no effect) for a duplicate of an already-seen message."""
        if source_id not in self._allowed:
            self.log("Coordinator", f"Delivery of {source_id} refused: not in this scenario's allowed sources",
                     "blocked")
            return False
        src = self._sources[source_id]
        dup =self.db.execute("SELECT 1 FROM deliveries WHERE source_id=? AND content_hash=? AND duplicate=0",
                              (source_id, src["content_hash"])).fetchone() is not None
        dup = dup or source_id in self._active
        self.db.execute("INSERT INTO deliveries (source_id,content_hash,duplicate,at) VALUES (?,?,?,?)",
                        (source_id, src["content_hash"], int(dup), _now()))
        self.db.commit()
        if not dup:
            self._active.append(source_id)
        return not dup

    def source(self, source_id: str) -> dict | None:
        return copy.deepcopy(self._sources[source_id]) if source_id in self._active else None

    def visible_sources(self) -> list[dict]:
        return [copy.deepcopy(self._sources[s]) for s in self._active]

    def evidence(self, evidence_id: str) -> dict | None:
        ev = self._evidence.get(evidence_id)
        return dict(ev) if ev and ev["source_id"] in self._active else None

    def evidence_for_source(self, source_id: str) -> list[dict]:
        if source_id not in self._active:
            return []
        return [dict(e) for e in self._evidence.values() if e["source_id"] == source_id]

    def list_evidence(self) -> list[dict]:
        return [dict(e) for e in self._evidence.values() if e["source_id"] in self._active]

    # ---------- operations ledger ----------
    def op_get(self, op_key: str) -> dict | None:
        row = self.db.execute("SELECT * FROM ops WHERE op_key=?", (op_key,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["args"] = json.loads(d["args"])
        d["receipt"] = json.loads(d["receipt"]) if d["receipt"] else None
        return d

    def op_upsert(self, op_key: str, tool: str, kind: str, target_id: str, args: Any,
                  status: str, attempts: int, receipt: dict | None = None) -> None:
        self.db.execute(
            "INSERT INTO ops VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(op_key) DO UPDATE SET "
            "status=excluded.status, attempts=excluded.attempts, receipt=excluded.receipt, "
            "updated_at=excluded.updated_at",
            (op_key, tool, kind, target_id, json.dumps(args, ensure_ascii=False), status, attempts,
             json.dumps(receipt, ensure_ascii=False) if receipt else None, _now()))
        self.db.commit()

    def ops(self) -> list[dict]:
        return [self.op_get(r["op_key"]) for r in
                self.db.execute("SELECT op_key FROM ops ORDER BY rowid").fetchall()]

    # ---------- action log ----------
    def log(self, agent: str, message: str, kind: str = "info", data: dict | None = None) -> None:
        entry = {"at": _now(), "agent": agent, "kind": kind, "message": message, "data": data}
        self.db.execute("INSERT INTO log (at,agent,kind,message,data) VALUES (?,?,?,?,?)",
                        (entry["at"], agent, kind, message,
                         json.dumps(data, ensure_ascii=False, default=str) if data else None))
        self.db.commit()
        if self.on_log:
            try:
                self.on_log(entry)
            except Exception:
                # A progress display must never interrupt a committed business operation.
                logging.getLogger(__name__).exception("Progress display failed; workflow continues")

    def logs(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM log ORDER BY seq").fetchall()
        return [{**dict(r), "data": json.loads(r["data"]) if r["data"] else None} for r in rows]
