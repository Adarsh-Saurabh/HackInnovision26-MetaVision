"""Offline fixture checks only; no workflow, connectors, or dependencies."""

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


class FixtureError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise FixtureError(message)


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def nonfinite(value):
    raise FixtureError(f"non-finite JSON value: {value}")


def finite_float(value):
    number = float(value)
    require(math.isfinite(number), f"non-finite JSON number: {value}")
    return number


def parse(text):
    return json.loads(text, object_pairs_hook=strict_pairs, parse_constant=nonfinite, parse_float=finite_float)


def enum(*values):
    return ("enum", values)


def nullable(spec):
    return ("nullable", spec)


SYSTEM = enum("mail", "team_chat", "tracker", "docs", "calendar")
TIER = enum("Gold", "Silver")
STATUS = enum("planned", "scheduled", "in_production", "done", "cancelled")
DECISION_STATUS = enum("pending", "at_risk", "superseded", "approved", "rejected")
SCOPES = [enum("business_records", "internal_notifications", "sponsor_send")]
M = {
    "event_id": "str", "version": "positive", "valid_from": "time",
    "valid_to": nullable("time"), "recorded_at": "time",
    "superseded_by": nullable("str"), "evidence_ids": ["str"],
}
CONDITION = {
    "metric": enum("forecast_balance_paise"), "budget_id": "str",
    "operator": enum("gte"), "threshold_paise": "money", "currency": enum("INR"),
    "evidence_ids": ["str"],
}
ENTITLEMENTS = {
    "main_stage_banner_logo": "bool", "sponsor_wall_banner_logo": "bool",
    "social_posts": "money", "stage_mention": "bool",
}
NODE_TYPES = enum(
    "Sponsor", "Commitment", "Event", "Budget", "Policy", "Deliverable",
    "Document", "Task", "CalendarItem", "Person/Role", "Decision", "SourceMessage",
    "Thread",
)
RELATIONS = enum(
    "SPONSORS", "HAS_COMMITMENT", "CONTRIBUTES_TO", "QUALIFIES_UNDER", "ENTITLES_TO",
    "DOCUMENTED_IN", "DEPENDS_ON", "CONTINGENT_ON", "ASSIGNED_TO", "DUE_AT",
    "REQUIRES_APPROVAL", "SUPERSEDES", "MENTIONS", "PART_OF_THREAD", "EVIDENCED_BY",
)
FINANCIALS = {
    "currency": enum("INR"), "total_commitments_paise": "money",
    "planned_expenses_paise": "money", "forecast_balance_paise": "int",
    "total_cash_received_paise": "money",
}
SCHEMAS = {
    "sponsors.json": {
        "events": [{"event_id": "str", "name": "str", "starts_on": "date",
                    "ends_on": "date", "timezone": enum("Asia/Kolkata")}],
        "budgets": [{**M, "budget_id": "str", "currency": enum("INR"),
                     "sponsor_ids": ["str"], "expense_ids": ["str"]}],
        "expenses": [{**M, "expense_id": "str", "budget_id": "str",
                      "description": "str", "amount_paise": "money", "currency": enum("INR")}],
        "people": [{"person_id": "str", "event_id": "str", "name": "str",
                    "role": enum("design", "social", "events", "finance", "organizer",
                                 "sponsor_contact", "unknown"),
                    "email": nullable("str"), "evidence_ids": ["str"]}],
        "contacts": [{"contact_id": "str", "event_id": "str", "person_id": "str",
                      "sponsor_id": "str", "address": "str",
                      "authority": enum("commitment_contact"), "evidence_ids": ["str"]}],
        "aliases": [{"alias_id": "str", "event_id": "str", "entity_id": "str",
                     "alias": "str", "source_id": "str", "evidence_ids": ["str"]}],
        "sponsors": [{**M, "sponsor_id": "str", "name": "str", "commitment_id": "str",
                      "commitment_paise": "money", "cash_received_paise": "money",
                      "currency": enum("INR"), "tier": TIER, "contact_ids": ["str"]}],
    },
    "sources.json": {
        "threads": [{"thread_id": "str", "event_id": "str", "source_system": SYSTEM,
                     "subject": "str"}],
        "sources": [{"source_id": "str", "source_system": SYSTEM,
                     "provider": enum("gmail", "slack", "whatsapp", "local_tracker",
                                      "local_docs", "local_calendar"),
                     "external_id": "str", "event_id": "str", "thread_id": nullable("str"),
                     "in_reply_to": nullable("str"), "channel": nullable("str"),
                     "sender_id": "str", "occurred_at": "time", "received_at": "time",
                     "body": "str", "content_hash": "str",
                     "sensitivity": enum("public", "internal", "confidential")}],
        "evidence": [{"evidence_id": "str", "source_id": "str", "quote": "str",
                      "start": "money", "end": "positive"}],
    },
    "policies.json": {"policies": [{
        **M, "policy_id": "str", "currency": enum("INR"),
        "selection": enum("highest_qualifying"),
        "tiers": [{"tier": TIER, "minimum_commitment_paise": "money",
                   "entitlements": ENTITLEMENTS}],
        "benefit_reduction_requires_organizer_approval": "bool",
        "below_minimum": enum("unresolved"),
    }]},
    "deliverables.json": {"deliverables": [{
        **M, "deliverable_id": "str", "sponsor_id": "str",
        "kind": enum("main_stage_banner_logo", "social_post", "stage_mention"),
        "status": STATUS, "reversible": "bool", "external_ref": nullable("str"),
        "owner_id": "str", "scheduled_at": nullable("time"), "document_ids": ["str"],
    }]},
    "decisions.json": {"decisions": [{
        **M, "decision_id": "str", "title": "str", "status": DECISION_STATUS,
        "owner_id": "str", "sponsor_id": nullable("str"), "condition": nullable(CONDITION),
        "optional_cost_paise": nullable("money"), "currency": enum("INR"),
        "condition_evaluation": nullable({"observed_paise": "int", "satisfied": "bool",
                                          "evaluated_at": "time", "evidence_ids": ["str"]}),
    }]},
    "dependencies.json": {
        "nodes": [{"node_id": "str", "event_id": "str", "node_type": NODE_TYPES,
                   "record_id": "str", "record_file": "str"}],
        "edges": [{"edge_id": "str", "event_id": "str", "from_id": "str",
                   "relation": RELATIONS, "to_id": "str", "provenance": enum("declared"),
                   "evidence_ids": ["str"], "valid_from": "time", "valid_to": nullable("time")}],
    },
    "documents.json": {"documents": [{
        **M, "document_id": "str", "title": "str", "owner_id": "str", "source_id": "str",
        "body": "str", "entries": [{"entry_id": "str", "sponsor_id": nullable("str"),
                                      "deliverable_id": nullable("str"), "text": "str"}],
    }]},
    "calendar.json": {"calendar_items": [{
        **M, "calendar_id": "str", "logical_key": "str", "title": "str", "starts_at": "time",
        "ends_at": "time", "owner_id": "str", "sponsor_id": nullable("str"), "source_id": "str",
    }]},
    "scenarios.json": {
        "baselines": [{"baseline_id": "str", "event_id": "str", "record_files": ["str"],
                       "source_ids": ["str"]}],
        "scenarios": [{
            "scenario_id": "str", "title": "str", "priority": enum("P0", "P1"),
            "event_id": "str", "baseline_id": "str", "demo_now": "time",
            "trigger_source_id": "str", "available_source_ids": ["str"],
            "activation": [{"source_id": "str", "order": "money",
                            "phase": enum("baseline", "trigger", "clarification", "after_verified_parent")}],
            "human_choices": [{"stage": enum("initial", "delta", "fallback", "after_clarification"),
                               "decision": enum("approve", "reject"), "approver_id": "str",
                               "approved_scopes": SCOPES, "review_at": nullable("time")}],
            "faults": [{"fault_id": "str", "kind": enum("transient_before_write", "concurrent_publish",
                         "timeout_after_write", "permanent_outage", "agent_failure"),
                        "target_tool": nullable("str"), "target_id": nullable("str"),
                        "attempt": nullable("positive"),
                        "timing": enum("before_write", "after_approval_before_cancel", "after_possible_write",
                                       "all_attempts", "before_sensitive_context_release"),
                        "actor_id": nullable("str"),
                        "effect": nullable({"status": enum("done"), "version_increment": "positive"})}],
            "replay": {"additional_deliveries": "money", "same_source_identity": "bool", "same_content": "bool"},
            "inheritance": nullable({"parent_scenario_id": "str", "required_parent_state": enum("verified_actual"),
                                     "state_source": enum("runtime_state_and_history"), "include_history": "bool"}),
            "intentional_negative": "bool",
            "privacy": {"allowed_source_ids": ["str"], "denied_source_ids": ["str"],
                        "outgoing_excluded_source_ids": ["str"]},
            "memory": {"mode": enum("fresh", "short_term_resume", "long_term_inherit"),
                       "pause_at": nullable(enum("initial_approval", "after_sponsor_commit")),
                       "resume_same_run": "bool", "preserve_committed_effects": "bool"},
        }],
    },
    "expected_outcomes.json": {
        "test_only": "bool",
        "outcome_profiles": [{
            "profile_id": "str", "financials": FINANCIALS,
            "sponsor_effects": [{"sponsor_id": "str", "commitment_paise": "money",
                                 "tier": TIER, "cash_received_paise": "money"}],
            "deliverable_effects": [{"deliverable_id": "str", "status": STATUS,
                                     "disposition": enum("retain", "satisfied", "cancel", "flag_human", "over_delivery"),
                                     "mutation_actor": enum("none", "agent", "injected_external"),
                                     "run_sheet_present": nullable("bool")}],
            "decision_effects": [{"decision_id": "str", "status": DECISION_STATUS,
                                  "superseded_by": nullable("str"), "replacement_status": nullable(DECISION_STATUS),
                                  "condition_satisfied": nullable("bool")}],
            "review": nullable({"logical_key": "str", "starts_at": "time", "ends_at": "time", "logical_count": "positive"}),
            "required_flags": ["str"], "preserved_ids": ["str"],
            "inferred_links": [{"from_id": "str", "relation": RELATIONS, "to_id": "str", "evidence_ids": ["str"]}],
            "trace_requirements": ["str"],
        }],
        "outcomes": [{
            "scenario_id": "str", "profile_id": nullable("str"),
            "expectation": enum("approved_effects", "baseline_preserved", "partial_preserved",
                                "clarification_required", "inherited_effects", "fail_closed"),
            "resolved_deadline": nullable("time"),
            "communication": {"sponsor_send_allowed": "bool", "internal_posts_allowed": "bool",
                              "recipient_owner_ids": ["str"], "drafts_are_not_delivery": "bool"},
            "safety": ["str"], "unresolved": ["str"],
            "rule_support": {key: ["str"] for key in (
                "EVT-SRC-001", "EVT-FIN-001", "EVT-BEN-001", "EVT-DLV-001",
                "EVT-DEC-001", "EVT-DEP-001", "EVT-APR-001", "EVT-VER-001")},
        }],
    },
}


def timestamp(value):
    require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", value)),
            f"offset-aware timestamp required: {value}")
    require(int(value[-5:-3]) <= 23 and int(value[-2:]) <= 59, f"invalid UTC offset: {value}")
    require(value.endswith("+05:30"), "fixture timestamps must be normalized to Asia/Kolkata (+05:30)")
    return datetime.fromisoformat(value)


def shape(value, spec, path):
    if isinstance(spec, dict):
        require(type(value) is dict, f"{path}: expected object")
        require(set(value) == set(spec), f"{path}: missing/unknown fields {set(value) ^ set(spec)}")
        for key, child in spec.items():
            shape(value[key], child, f"{path}.{key}")
    elif isinstance(spec, list):
        require(type(value) is list, f"{path}: expected array")
        for index, item in enumerate(value):
            shape(item, spec[0], f"{path}[{index}]")
        if spec[0] == "str" or isinstance(spec[0], tuple):
            require(len(value) == len(set(value)), f"{path}: duplicate array values")
    elif isinstance(spec, tuple):
        if spec[0] == "nullable":
            if value is not None:
                shape(value, spec[1], path)
        else:
            require(type(value) is str and value in spec[1], f"{path}: invalid enum {value!r}")
    elif spec == "bool":
        require(type(value) is bool, f"{path}: expected boolean")
    elif spec in ("int", "money", "positive"):
        require(type(value) is int, f"{path}: expected strict integer, not boolean/float")
        if spec != "int":
            require(value >= (1 if spec == "positive" else 0), f"{path}: invalid integer range")
    else:
        require(type(value) is str and bool(value), f"{path}: expected nonempty string")
        if spec == "time":
            timestamp(value)
        elif spec == "date":
            require(date.fromisoformat(value).isoformat() == value, f"{path}: invalid date")


def index(rows, key):
    result = {}
    for row in rows:
        require(row[key] not in result, f"duplicate {key}: {row[key]}")
        result[row[key]] = row
    return result


def load(root):
    result = {}
    for name in ("README.md", "validate.py"):
        raw = (root / name).read_bytes()
        require(not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and raw.endswith(b"\n"),
                f"{name}: require UTF-8 without BOM, LF, final newline")
        raw.decode("utf-8")
        if name.endswith(".py"):
            require(all(line.rstrip(b" \t") == line for line in raw.splitlines()), "validate.py: trailing whitespace")
    for name in SCHEMAS:
        path = root / name
        require(path.is_file(), f"missing fixture: {name}")
        raw = path.read_bytes()
        require(not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and raw.endswith(b"\n"),
                f"{name}: require UTF-8 without BOM, LF, final newline")
        result[name] = parse(raw.decode("utf-8"))
        require(json.dumps(result[name], ensure_ascii=False, indent=2) + "\n" == raw.decode("utf-8"),
                f"{name}: require canonical two-space indentation")
    return result


def validate(data):
    require(set(data) == set(SCHEMAS), "fixture file set differs from contract")
    for name, spec in SCHEMAS.items():
        shape(data[name], {"schema_version": enum("metavision-fixtures/1"),
                           "dataset_id": enum("dataset-innovision-2026-v1"), **spec}, name)
    records = {}
    locations = {}
    tables = {}
    primary = {
        "events": "event_id", "budgets": "budget_id", "expenses": "expense_id",
        "people": "person_id", "contacts": "contact_id", "aliases": "alias_id",
        "sponsors": "sponsor_id", "threads": "thread_id", "sources": "source_id",
        "evidence": "evidence_id", "policies": "policy_id", "deliverables": "deliverable_id",
        "decisions": "decision_id", "documents": "document_id", "calendar_items": "calendar_id",
        "baselines": "baseline_id", "scenarios": "scenario_id", "outcome_profiles": "profile_id",
    }
    for name, doc in data.items():
        for table, key in primary.items():
            if table not in doc:
                continue
            tables[table] = index(doc[table], key)
            if name not in ("scenarios.json", "expected_outcomes.json"):
                for identifier, row in tables[table].items():
                    require(identifier not in records, f"cross-namespace ID collision: {identifier}")
                    records[identifier] = row
                    locations[identifier] = name
    event_id = "event-innovision-2026"
    now = timestamp("2026-11-14T06:30:00+05:30")
    require(set(tables["events"]) == {event_id}, "wrong event scope")
    historical_source_ids = {i for b in tables["baselines"].values() for i in b["source_ids"]}
    event = tables["events"][event_id]
    require((event["name"], event["starts_on"], event["ends_on"]) ==
            ("Innovision Campus Fest 2026", "2026-11-21", "2026-11-22"), "wrong event facts")

    def ref(identifier, table=None):
        if identifier is None:
            return
        require(identifier in (tables[table] if table else records), f"unresolved {table or 'record'} reference: {identifier}")

    def evidence_refs(row):
        require(bool(row["evidence_ids"]), "empty evidence_ids")
        for evidence_id in row["evidence_ids"]:
            ref(evidence_id, "evidence")

    for row in records.values():
        if "event_id" in row:
            require(row["event_id"] == event_id, "record event scope mismatch")
        if "version" in row:
            require(row["version"] == 1 and row["valid_to"] is None and row["superseded_by"] is None,
                    "baseline contains future version/supersession")
            require(timestamp(row["valid_from"]) <= timestamp(row["recorded_at"]) <= now,
                    "baseline temporal ordering/future state")
        if "evidence_ids" in row:
            evidence_refs(row)
            require(all(tables["evidence"][i]["source_id"] in historical_source_ids for i in row["evidence_ids"]),
                    "baseline record cites non-baseline evidence")
    sources = tables["sources"]
    identities = set()
    providers = {"gmail": "mail", "slack": "team_chat", "whatsapp": "team_chat",
                 "local_tracker": "tracker", "local_docs": "docs", "local_calendar": "calendar"}
    for source in sources.values():
        ref(source["sender_id"], "people")
        require(providers[source["provider"]] == source["source_system"], "source provider/system mismatch")
        identity = (source["source_system"], source["external_id"])
        require(identity not in identities, "duplicate source system/external identity")
        identities.add(identity)
        require(timestamp(source["occurred_at"]) <= timestamp(source["received_at"]), "source received before occurrence")
        require(hashlib.sha256(source["body"].encode("utf-8")).hexdigest() == source["content_hash"],
                f"content hash mismatch: {source['source_id']}")
        if source["source_system"] == "mail":
            ref(source["thread_id"], "threads")
            require(source["thread_id"] is not None and source["channel"] is None, "invalid email envelope")
        elif source["source_system"] == "team_chat":
            require(source["channel"] is not None, "chat missing channel")
            ref(source["thread_id"], "threads")
        else:
            require(source["thread_id"] is None and source["in_reply_to"] is None, "snapshot has email linkage")
        if source["in_reply_to"] is not None:
            ref(source["in_reply_to"], "sources")
            parent = sources[source["in_reply_to"]]
            require(parent["thread_id"] == source["thread_id"] and
                    timestamp(parent["occurred_at"]) < timestamp(source["occurred_at"]), "invalid reply linkage")
        if source["thread_id"] is not None:
            require(tables["threads"][source["thread_id"]]["source_system"] == source["source_system"], "thread system mismatch")
        for email in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", source["body"]):
            require(email.lower().endswith(".example"), f"non-reserved source email: {email}")
        require(not re.search(r"\+\d[\d -]{9,}", source["body"]), "possible real phone number in source")
    for evidence in tables["evidence"].values():
        ref(evidence["source_id"], "sources")
        body = sources[evidence["source_id"]]["body"]
        require(0 <= evidence["start"] < evidence["end"] <= len(body), "evidence span outside body")
        require(body[evidence["start"]:evidence["end"]] == evidence["quote"],
                f"evidence quote mismatch: {evidence['evidence_id']}")
    for evidence_id, source_id in (("evidence-mail-aster-private-ref", "mail-aster-private"),
                                   ("evidence-chat-whatsapp-private-ref", "chat-whatsapp-private")):
        ref(evidence_id, "evidence")
        marker = tables["evidence"][evidence_id]
        require(marker["source_id"] == source_id and sources[source_id]["sensitivity"] == "confidential" and
                len(marker["quote"]) >= 8, "privacy leakage probe missing/misclassified")
        require(not any(marker["quote"] in s["body"] for s in sources.values() if s["source_id"] != source_id),
                "confidential marker leaked into another source")
    for person in tables["people"].values():
        if person["email"] is not None:
            require(person["email"].endswith(".example"), "person email is not reserved")
    contact_bindings = {
        "contact-aster-priya": ("person-priya", "sponsor-aster", "priya.nair@aster.example"),
        "contact-aster-neil": ("person-aster-secondary", "sponsor-aster", "@aster-neil-demo"),
        "contact-brightline-devika": ("person-brightline-contact", "sponsor-brightline", "devika.sen@brightline.example"),
        "contact-corvex-arjun": ("person-corvex-contact", "sponsor-corvex", "arjun.rao@corvex.example"),
    }
    require(set(tables["contacts"]) == set(contact_bindings), "contact registry IDs differ from frozen bindings")
    for contact in tables["contacts"].values():
        ref(contact["person_id"], "people")
        ref(contact["sponsor_id"], "sponsors")
        require(tables["people"][contact["person_id"]]["role"] == "sponsor_contact", "non-contact person granted authority")
        address = contact["address"]
        require((contact["person_id"], contact["sponsor_id"], address) == contact_bindings[contact["contact_id"]],
                "contact/person/sponsor/address binding mismatch")
        reserved_email = re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.example", address)
        fictional_handle = re.fullmatch(r"@[A-Za-z][A-Za-z0-9_-]*", address)
        require(reserved_email is not None or fictional_handle is not None, "contact requires reserved email or fictional handle")
        person = tables["people"][contact["person_id"]]
        require(person["email"] is None or person["email"] == address, "contact address/person identity mismatch")
        contact_text = "\n".join(tables["evidence"][i]["quote"] for i in contact["evidence_ids"])
        require(address in contact_text and person["name"] in contact_text, "contact mapping not supported by evidence")
    for alias in tables["aliases"].values():
        ref(alias["entity_id"])
        ref(alias["source_id"], "sources")
        require(alias["alias"] in sources[alias["source_id"]]["body"], "alias absent from supporting source")

    sponsors = tables["sponsors"]
    require(set(sponsors) == {"sponsor-aster", "sponsor-brightline", "sponsor-corvex"}, "wrong sponsor set")
    for identifier, amount in (("sponsor-aster", 10000000), ("sponsor-brightline", 9000000), ("sponsor-corvex", 6000000)):
        sponsor = sponsors[identifier]
        require(sponsor["commitment_paise"] == amount and sponsor["cash_received_paise"] == 0, "baseline financial corruption")
        require(sponsor["tier"] == ("Gold" if amount >= 10000000 else "Silver"), "baseline tier mismatch")
        require(bool(sponsor["contact_ids"]), "sponsor has no contact mapping")
        for contact_id in sponsor["contact_ids"]:
            ref(contact_id, "contacts")
            require(tables["contacts"][contact_id]["sponsor_id"] == identifier, "contact sponsor mismatch")
    require(any(c["person_id"] == "person-priya" and c["sponsor_id"] == "sponsor-aster"
                for c in tables["contacts"].values()), "Priya authority not grounded")
    require(any(c["person_id"] == "person-aster-secondary" and c["sponsor_id"] == "sponsor-aster"
                for c in tables["contacts"].values()), "second contact not authorized for conflict case")
    require(not any(c["person_id"] == "person-unknown" for c in tables["contacts"].values()), "unknown sender granted authority")
    budgets = tables["budgets"]
    require(set(budgets) == {"budget-innovision-2026"}, "wrong budget set")
    budget = budgets["budget-innovision-2026"]
    require(set(budget["sponsor_ids"]) == set(sponsors), "budget sponsor membership mismatch")
    require(set(budget["expense_ids"]) == set(tables["expenses"]), "unreferenced or missing expense")
    for expense in tables["expenses"].values():
        ref(expense["budget_id"], "budgets")
    expense_total = sum(tables["expenses"][i]["amount_paise"] for i in budget["expense_ids"])
    require(expense_total == 22000000, "planned expenses must sum to 22000000")
    require(sum(s["commitment_paise"] for s in sponsors.values()) == 25000000, "baseline commitments mismatch")
    policy = tables["policies"]["policy-tiers-v1"]
    require(policy["benefit_reduction_requires_organizer_approval"], "approval policy missing")
    tiers = index(policy["tiers"], "tier")
    require(set(tiers) == {"Gold", "Silver"}, "tier set mismatch")
    require(tiers["Gold"]["minimum_commitment_paise"] == 10000000 and
            tiers["Silver"]["minimum_commitment_paise"] == 5000000, "tier thresholds mismatch")
    require(tiers["Gold"]["entitlements"] == {"main_stage_banner_logo": True, "sponsor_wall_banner_logo": False,
                                              "social_posts": 2, "stage_mention": True}, "Gold entitlement mismatch")
    require(tiers["Silver"]["entitlements"] == {"main_stage_banner_logo": False, "sponsor_wall_banner_logo": True,
                                                "social_posts": 1, "stage_mention": False}, "Silver entitlement mismatch")
    decisions = tables["decisions"]
    require(set(decisions) == {"DEC-05", "DEC-07"}, "future business decision seeded")
    for decision in decisions.values():
        ref(decision["owner_id"], "people")
        ref(decision["sponsor_id"], "sponsors")
        require(decision["status"] == "pending" and decision["condition_evaluation"] is None, "decision pre-applied")
    require(decisions["DEC-05"]["condition"] is None and decisions["DEC-05"]["sponsor_id"] == "sponsor-aster", "DEC-05 baseline mismatch")
    upgrade = decisions["DEC-07"]
    require(upgrade["optional_cost_paise"] == 2500000 and upgrade["condition"] is not None, "DEC-07 cost/condition missing")
    require(upgrade["condition"]["threshold_paise"] == 2500000, "DEC-07 threshold mismatch")
    ref(upgrade["condition"]["budget_id"], "budgets")
    evidence_refs(upgrade["condition"])

    deliverables = tables["deliverables"]
    require(set(deliverables) == {"D1", "D2", "D3", "D4"}, "wrong deliverable set")
    for identifier, status, reversible, owner in (
        ("D1", "in_production", False, "person-design"), ("D2", "done", False, "person-social"),
        ("D3", "scheduled", True, "person-social"), ("D4", "planned", True, "person-events"),
    ):
        row = deliverables[identifier]
        require((row["status"], row["reversible"], row["owner_id"], row["sponsor_id"]) ==
                (status, reversible, owner, "sponsor-aster"), "deliverable baseline mismatch")
        require(row["kind"] == {"D1": "main_stage_banner_logo", "D2": "social_post", "D3": "social_post", "D4": "stage_mention"}[identifier],
                "deliverable kind/identity mismatch")
        for document_id in row["document_ids"]:
            ref(document_id, "documents")
    require(deliverables["D1"]["external_ref"] == "PH-2231" and deliverables["D1"]["kind"] == "main_stage_banner_logo", "D1 print identity mismatch")
    require(deliverables["D3"]["scheduled_at"] == "2026-11-16T10:00:00+05:30", "D3 schedule mismatch")
    entries = {}
    for document in tables["documents"].values():
        ref(document["source_id"], "sources")
        ref(document["owner_id"], "people")
        require(document["body"] == sources[document["source_id"]]["body"], "document snapshot/body mismatch")
        for entry in document["entries"]:
            require(entry["entry_id"] not in entries, "duplicate document entry ID")
            entries[entry["entry_id"]] = entry
            ref(entry["sponsor_id"], "sponsors")
            ref(entry["deliverable_id"], "deliverables")
            require(entry["text"] in document["body"], "document entry not grounded in body")
            if entry["deliverable_id"]:
                linked = deliverables[entry["deliverable_id"]]
                require(entry["sponsor_id"] == linked["sponsor_id"] and document["document_id"] in linked["document_ids"],
                        "document entry sponsor/deliverable identity mismatch")
            if entry["sponsor_id"]:
                require(sponsors[entry["sponsor_id"]]["name"] in document["body"], "document sponsor identity unsupported")
    require(any(e["deliverable_id"] == "D4" for e in tables["documents"]["doc-run-sheet"]["entries"]), "D4 absent from baseline run sheet")
    scoped_documents = {
        sponsor_id: {d["document_id"] for d in tables["documents"].values()
                     if any(e["sponsor_id"] == sponsor_id for e in d["entries"])}
        for sponsor_id in sponsors
    }
    require(scoped_documents["sponsor-brightline"] == {"doc-brightline-benefits"} and
            scoped_documents["sponsor-aster"] == {"doc-aster-benefits", "doc-run-sheet"},
            "explicit sponsor/document foreign-key discovery mismatch")
    calendars = tables["calendar_items"]
    require("cal-sponsor-review" not in calendars and not any(c["sponsor_id"] == "sponsor-aster" for c in calendars.values()), "future Aster review appointment seeded")
    require("cal-volunteer-briefing" in calendars, "unrelated calendar control missing")
    require(len({c["logical_key"] for c in calendars.values()}) == len(calendars), "duplicate calendar logical identity")
    for item in calendars.values():
        ref(item["owner_id"], "people")
        ref(item["source_id"], "sources")
        ref(item["sponsor_id"], "sponsors")
        require(timestamp(item["starts_at"]) < timestamp(item["ends_at"]), "calendar temporal ordering")
        require(item["logical_key"] != "cal-sponsor-review", "reserved future calendar logical identity seeded")

    graph = data["dependencies.json"]
    nodes = index(graph["nodes"], "node_id")
    edge_ids = index(graph["edges"], "edge_id")
    backing = {"Sponsor": "sponsors", "Commitment": "sponsors", "Event": "events", "Budget": "budgets",
               "Policy": "policies", "Deliverable": "deliverables", "Document": "documents",
               "CalendarItem": "calendar_items", "Person/Role": "people", "Decision": "decisions",
               "SourceMessage": "sources", "Thread": "threads"}
    for node in nodes.values():
        require(node["node_type"] in backing, "no backing contract for graph node type")
        ref(node["record_id"], backing[node["node_type"]])
        require(locations[node["record_id"]] == node["record_file"], "graph record_file mismatch")
        require(node["event_id"] == event_id, "graph node scope mismatch")
        if node["node_type"] == "SourceMessage":
            require(node["record_id"] in historical_source_ids and sources[node["record_id"]]["sensitivity"] != "confidential",
                    "baseline graph exposes hidden/confidential source")
        if node["node_type"] == "Commitment":
            require(sponsors[node["record_id"]]["commitment_id"] == node["node_id"], "commitment node duplicates/wrong identity")
        else:
            require(node["node_id"] == node["record_id"], "graph node identity mismatch")
    signatures = set()
    endpoint_types = {
        "SPONSORS": ({"Sponsor"}, {"Event"}), "HAS_COMMITMENT": ({"Sponsor"}, {"Commitment"}),
        "CONTRIBUTES_TO": ({"Commitment"}, {"Budget"}), "QUALIFIES_UNDER": ({"Commitment"}, {"Policy"}),
        "ENTITLES_TO": ({"Policy"}, {"Deliverable"}), "DOCUMENTED_IN": ({"Deliverable", "Budget", "Decision", "Policy", "Commitment"}, {"Document"}),
        "CONTINGENT_ON": ({"Decision"}, {"Budget"}), "ASSIGNED_TO": ({"Deliverable", "Decision", "Document", "CalendarItem", "Budget", "Task"}, {"Person/Role"}),
        "PART_OF_THREAD": ({"SourceMessage"}, {"Thread"}), "EVIDENCED_BY": (set(backing), {"SourceMessage"}),
        "MENTIONS": ({"SourceMessage", "Document"}, set(backing)),
        "SUPERSEDES": ({"Decision"}, {"Decision"}), "REQUIRES_APPROVAL": (set(backing), {"Decision", "Person/Role"}),
        "DUE_AT": ({"Deliverable", "Task", "Decision"}, {"CalendarItem"}),
        "DEPENDS_ON": (set(backing), set(backing)),
    }
    for edge in edge_ids.values():
        require(edge["from_id"] in nodes and edge["to_id"] in nodes, "unresolved graph endpoint")
        require(edge["event_id"] == event_id and edge["valid_to"] is None and timestamp(edge["valid_from"]) <= now, "graph scope/validity mismatch")
        evidence_refs(edge)
        signature = (edge["from_id"], edge["relation"], edge["to_id"])
        require(signature not in signatures, "duplicate graph relationship")
        signatures.add(signature)
        allowed_from, allowed_to = endpoint_types[edge["relation"]]
        require(nodes[edge["from_id"]]["node_type"] in allowed_from and
                nodes[edge["to_id"]]["node_type"] in allowed_to, "graph relation endpoint type mismatch")
        if edge["relation"] == "ASSIGNED_TO":
            backing_record = records[nodes[edge["from_id"]]["record_id"]]
            expected_owner = backing_record.get("owner_id", "person-finance" if edge["from_id"] == "budget-innovision-2026" else None)
            require(expected_owner is not None and edge["to_id"] == expected_owner, "graph owner/backing-record mismatch")
        cited = [tables["evidence"][i] for i in edge["evidence_ids"]]
        left = records[nodes[edge["from_id"]]["record_id"]]
        right = records[nodes[edge["to_id"]]["record_id"]]
        relation = edge["relation"]
        if relation in ("SPONSORS", "HAS_COMMITMENT"):
            require(bool(set(edge["evidence_ids"]) & set(left["evidence_ids"])) and
                    any(left["name"] in e["quote"] and format(left["commitment_paise"] // 100, ",") in e["quote"] for e in cited),
                    "sponsor/commitment edge lacks relevant amount evidence")
        elif relation in ("CONTRIBUTES_TO", "QUALIFIES_UNDER"):
            require("evidence-tracker-budget-policy" in edge["evidence_ids"] and
                    bool(set(edge["evidence_ids"]) & set(left["evidence_ids"])),
                    "commitment edge lacks tracker relationship evidence")
            if relation == "QUALIFIES_UNDER":
                require("evidence-policy-tiers-body" in edge["evidence_ids"], "qualification edge lacks policy evidence")
        elif relation == "ENTITLES_TO":
            require("evidence-aster-policy-deliverables" in edge["evidence_ids"] and
                    any(edge["to_id"] in e["quote"] and "Aster" in e["quote"] for e in cited),
                    "entitlement edge lacks sponsor/deliverable policy evidence")
        elif relation == "DOCUMENTED_IN":
            require(any(e["source_id"] == right["source_id"] for e in cited), "document edge lacks target-document evidence")
            if nodes[edge["from_id"]]["node_type"] == "Deliverable":
                require(any(e["source_id"] == right["source_id"] and edge["from_id"] in e["quote"] for e in cited),
                        "document edge lacks deliverable-specific span")
        elif relation == "ASSIGNED_TO":
            require(bool(set(edge["evidence_ids"]) & set(left["evidence_ids"])) and
                    any(right["name"] in e["quote"] for e in cited), "owner edge lacks relevant assignment evidence")
        elif relation == "CONTINGENT_ON":
            require(left["condition"] is not None and set(left["condition"]["evidence_ids"]) <= set(edge["evidence_ids"]) and
                    any(edge["from_id"] in e["quote"] and "contingent" in e["quote"] for e in cited),
                    "contingency edge lacks structured-condition evidence")
        elif relation == "REQUIRES_APPROVAL":
            require(bool(set(edge["evidence_ids"]) & set(left["evidence_ids"])) and
                    any((edge["to_id"] if nodes[edge["to_id"]]["node_type"] == "Decision" else right["name"]) in e["quote"] for e in cited),
                    "approval edge lacks relevant authority/decision evidence")
        for evidence_id in edge["evidence_ids"]:
            source = sources[tables["evidence"][evidence_id]["source_id"]]
            require(source["source_id"] in historical_source_ids and source["sensitivity"] != "confidential" and
                    timestamp(source["occurred_at"]) <= now, "hidden/confidential/future evidence in baseline graph")
    for sponsor in sponsors.values():
        require((sponsor["sponsor_id"], "HAS_COMMITMENT", sponsor["commitment_id"]) in signatures and
                (sponsor["commitment_id"], "CONTRIBUTES_TO", "budget-innovision-2026") in signatures,
                "missing sponsor/commitment/budget path")
    require(("commitment-aster", "QUALIFIES_UNDER", "policy-tiers-v1") in signatures, "missing Aster policy path")
    for identifier, row in deliverables.items():
        require(("policy-tiers-v1", "ENTITLES_TO", identifier) in signatures, "missing policy/deliverable path")
        owners = [e["to_id"] for e in graph["edges"] if e["from_id"] == identifier and e["relation"] == "ASSIGNED_TO"]
        require(owners == [row["owner_id"]], "owner_id and ASSIGNED_TO disagree")
        for document_id in row["document_ids"]:
            require((identifier, "DOCUMENTED_IN", document_id) in signatures, "missing deliverable/document path")
    require(("DEC-07", "CONTINGENT_ON", "budget-innovision-2026") in signatures, "missing reverse contingent path")
    policy_targets = {to for _, relation, to in signatures if relation == "ENTITLES_TO"}
    scoped_brightline_targets = {i for i in policy_targets if deliverables[i]["sponsor_id"] == "sponsor-brightline"}
    require(not scoped_brightline_targets and not (scoped_documents["sponsor-brightline"] & scoped_documents["sponsor-aster"]),
            "shared policy/document discovery leaks another sponsor's obligations")
    require(("chat-014", "MENTIONS", "sponsor-aster") not in signatures and
            ("chat-014", "MENTIONS", "D1") not in signatures, "expected inference predeclared in runtime graph")

    trigger = sources["mail-aster-002"]
    wording = "We need to revise Aster Labs' commitment from INR 100,000 to INR 60,000. Please send an updated benefits proposal by 18:00 IST tomorrow."
    require(wording in trigger["body"], "required trigger wording changed")
    require(trigger["in_reply_to"] == "mail-aster-001" and trigger["thread_id"] == "thread-aster" and
            trigger["sender_id"] == "person-priya", "trigger identity/thread mismatch")
    require(trigger["occurred_at"] == "2026-11-14T06:10:00+05:30", "trigger timestamp changed")
    require(sources["mail-aster-001"]["occurred_at"].startswith("2026-10-20T"), "original email date mismatch")
    require(sources["chat-014"]["occurred_at"] == "2026-11-13T21:40:00+05:30" and
            sources["chat-015"]["occurred_at"] == "2026-11-13T22:05:00+05:30", "chat timestamp mismatch")
    require("Aster" in sources["chat-014"]["body"] and "PH-2231" in sources["chat-014"]["body"], "inference evidence missing")
    tomorrow = timestamp(trigger["occurred_at"]).astimezone(now.tzinfo).date() + timedelta(days=1)
    deadline = f"{tomorrow.isoformat()}T18:00:00+05:30"
    require(deadline == "2026-11-15T18:00:00+05:30", "relative deadline incorrect")

    scenarios = tables["scenarios"]
    profiles = tables["outcome_profiles"]
    outcomes = index(data["expected_outcomes.json"]["outcomes"], "scenario_id")
    require(data["expected_outcomes.json"]["test_only"] is True, "oracle not marked test_only")
    require(set(outcomes) == set(scenarios), "scenario/outcome coverage mismatch")
    operational_files = set(SCHEMAS) - {"sources.json", "scenarios.json", "expected_outcomes.json"}
    for baseline in tables["baselines"].values():
        require(baseline["event_id"] == event_id and set(baseline["record_files"]) == operational_files, "baseline record file allowlist mismatch")
        for source_id in baseline["source_ids"]:
            ref(source_id, "sources")
            require(timestamp(sources[source_id]["received_at"]) <= now, "future baseline source")
        require("mail-aster-002" not in baseline["source_ids"], "trigger seeded as historical baseline source")
    for identifier, scenario in scenarios.items():
        label = f"scenario {identifier}"
        require(scenario["event_id"] == event_id, f"{label}: event scope")
        ref(scenario["baseline_id"], "baselines")
        visible = set(scenario["available_source_ids"])
        require(scenario["trigger_source_id"] in visible, f"{label}: trigger not visible")
        require(set(tables["baselines"][scenario["baseline_id"]]["source_ids"]) <= visible, f"{label}: baseline sources missing")
        activations = index(scenario["activation"], "source_id")
        require(set(activations) == visible, f"{label}: activation/visibility mismatch")
        baseline_ids = set(tables["baselines"][scenario["baseline_id"]]["source_ids"])
        require({i for i, a in activations.items() if a["phase"] == "baseline"} == baseline_ids,
                f"{label}: baseline activation phase mismatch")
        orders = [a["order"] for a in scenario["activation"]]
        require(len(orders) == len(set(orders)), f"{label}: duplicate activation order")
        require(orders == sorted(orders), f"{label}: activations not ordered")
        require(activations[scenario["trigger_source_id"]]["phase"] in ("trigger", "after_verified_parent"), f"{label}: trigger phase mismatch")
        for source_id in visible:
            ref(source_id, "sources")
            require(timestamp(sources[source_id]["received_at"]) <= timestamp(scenario["demo_now"]), f"{label}: source not yet received")
            parent = sources[source_id]["in_reply_to"]
            require(parent is None or parent in visible, f"{label}: reply parent invisible")
            require(parent is None or activations[parent]["order"] < activations[source_id]["order"],
                    f"{label}: reply activated before parent")
            phase = activations[source_id]["phase"]
            require((source_id == "mail-aster-clarification") == (phase == "clarification"),
                    f"{label}: clarification phase bypass")
            if phase == "clarification":
                require(identifier == "S1-conflict-clarified" and
                        activations["chat-whatsapp-aster-conflict"]["order"] < activations[source_id]["order"] and
                        any(c["stage"] == "after_clarification" for c in scenario["human_choices"]),
                        f"{label}: clarification must precede its separate approval")
            if source_id not in baseline_ids and phase != "clarification":
                require(phase == ("after_verified_parent" if scenario["inheritance"] else "trigger"),
                        f"{label}: trigger/inherited activation phase mismatch")
        require(max(activations[i]["order"] for i in baseline_ids) < activations[scenario["trigger_source_id"]]["order"],
                f"{label}: trigger activated before baseline")
        for choice in scenario["human_choices"]:
            ref(choice["approver_id"], "people")
            require(tables["people"][choice["approver_id"]]["role"] == "organizer", f"{label}: approver not organizer")
            require(choice["decision"] != "reject" or not choice["approved_scopes"], f"{label}: rejected scopes approved")
            if choice["review_at"]:
                require(timestamp(scenario["demo_now"]) < timestamp(choice["review_at"]) < timestamp(deadline), f"{label}: review outside scheduling window")
        index(scenario["faults"], "fault_id")
        for fault in scenario["faults"]:
            if fault["target_id"] is not None:
                require(fault["target_id"] in records or fault["target_id"] in ("cal-sponsor-review", "privacy_boundary"), f"{label}: fault target unresolved")
            ref(fault["actor_id"], "people")
            if fault["kind"] == "transient_before_write":
                require((fault["target_tool"], fault["target_id"], fault["attempt"], fault["timing"], fault["effect"]) ==
                        ("update_sponsor", "sponsor-aster", 1, "before_write", None), f"{label}: wrong tracker fault")
            elif fault["kind"] == "concurrent_publish":
                require(fault["target_tool"] == "update_deliverable" and fault["target_id"] == "D3" and
                        fault["attempt"] is None and fault["actor_id"] == "person-social" and
                        fault["timing"] == "after_approval_before_cancel" and fault["effect"] == {"status": "done", "version_increment": 1}, f"{label}: wrong concurrent edit")
            elif fault["kind"] == "timeout_after_write":
                require((fault["target_tool"], fault["target_id"], fault["attempt"], fault["actor_id"]) ==
                        ("update_sponsor", "sponsor-aster", 1, None) and fault["timing"] == "after_possible_write" and
                        fault["effect"] is None, f"{label}: invalid timeout selector or fabricated outcome")
            elif fault["kind"] == "permanent_outage":
                require((fault["target_tool"], fault["target_id"]) in
                        (("upsert_calendar_item", "cal-sponsor-review"), ("read_source", "mail-aster-002")) and
                        fault["attempt"] is None and fault["actor_id"] is None and fault["timing"] == "all_attempts" and
                        fault["effect"] is None, f"{label}: invalid permanent fault selector")
            else:
                require(fault["target_tool"] in (None, "privacy_boundary") and fault["target_id"] == "privacy_boundary" and
                        fault["attempt"] == 1 and fault["actor_id"] is None and
                        fault["timing"] == "before_sensitive_context_release" and fault["effect"] is None,
                        f"{label}: invalid privacy fault")
        privacy = scenario["privacy"]
        allowed, denied = set(privacy["allowed_source_ids"]), set(privacy["denied_source_ids"])
        excluded = set(privacy["outgoing_excluded_source_ids"])
        require(allowed.isdisjoint(denied) and allowed | denied == visible and excluded <= visible,
                f"{label}: privacy scope partition invalid")
        confidential = {i for i in visible if sources[i]["sensitivity"] == "confidential"}
        require(confidential <= denied and confidential <= excluded, f"{label}: confidential source not denied/excluded")
        inherit = scenario["inheritance"]
        if inherit is not None:
            require(identifier == "S2-brightline-inherited" and inherit["parent_scenario_id"] == "S1-main-demo" and
                    inherit["include_history"] is True and scenario["memory"]["mode"] == "long_term_inherit", f"{label}: inheritance not verified-actual main demo")
            require(timestamp(scenario["demo_now"]) > timestamp(scenarios["S1-main-demo"]["demo_now"]), f"{label}: parent/child clock ordering")
        else:
            require(scenario["demo_now"] == now.isoformat(), f"{label}: fresh case changed DEMO_NOW")
            require(scenario["memory"]["mode"] != "long_term_inherit", f"{label}: missing inheritance")
        if scenario["memory"]["mode"] == "short_term_resume":
            require(scenario["memory"]["pause_at"] is not None and scenario["memory"]["resume_same_run"] and
                    scenario["memory"]["preserve_committed_effects"], f"{label}: short-term resume loses state")
        outcome = outcomes[identifier]
        if outcome["profile_id"] is not None:
            ref(outcome["profile_id"], "outcome_profiles")
        for support in outcome["rule_support"].values():
            require(bool(support), f"{label}: missing EVT rule support")
            for support_id in support:
                require(support_id in records or support_id in nodes, f"{label}: unresolved rule support {support_id}")
                if support_id in sources:
                    require(support_id in visible, f"{label}: hidden source leaks into rule support")
                elif support_id in tables["evidence"]:
                    require(tables["evidence"][support_id]["source_id"] in visible,
                            f"{label}: hidden source leaks through evidence ID in rule support")
        for owner in outcome["communication"]["recipient_owner_ids"]:
            ref(owner, "people")
        require(outcome["communication"]["drafts_are_not_delivery"], f"{label}: draft implies delivery")
        approved_scopes = {s for c in scenario["human_choices"] if c["decision"] == "approve" for s in c["approved_scopes"]}
        require(not outcome["communication"]["sponsor_send_allowed"] or "sponsor_send" in approved_scopes, f"{label}: send lacks scope")
        require(not outcome["communication"]["internal_posts_allowed"] or "internal_notifications" in approved_scopes, f"{label}: internal post lacks scope")
        if outcome["expectation"] in ("baseline_preserved", "clarification_required", "fail_closed"):
            require(not outcome["communication"]["sponsor_send_allowed"] and not outcome["communication"]["internal_posts_allowed"], f"{label}: blocked case communicates effects")
        if outcome["resolved_deadline"] is not None:
            require(outcome["resolved_deadline"] == deadline, f"{label}: wrong resolved deadline")
        profile = profiles.get(outcome["profile_id"])
        if profile:
            sponsor_effects = index(profile["sponsor_effects"], "sponsor_id")
            blocked = outcome["expectation"] in ("baseline_preserved", "clarification_required", "fail_closed")
            expected_aster = 10000000 if blocked else 6000000
            expected_brightline = 10000000 if identifier == "S2-brightline-inherited" else 9000000
            require(sponsor_effects["sponsor-aster"]["commitment_paise"] == expected_aster and
                    sponsor_effects["sponsor-brightline"]["commitment_paise"] == expected_brightline and
                    sponsor_effects["sponsor-corvex"]["commitment_paise"] == 6000000,
                    f"{label}: independently specified sponsor outcome mismatch")
            d_effects = index(profile["deliverable_effects"], "deliverable_id")
            d_effect = index(profile["decision_effects"], "decision_id")
            if blocked:
                require(d_effects["D3"]["status"] == "scheduled" and d_effects["D4"]["status"] == "planned" and
                        d_effect["DEC-05"]["status"] == "pending" and d_effect["DEC-07"]["status"] == "pending" and
                        profile["review"] is None, f"{label}: rejected/blocked case changed consequential records")
            else:
                require(d_effect["DEC-05"]["status"] == "superseded" and d_effect["DEC-07"]["status"] == "at_risk",
                        f"{label}: required approved decision effects omitted")
                concurrent = any(f["kind"] == "concurrent_publish" for f in scenario["faults"]) or inherit is not None
                require(d_effects["D3"]["status"] == ("done" if concurrent else "cancelled"),
                        f"{label}: ordinary/concurrent D3 outcome mismatch")
                require(d_effects["D4"]["status"] == ("planned" if identifier == "S1-rejected-delta" else "cancelled"),
                        f"{label}: D4 outcome mismatch")
                if identifier in ("S1-rejected-delta", "S1-calendar-outage"):
                    require(profile["review"] is None, f"{label}: fabricated appointment after blocked execution")
                else:
                    require(profile["review"] is not None, f"{label}: approved review predicate omitted")
            for link in profile["inferred_links"]:
                for evidence_id in link["evidence_ids"]:
                    require(tables["evidence"][evidence_id]["source_id"] in visible, f"{label}: inferred evidence hidden")
    require({f["kind"] for f in scenarios["S1-main-demo"]["faults"]} == {"transient_before_write", "concurrent_publish"}, "main demo missing either fault")
    require({f["kind"] for f in scenarios["S1-tracker-failure"]["faults"]} == {"transient_before_write"}, "tracker-only case contaminated")
    require({f["kind"] for f in scenarios["S1-concurrent-edit"]["faults"]} == {"concurrent_publish"}, "concurrent-only case contaminated")
    replay = scenarios["S1-replay"]["replay"]
    require(replay["additional_deliveries"] >= 10 and replay["same_source_identity"] and replay["same_content"], "replay needs ten same-identity replays")
    require("sponsor_send" not in {scope for c in scenarios["S1-main-demo"]["human_choices"] for scope in c["approved_scopes"]}, "main demo sponsor-send not unchecked")
    variants = {
        "S1-authorized-conflict": {"chat-whatsapp-aster-conflict", "mail-aster-002"},
        "S1-conflict-clarified": {"chat-whatsapp-aster-conflict", "mail-aster-002", "mail-aster-clarification"},
        "S1-currency-unresolved": {"mail-aster-currency-unresolved"},
        "S1-tracker-chat-mismatch": {"chat-slack-tracker-mismatch", "mail-aster-002"},
    }
    for scenario_id, required in variants.items():
        require(required <= set(scenarios[scenario_id]["available_source_ids"]), "required isolated variants missing")
    clean = set(scenarios["S1-approved"]["available_source_ids"])
    require(not clean & {"chat-whatsapp-aster-conflict", "mail-aster-currency-unresolved", "mail-aster-unknown",
                         "mail-aster-tentative", "mail-aster-injection", "mail-aster-clarification",
                         "chat-slack-tracker-mismatch", "mail-aster-private", "chat-whatsapp-private"}, "ordinary inbox contaminated by alternatives")
    for profile in profiles.values():
        effects = index(profile["sponsor_effects"], "sponsor_id")
        require(set(effects) == set(sponsors), "oracle sponsor effect set incomplete")
        total = sum(e["commitment_paise"] for e in effects.values())
        require(profile["financials"] == {"currency": "INR", "total_commitments_paise": total,
                                          "planned_expenses_paise": expense_total, "forecast_balance_paise": total - expense_total,
                                          "total_cash_received_paise": 0}, "oracle financial arithmetic mismatch")
        for effect in effects.values():
            amount = effect["commitment_paise"]
            qualifying = [t for t in tiers.values() if amount >= t["minimum_commitment_paise"]]
            require(bool(qualifying), "oracle invented below-Silver treatment")
            require(effect["tier"] == max(qualifying, key=lambda t: t["minimum_commitment_paise"])["tier"] and
                    effect["cash_received_paise"] == 0, "oracle tier/cash mismatch")
        ds = index(profile["deliverable_effects"], "deliverable_id")
        require(set(ds) == set(deliverables), "oracle deliverable coverage incomplete")
        require(ds["D1"]["status"] == "in_production" and ds["D1"]["mutation_actor"] == "none", "D1 changed in oracle")
        require(ds["D2"]["status"] == "done" and ds["D2"]["mutation_actor"] == "none", "D2 changed in oracle")
        if ds["D3"]["status"] == "done":
            require(ds["D3"]["mutation_actor"] == "injected_external" and
                    ds["D3"]["disposition"] in ("over_delivery", "flag_human", "retain"), "D3 publication misattributed")
        if ds["D3"]["status"] == "cancelled":
            require(ds["D3"]["mutation_actor"] == "agent" and ds["D3"]["disposition"] == "cancel", "D3 cancellation mismatch")
        require(ds["D4"]["run_sheet_present"] == (ds["D4"]["status"] != "cancelled"), "D4 lifecycle/run-sheet mismatch")
        decisions_after = index(profile["decision_effects"], "decision_id")
        require(set(decisions_after) == set(decisions), "oracle decision coverage incomplete")
        d5, d7 = decisions_after["DEC-05"], decisions_after["DEC-07"]
        if d5["status"] == "superseded":
            require(d5["superseded_by"] == "DEC-05-SILVER-01" and d5["replacement_status"] == "pending", "DEC-05 supersession/workflow approval confusion")
        else:
            require(d5["status"] == "pending" and d5["superseded_by"] is None, "unexpected DEC-05 status")
        require(d7["status"] in ("pending", "at_risk") and d7["condition_satisfied"] == (total - expense_total >= 2500000), "DEC-07 conditional status mismatch")
        for preserved_id in profile["preserved_ids"]:
            require(preserved_id in records or preserved_id in nodes, "oracle preserved ID unresolved")
        for link in profile["inferred_links"]:
            require(link["from_id"] in nodes and link["to_id"] in nodes, "inferred oracle endpoint unresolved")
            require((link["from_id"], link["relation"], link["to_id"]) not in signatures, "inferred oracle edge already declared")
            evidence_refs(link)
            require(link["from_id"] == "chat-014" and link["relation"] == "MENTIONS" and
                    link["to_id"] in ("sponsor-aster", "D1") and link["evidence_ids"] == ["evidence-chat-014-link"] and
                    tables["evidence"]["evidence-chat-014-link"]["source_id"] == "chat-014" and
                    "Aster" in tables["evidence"]["evidence-chat-014-link"]["quote"] and
                    "PH-2231" in tables["evidence"]["evidence-chat-014-link"]["quote"],
                    "inferred link lacks exact Aster/print-order evidence")
        review = profile["review"]
        if review:
            require(review == {"logical_key": "cal-sponsor-review", "starts_at": "2026-11-15T12:00:00+05:30",
                               "ends_at": "2026-11-15T12:30:00+05:30", "logical_count": 1}, "oracle review appointment mismatch")
    return {"json_files": len(data), "sources": len(sources), "evidence": len(tables["evidence"]),
            "sponsors": len(sponsors), "expenses": len(tables["expenses"]), "people": len(tables["people"]),
            "contacts": len(tables["contacts"]), "deliverables": len(deliverables), "decisions": len(decisions),
            "documents": len(tables["documents"]), "calendar_items": len(calendars),
            "graph_nodes": len(nodes), "declared_edges": len(edge_ids), "scenarios": len(scenarios),
            "outcome_profiles": len(profiles), "outcomes": len(outcomes)}


def self_test(data):
    """Corrupt in-memory copies, never actual fixtures, to prove checks reject them."""
    count = 0
    for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}', '{"a":1e999}'):
        try:
            parse(text)
        except FixtureError:
            count += 1
        else:
            raise FixtureError("strict JSON parser accepted intentional invalid JSON")
    mutations = [
        ("boolean money", lambda d: d["sponsors.json"]["sponsors"][0].update(commitment_paise=True)),
        ("boolean version", lambda d: d["deliverables.json"]["deliverables"][0].update(version=True)),
        ("unknown field", lambda d: d["calendar.json"].update(balance_paise=123)),
        ("missing field", lambda d: d["sources.json"]["sources"][0].pop("sender_id")),
        ("null required field", lambda d: d["sources.json"]["sources"][0].update(sender_id=None)),
        ("duplicate ID", lambda d: d["sponsors.json"]["sponsors"].append(copy.deepcopy(d["sponsors.json"]["sponsors"][0]))),
        ("wrong owner", lambda d: d["deliverables.json"]["deliverables"][0].update(owner_id="person-unknown")),
        ("real-domain contact", lambda d: d["sponsors.json"]["contacts"][0].update(address="someone@gmail.com")),
        ("hash mismatch", lambda d: d["sources.json"]["sources"][0].update(content_hash="0" * 64)),
        ("span mismatch", lambda d: d["sources.json"]["evidence"][0].update(quote="unsupported quote")),
        ("naive timestamp", lambda d: d["sources.json"]["sources"][0].update(occurred_at="2026-10-20T10:00:00")),
        ("unknown graph endpoint", lambda d: d["dependencies.json"]["edges"][0].update(to_id="missing-node")),
        ("future lifecycle", lambda d: d["deliverables.json"]["deliverables"][0].update(status="flag_human")),
        ("oracle arithmetic", lambda d: d["expected_outcomes.json"]["outcome_profiles"][0]["financials"].update(forecast_balance_paise=999)),
        ("oracle exposure", lambda d: d["expected_outcomes.json"].update(test_only=False)),
        ("main fault missing", lambda d: next(s for s in d["scenarios.json"]["scenarios"] if s["scenario_id"] == "S1-main-demo")["faults"].clear()),
        ("replay too short", lambda d: next(s for s in d["scenarios.json"]["scenarios"] if s["scenario_id"] == "S1-replay")["replay"].update(additional_deliveries=9)),
        ("privacy widened", lambda d: next(s for s in d["scenarios.json"]["scenarios"] if s["scenario_id"] == "S1-privacy-scope")["privacy"].update(denied_source_ids=[])),
        ("inherit oracle", lambda d: next(s for s in d["scenarios.json"]["scenarios"] if s["scenario_id"] == "S2-brightline-inherited")["inheritance"].update(state_source="expected_outcomes.json")),
    ]
    def leak_marker(d):
        source = next(s for s in d["sources.json"]["sources"] if s["source_id"] == "mail-aster-unknown")
        marker = next(e for e in d["sources.json"]["evidence"] if e["evidence_id"] == "evidence-mail-aster-private-ref")
        source["body"] += "\n" + marker["quote"]
        source["content_hash"] = hashlib.sha256(source["body"].encode("utf-8")).hexdigest()
    mutations.append(("confidential marker copied to unrestricted source", leak_marker))
    def row(d, table, key, value):
        file = next(name for name in SCHEMAS if table in SCHEMAS[name])
        return next(r for r in d[file][table] if r[key] == value)
    def early_reply(d):
        activation = row(d, "scenarios", "scenario_id", "S1-approved")["activation"]
        parent = next(a for a in activation if a["source_id"] == "mail-aster-001")
        reply = next(a for a in activation if a["source_id"] == "mail-aster-002")
        parent["order"], reply["order"] = reply["order"], parent["order"]
        activation.sort(key=lambda a: a["order"])
    mutations.extend([
        ("invalid offset minutes", lambda d: row(d, "sources", "source_id", "mail-aster-private").update(occurred_at="2026-11-13T18:30:00+05:99")),
        ("noncanonical event timezone", lambda d: row(d, "sources", "source_id", "mail-aster-private").update(occurred_at="2026-11-13T18:30:00+04:30")),
        ("confidential baseline graph node", lambda d: d["dependencies.json"]["nodes"].append({"node_id": "mail-aster-private", "event_id": "event-innovision-2026", "node_type": "SourceMessage", "record_id": "mail-aster-private", "record_file": "sources.json"})),
        ("confidential graph evidence", lambda d: d["dependencies.json"]["edges"][0].update(evidence_ids=["evidence-mail-aster-private-body"])),
        ("hidden oracle evidence", lambda d: row(d, "outcomes", "scenario_id", "S1-approved")["rule_support"]["EVT-DEP-001"].append("evidence-mail-aster-private-body")),
        ("baseline activation moved", lambda d: row(d, "scenarios", "scenario_id", "S1-approved")["activation"][0].update(phase="clarification")),
        ("reply before parent", early_reply),
        ("clarification phase bypass", lambda d: next(a for a in row(d, "scenarios", "scenario_id", "S1-conflict-clarified")["activation"] if a["source_id"] == "mail-aster-clarification").update(phase="trigger")),
        ("contact identity mismatch", lambda d: d["sponsors.json"]["contacts"][0].update(address="arjun.rao@corvex.example")),
        ("chat-only contact assigned Corvex email", lambda d: row(d, "contacts", "contact_id", "contact-aster-neil").update(address="arjun.rao@corvex.example")),
        ("chat-only contact assigned Priya email", lambda d: row(d, "contacts", "contact_id", "contact-aster-neil").update(address="priya.nair@aster.example")),
        ("decision owner edge mismatch", lambda d: row(d, "edges", "edge_id", "edge-DEC05-owner").update(to_id="person-unknown")),
        ("deliverable kind mismatch", lambda d: row(d, "deliverables", "deliverable_id", "D2").update(kind="stage_mention")),
        ("document entry sponsor mismatch", lambda d: row(d, "documents", "document_id", "doc-aster-benefits")["entries"][0].update(sponsor_id="sponsor-corvex")),
        ("reserved baseline logical identity", lambda d: d["calendar.json"]["calendar_items"][0].update(logical_key="cal-sponsor-review")),
        ("unknown fault tool", lambda d: row(d, "scenarios", "scenario_id", "S1-calendar-outage")["faults"][0].update(target_tool="arbitrary_tool")),
        ("unrelated relationship evidence", lambda d: row(d, "edges", "edge_id", "edge-aster-commitment").update(evidence_ids=["evidence-budget-expenses"])),
        ("unrelated inference evidence", lambda d: row(d, "outcome_profiles", "profile_id", "profile-s1-approved")["inferred_links"][0].update(evidence_ids=["evidence-budget-expenses"])),
    ])
    for label, mutate in mutations:
        broken = copy.deepcopy(data)
        mutate(broken)
        try:
            validate(broken)
        except (FixtureError, KeyError, ValueError):
            count += 1
        else:
            raise FixtureError(f"negative self-test accepted: {label}")
    print(f"PASS: {count} intentional corruptions rejected; fixture files unchanged")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="also reject deliberately corrupted in-memory copies")
    args = parser.parse_args()
    try:
        data = load(Path(__file__).resolve().parent)
        counts = validate(data)
        print("PASS: strict parsing, closed schemas, IDs/references, evidence/hash/spans, temporal ordering,")
        print("      graph paths/provenance, scenario isolation, privacy descriptors, and oracle consistency")
        print(json.dumps(counts, sort_keys=True))
        if args.self_test:
            self_test(data)
        print("NOT RUN: application workflow, approval enforcement, retries/replans, replay, delivery, privacy enforcement, durability")
        return 0
    except (FixtureError, ValueError, KeyError, OSError, UnicodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
