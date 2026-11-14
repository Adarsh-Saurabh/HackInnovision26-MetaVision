"""Deterministic agents for the MetaVision Second Brain demo (S1-main-demo).

Communication -> Knowledge -> Planning -> (executor) -> Verification.
Pure stdlib, no network. All money is integer paise.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .storage import Store

IST = timezone(timedelta(hours=5, minutes=30))
BUDGET_ID = "budget-innovision-2026"
POLICY_ID = "policy-tiers-v1"
POST_RECIPIENTS = ["person-design", "person-social", "person-events", "person-finance"]
UNRELATED_RUN_ENTRIES = ["entry-run-welcome", "entry-run-housekeeping", "entry-run-closing"]
OTHER_SPONSOR_COMMITMENTS = {"sponsor-brightline": 9000000, "sponsor-corvex": 6000000}

_ENTITLEMENT_FOR_KIND = {
    "main_stage_banner_logo": "main_stage_banner_logo",
    "sponsor_wall_banner_logo": "sponsor_wall_banner_logo",
    "stage_mention": "stage_mention",
}


# --------------------------------------------------------------------------- helpers

def inr(paise: int | None) -> str:
    """Format paise as 'INR 60,000' (whole rupees when exact)."""
    if paise is None:
        return "INR ?"
    sign = "-" if paise < 0 else ""
    rupees, rem = divmod(abs(int(paise)), 100)
    return f"{sign}INR {rupees:,}" + (f".{rem:02d}" if rem else "")


def _rupees_to_paise(text: str) -> int:
    text = text.replace(",", "")
    if "." in text:
        whole, frac = text.split(".", 1)
        return int(whole or 0) * 100 + int((frac + "00")[:2])
    return int(text) * 100


def _person_name(store: "Store", person_id: str | None) -> str:
    rec = store.get("person", person_id) if person_id else None
    return rec["name"] if rec else (person_id or "unknown")


def _evidence_ids_for(store: "Store", source_id: str, suffixes: tuple[str, ...] = ("body",)) -> list[str]:
    """Evidence rows for a source. Uses a store listing if one exists, else id convention."""
    for attr in ("evidence_for_source", "evidence_for"):
        fn = getattr(store, attr, None)
        if callable(fn):
            try:
                rows = fn(source_id) or []
                ids = [r["evidence_id"] if isinstance(r, dict) else r for r in rows]
                wanted = [i for i in ids if any(i.endswith("-" + s) for s in suffixes)]
                if wanted:
                    return wanted
            except Exception:  # noqa: BLE001 - fall back to convention
                pass
    out = []
    for s in suffixes:
        eid = f"evidence-{source_id}-{s}"
        try:
            ev = store.evidence(eid)
        except Exception:  # noqa: BLE001
            ev = None
        if ev is not None:
            out.append(eid)
    return out


def _find_alias_sponsor(store: "Store", body: str) -> tuple[str | None, str | None]:
    """Longest-first, case-insensitive alias match. Returns (sponsor_id, alias)."""
    candidates: list[tuple[str, str]] = []
    for a in store.list("alias"):
        if str(a.get("entity_id", "")).startswith("sponsor-"):
            candidates.append((a["alias"], a["entity_id"]))
    for s in store.list("sponsor"):
        candidates.append((s["name"], s["sponsor_id"]))
    candidates.sort(key=lambda c: (-len(c[0]), c[0]))
    low = body.lower()
    best: tuple[int, int, str, str] | None = None  # (pos, -len, sponsor, alias)
    for alias, sid in candidates:
        m = re.search(r"(?<![A-Za-z0-9])" + re.escape(alias.lower()) + r"(?![A-Za-z0-9])", low)
        if m:
            key = (m.start(), -len(alias), sid, alias)
            if best is None or key < best:
                best = key
    return (best[2], best[3]) if best else (None, None)


def _op_key(store: "Store", proposal: dict, tool: str, target_id: str, changes: dict) -> str:
    src = store.source(proposal["source_id"]) or {}
    payload = [store.scenario["scenario_id"], proposal["source_id"], src.get("content_hash"),
               tool, target_id, changes]
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# --------------------------------------------------------------------------- 1. communication

def communication_agent(store: "Store", source_id: str) -> dict:
    """Rule-based extraction of a commitment-change request from one source."""
    src = store.source(source_id) or {}
    body = src.get("body", "") or ""
    sender_id = src.get("sender_id")
    occurred_at = src.get("occurred_at") or store.demo_now

    sponsor_id, alias = _find_alias_sponsor(store, body)
    sponsor = store.get("sponsor", sponsor_id) if sponsor_id else None

    # Amounts
    old_paise = new_paise = None
    currency = None
    m = re.search(r"from\s+INR\s*([\d,]+(?:\.\d+)?)\s+to\s+INR\s*([\d,]+(?:\.\d+)?)", body, re.I)
    confirmed = re.search(r"commitment\s+is\s+INR\s*([\d,]+(?:\.\d+)?)", body, re.I)
    if confirmed:
        # e.g. "our confirmed revised commitment is INR 60,000 ... The original INR 100,000 agreement"
        new_paise, currency = _rupees_to_paise(confirmed.group(1)), "INR"
        orig = re.search(r"original\s+INR\s*([\d,]+(?:\.\d+)?)", body, re.I)
        old_paise = _rupees_to_paise(orig.group(1)) if orig else None
    elif m:
        old_paise, new_paise, currency = _rupees_to_paise(m.group(1)), _rupees_to_paise(m.group(2)), "INR"
    else:
        amounts = re.findall(r"INR\s*([\d,]+(?:\.\d+)?)", body)
        if len(amounts) >= 2:
            old_paise, new_paise, currency = _rupees_to_paise(amounts[0]), _rupees_to_paise(amounts[1]), "INR"
        elif len(amounts) == 1:
            new_paise, currency = _rupees_to_paise(amounts[0]), "INR"

    # Deadline: "by HH:MM IST today|tomorrow"
    deadline = None
    d = re.search(r"by\s+(\d{1,2}):(\d{2})\s*IST\s+(today|tomorrow)", body, re.I)
    if d:
        base = datetime.fromisoformat(occurred_at).astimezone(IST).date()
        if d.group(3).lower() == "tomorrow":
            base = base + timedelta(days=1)
        deadline = datetime(base.year, base.month, base.day, int(d.group(1)), int(d.group(2)),
                            tzinfo=IST).isoformat()

    requested = None
    r = re.search(r"send (?:an |the )?(updated benefits proposal|updated [a-z ]+?proposal)", body, re.I)
    if r:
        requested = r.group(1).lower()

    # Authority
    contact = None
    for c in store.list("contact"):
        if c.get("person_id") == sender_id and c.get("sponsor_id") == sponsor_id:
            contact = c
            break
    authority = contact.get("authority") if contact else None
    authorized = authority == "commitment_contact"

    current_paise = sponsor.get("commitment_paise") if sponsor else None
    sponsor_name = sponsor["name"] if sponsor else None
    sender_name = _person_name(store, sender_id)

    evidence_ids = _evidence_ids_for(store, source_id) or [f"evidence-{source_id}-body"]

    who = sponsor_name or "an unknown sponsor"
    possessive = who + ("'" if who.endswith("s") else "'s")
    nice_deadline = (datetime.fromisoformat(deadline).strftime("%d %b %H:%M IST") if deadline else None)
    summary = (f"{sender_name} asked to revise {possessive} commitment "
               f"from {inr(old_paise)} to {inr(new_paise)}"
               + (f" and requested an {requested} by {nice_deadline}" if requested and deadline else "") + ".")

    proposal = {
        "proposal_id": f"prop-{source_id}",
        "source_id": source_id,
        "sender_id": sender_id,
        "contact_id": contact["contact_id"] if contact else None,
        "authority": authority,
        "authorized": authorized,
        "sponsor_id": sponsor_id,
        "sponsor_name": sponsor_name,
        "field": "commitment_paise",
        "old_paise": old_paise,
        "new_paise": new_paise,
        "currency": currency,
        "current_paise": current_paise,
        "old_matches_current": old_paise is not None and old_paise == current_paise,
        "deadline": deadline,
        "requested": requested,
        "evidence_ids": evidence_ids,
        "method": "fixture-rules",
        "confidence": 0.97,
        "summary": summary,
    }

    store.log("Communication", f"Read {source_id} from {sender_name} ({src.get('source_system', 'source')}).")
    if sponsor_id:
        store.log("Communication", f"Resolved sponsor alias '{alias}' to {sponsor_name} ({sponsor_id}).")
    store.log("Communication",
              f"Extracted commitment change {sponsor_name} {inr(old_paise)} → {inr(new_paise)}",
              "extract", {"old_paise": old_paise, "new_paise": new_paise})
    if authorized:
        store.log("Communication",
                  f"Sender {sender_name} verified as {alias or sponsor_name} commitment contact ({proposal['contact_id']}).",
                  "verify")
    else:
        store.log("Communication", f"Sender {sender_name} is NOT a registered commitment contact for {sponsor_name}.",
                  "warning")
    if not proposal["old_matches_current"]:
        store.log("Communication",
                  f"Stated old amount {inr(old_paise)} does not match tracker {inr(current_paise)}.", "warning")
    if deadline:
        store.log("Communication", f"Resolved deadline '{d.group(0)}' to {deadline}.")
    return proposal


# --------------------------------------------------------------------------- 2/3. finance + policy

def compute_financials(store: "Store", commitment_overrides: dict[str, int] | None = None) -> dict:
    """Commitments, planned expenses and forecast balance for the event budget."""
    overrides = commitment_overrides or {}
    budget = store.get("budget", BUDGET_ID) or {}
    commitments = cash = 0
    for sid in budget.get("sponsor_ids", []):
        s = store.get("sponsor", sid) or {}
        commitments += int(overrides.get(sid, s.get("commitment_paise", 0)))
        cash += int(s.get("cash_received_paise", 0) or 0)
    expenses = sum(int((store.get("expense", eid) or {}).get("amount_paise", 0))
                   for eid in budget.get("expense_ids", []))
    return {
        "currency": "INR",
        "total_commitments_paise": commitments,
        "planned_expenses_paise": expenses,
        "forecast_balance_paise": commitments - expenses,
        "total_cash_received_paise": cash,
    }


def _policy(store: "Store") -> dict:
    return store.get("policy", POLICY_ID) or {"tiers": []}


def tier_for(store: "Store", commitment_paise: int | None) -> str | None:
    """Highest qualifying tier name, or None when below every minimum."""
    if commitment_paise is None:
        return None
    tiers = sorted(_policy(store).get("tiers", []), key=lambda t: -t["minimum_commitment_paise"])
    for t in tiers:
        if commitment_paise >= t["minimum_commitment_paise"]:
            return t["tier"]
    return None


def entitlements_for(store: "Store", tier: str | None) -> dict:
    """Entitlements dict for a tier name ({} when unresolved)."""
    for t in _policy(store).get("tiers", []):
        if t["tier"] == tier:
            return dict(t["entitlements"])
    return {}


# --------------------------------------------------------------------------- 4. knowledge

def _label(store: "Store", node_id: str, node_type: str) -> str:
    t = node_type
    if t == "Sponsor":
        return (store.get("sponsor", node_id) or {}).get("name", node_id)
    if t == "Commitment":
        for s in store.list("sponsor"):
            if s.get("commitment_id") == node_id:
                return f"{s['name']} commitment ({inr(s['commitment_paise'])})"
    if t == "Deliverable":
        d = store.get("deliverable", node_id) or {}
        kind = d.get("kind", "")
        if kind == "social_post":
            posts = sorted(x["deliverable_id"] for x in store.list("deliverable")
                           if x.get("sponsor_id") == d.get("sponsor_id") and x.get("kind") == "social_post")
            n = posts.index(node_id) + 1 if node_id in posts else 1
            return f"{node_id} social post #{n}"
        return f"{node_id} {kind.replace('_', ' ')}".strip()
    if t == "Decision":
        dec = store.get("decision", node_id) or {}
        short = {"DEC-07": "DJ upgrade", "DEC-05": "Gold package approval"}.get(node_id)
        return f"{node_id} {short or dec.get('title', '')}".strip()
    if t == "Document":
        return (store.get("document", node_id) or {}).get("title", node_id)
    if t == "Person/Role":
        p = store.get("person", node_id) or {}
        return f"{p.get('name', node_id)} ({p.get('role', '')})" if p else node_id
    if t == "Policy":
        return "Tier policy v1"
    if t == "Budget":
        return "Event budget"
    if t == "Event":
        return (store.get("event", node_id) or {}).get("name", node_id)
    if t == "CalendarItem":
        return (store.get("calendar", node_id) or {}).get("title", node_id)
    if t == "SourceMessage":
        src = store.source(node_id) or {}
        return f"{node_id} ({src.get('source_system', 'source')})"
    return node_id


def knowledge_agent(store: "Store", proposal: dict) -> dict:
    """Sponsor-scoped impact discovery over the dependency graph plus inferred chat links."""
    sponsor_id = proposal["sponsor_id"]
    node_types = {n["node_id"]: n["node_type"] for n in store.graph_nodes}
    edges = store.graph_edges

    def out(src: str, rel: str) -> list[str]:
        return [e["to_id"] for e in edges if e["from_id"] == src and e["relation"] == rel]

    def inc(dst: str, rel: str) -> list[str]:
        return [e["from_id"] for e in edges if e["to_id"] == dst and e["relation"] == rel]

    affected: list[str] = []
    used_edges: list[tuple[str, str, str]] = []
    paths: list[str] = []

    def add(*ids: str) -> None:
        for i in ids:
            if i not in affected:
                affected.append(i)

    def use(a: str, rel: str, b: str) -> None:
        if (a, rel, b) not in used_edges:
            used_edges.append((a, rel, b))

    add(sponsor_id)
    commitments = out(sponsor_id, "HAS_COMMITMENT")
    deliverables: list[str] = []
    documents: list[str] = []
    decisions: list[str] = []
    owners: list[str] = []
    for c in commitments:
        add(c)
        use(sponsor_id, "HAS_COMMITMENT", c)
        for b in out(c, "CONTRIBUTES_TO"):
            add(b)
            use(c, "CONTRIBUTES_TO", b)
            for dec in inc(b, "CONTINGENT_ON"):
                add(dec)
                use(dec, "CONTINGENT_ON", b)
                if dec not in decisions:
                    decisions.append(dec)
                paths.append(f"{sponsor_id} → {c} → {b} ← {dec} (CONTINGENT_ON)")
        for p in out(c, "QUALIFIES_UNDER"):
            add(p)
            use(c, "QUALIFIES_UNDER", p)
            for dl in out(p, "ENTITLES_TO"):
                rec = store.get("deliverable", dl) or {}
                if rec.get("sponsor_id") != sponsor_id:
                    continue  # shared policy is not a dependency for other sponsors' deliverables
                add(dl)
                use(p, "ENTITLES_TO", dl)
                if dl not in deliverables:
                    deliverables.append(dl)
                docs_here = out(dl, "DOCUMENTED_IN")
                for doc in docs_here:
                    use(dl, "DOCUMENTED_IN", doc)
                    if doc not in documents:
                        documents.append(doc)
                paths.append(f"{sponsor_id} → {c} → {p} → {dl} → " + ", ".join(docs_here))

    # Explicit sponsor foreign keys in document entries.
    for doc in store.list("document"):
        if any(e.get("sponsor_id") == sponsor_id for e in doc.get("entries", [])):
            if doc["document_id"] not in documents:
                documents.append(doc["document_id"])
                paths.append(f"{doc['document_id']} (entries[].sponsor_id = {sponsor_id})")
    for doc in documents:
        add(doc)
        for dec in out(doc, "REQUIRES_APPROVAL"):
            if node_types.get(dec) != "Decision":
                continue
            add(dec)
            use(doc, "REQUIRES_APPROVAL", dec)
            if dec not in decisions:
                decisions.append(dec)
            paths.append(f"{doc} → {dec} (REQUIRES_APPROVAL)")
    for dl in deliverables:
        add(dl)
    # Owners: forward ASSIGNED_TO only (never reversed).
    for item in deliverables + decisions:
        for person in out(item, "ASSIGNED_TO"):
            use(item, "ASSIGNED_TO", person)
            if person not in owners:
                owners.append(person)
    add(*owners)
    decisions.sort()

    # Inferred links from visible team chat.
    inferred: list[dict] = []
    aliases = [a["alias"] for a in store.list("alias") if a.get("entity_id") == sponsor_id]
    sponsor_rec = store.get("sponsor", sponsor_id) or {}
    if sponsor_rec.get("name"):
        aliases.append(sponsor_rec["name"])
    refs = {d["external_ref"]: d["deliverable_id"] for d in store.list("deliverable")
            if d.get("sponsor_id") == sponsor_id and d.get("external_ref")}
    for src in store.visible_sources():
        if src.get("source_system") != "team_chat":
            continue
        body = src.get("body", "") or ""
        hit_alias = any(re.search(r"(?<![A-Za-z0-9])" + re.escape(a) + r"(?![A-Za-z0-9])", body, re.I)
                        for a in aliases)
        hit_refs = [(ref, dl) for ref, dl in sorted(refs.items()) if ref in body]
        if not (hit_alias and hit_refs):
            continue
        ev = _evidence_ids_for(store, src["source_id"], ("link",))
        inferred.append({"from": src["source_id"], "relation": "MENTIONS", "to": sponsor_id,
                         "inferred": True, "evidence_ids": ev, "reason": "sponsor alias in message"})
        for ref, dl in hit_refs:
            inferred.append({"from": src["source_id"], "relation": "MENTIONS", "to": dl,
                             "inferred": True, "evidence_ids": ev, "reason": f"external ref {ref}"})
            paths.append(f"{src['source_id']} ⇢ {dl} (inferred MENTIONS {ref})")
        add(src["source_id"])
        node_types.setdefault(src["source_id"], "SourceMessage")

    # Visual subgraph: affected nodes + context.
    context: list[str] = []
    event_ids = out(sponsor_id, "SPONSORS")
    context += event_ids
    for s in store.list("sponsor"):
        if s["sponsor_id"] != sponsor_id and s.get("commitment_id"):
            context.append(s["commitment_id"])
    trigger = proposal.get("source_id")
    if trigger and trigger not in affected:
        context.append(trigger)
        node_types.setdefault(trigger, "SourceMessage")
    nodes = [{"id": n, "type": node_types.get(n, "Unknown"), "label": _label(store, n, node_types.get(n, "")),
              "affected": True} for n in affected]
    nodes += [{"id": n, "type": node_types.get(n, "Unknown"), "label": _label(store, n, node_types.get(n, "")),
               "affected": False} for n in context if n not in affected]
    shown = {n["id"] for n in nodes}
    vis_edges = [{"from": a, "relation": r, "to": b, "inferred": False} for a, r, b in used_edges]
    for e in edges:
        key = (e["from_id"], e["relation"], e["to_id"])
        if key in used_edges or e["from_id"] not in shown or e["to_id"] not in shown:
            continue
        if e["relation"] in ("SPONSORS", "CONTRIBUTES_TO", "HAS_COMMITMENT"):
            vis_edges.append({"from": key[0], "relation": key[1], "to": key[2], "inferred": False})
    if trigger:
        vis_edges.append({"from": trigger, "relation": "REQUESTS_CHANGE", "to": sponsor_id, "inferred": False})
    vis_edges += [{"from": i["from"], "relation": i["relation"], "to": i["to"], "inferred": True} for i in inferred]

    new_paise = proposal.get("new_paise")
    fin_before = compute_financials(store)
    fin_after = compute_financials(store, {sponsor_id: new_paise} if new_paise is not None else None)
    tier_before = tier_for(store, proposal.get("old_paise") if proposal.get("old_paise") is not None
                           else proposal.get("current_paise"))
    tier_after = tier_for(store, new_paise)

    impact = {
        "sponsor_id": sponsor_id,
        "affected_ids": affected,
        "nodes": nodes,
        "edges": vis_edges,
        "paths": paths,
        "deliverables": deliverables,
        "documents": documents,
        "decisions": decisions,
        "owners": owners,
        "inferred_links": inferred,
        "financials_before": fin_before,
        "financials_after": fin_after,
        "tier_before": tier_before,
        "tier_after": tier_after,
    }
    store.log("Knowledge", f"Traversed sponsor-scoped graph from {sponsor_id}: {len(affected)} affected nodes.",
              "graph", {"affected_ids": affected})
    store.log("Knowledge", f"Deliverables {', '.join(deliverables)}; documents {', '.join(documents)}; "
                           f"decisions {', '.join(decisions)}.")
    for i in inferred:
        store.log("Knowledge", f"Inferred link: {i['from']} MENTIONS {i['to']} ({i['reason']}).", "inference")
    store.log("Knowledge", f"Tier {tier_before} → {tier_after}; forecast balance "
                           f"{inr(fin_before['forecast_balance_paise'])} → {inr(fin_after['forecast_balance_paise'])}.")
    return impact


# --------------------------------------------------------------------------- 5. planning

def _d3_status_line(dispositions: dict, store: "Store") -> str:
    disp = dispositions.get("D3")
    owner = _person_name(store, (store.get("deliverable", "D3") or {}).get("owner_id"))
    if disp == "over_delivery":
        return f"D3 (second social post) was already published externally by {owner}; it is over-delivery beyond Silver and is flagged, not undone."
    if disp == "cancel":
        return "D3 (second social post) is cancelled before publication."
    return f"D3 status: {disp or 'not affected'}."


def planning_agent(store: "Store", proposal: dict, impact: dict, plan_version: int = 1,
                   parent_plan_id: str | None = None) -> dict:
    """Build an ordered, idempotent action plan from the proposal and current business state."""
    sponsor_id = proposal["sponsor_id"]
    sponsor = store.get("sponsor", sponsor_id) or {}
    sponsor_name = sponsor.get("name", sponsor_id)
    new_paise = proposal["new_paise"]
    fin_after = compute_financials(store, {sponsor_id: new_paise})
    tier_before = impact.get("tier_before") or tier_for(store, proposal.get("old_paise"))
    tier_after = tier_for(store, new_paise)
    ent = entitlements_for(store, tier_after)
    allowed_posts = int(ent.get("social_posts", 0))

    deliverables = [store.get("deliverable", d) for d in impact["deliverables"]]
    deliverables = [d for d in deliverables if d]

    # ---- dispositions
    dispositions: dict[str, str] = {}
    flags: list[str] = []
    # Social posts: delivered posts consume the tier's slots first (id order), then pending ones.
    slots = allowed_posts
    posts = sorted((d for d in deliverables if d["kind"] == "social_post"),
                   key=lambda x: (x["status"] != "done", x["deliverable_id"]))
    for d in posts:
        did = d["deliverable_id"]
        if d["status"] == "done":
            dispositions[did] = "satisfied" if slots > 0 else "over_delivery"
        elif slots > 0 and d["status"] != "cancelled":
            dispositions[did] = "satisfied"
        else:
            dispositions[did] = "cancel" if (d["reversible"] or d["status"] == "cancelled") else "flag_human"
            continue
        slots -= 1
    for d in sorted(deliverables, key=lambda x: x["deliverable_id"]):
        did, kind, status = d["deliverable_id"], d["kind"], d["status"]
        if kind == "social_post":
            continue
        else:
            entitled = bool(ent.get(_ENTITLEMENT_FOR_KIND.get(kind, kind), False))
            if entitled:
                dispositions[did] = "satisfied"
            elif status == "cancelled" or (d["reversible"] and status in ("planned", "scheduled")):
                dispositions[did] = "cancel"
            else:
                dispositions[did] = "flag_human"
    dispositions = dict(sorted(dispositions.items()))

    # Flags are read by the organiser at the approval step, so they are written in plain English.
    for did, disp in dispositions.items():
        d = store.get("deliverable", did) or {}
        what = d.get("kind", "item").replace("_", " ")
        if disp == "flag_human" and d.get("kind") == "main_stage_banner_logo":
            flags.append(f"{did} (main-stage banner logo) is already at the printer and cannot be undone, but "
                         f"{tier_after} sponsors don't get it. A person must decide what to do.")
        elif disp == "flag_human":
            flags.append(f"{did} ({what}) cannot be undone, but the {tier_after} level does not include it. "
                         "A person must decide what to do.")
        elif disp == "over_delivery":
            flags.append(f"{did} ({what}) was already published by a teammate. {tier_after} sponsors get only "
                         f"one post, so this is one extra. It cannot be undone, so it is flagged, not deleted.")

    forecast = fin_after["forecast_balance_paise"]
    if forecast < 0:
        flags.append(f"After this change the budget is short by {inr(-forecast)}. The AI will not invent cost "
                     "cuts; the team must decide.")
    dec07 = store.get("decision", "DEC-07") if "DEC-07" in impact["decisions"] else None
    dec07_at_risk = bool(dec07 and dec07.get("condition")
                         and forecast < dec07["condition"]["threshold_paise"])
    if dec07_at_risk:
        flags.append(f"The DJ upgrade (decision DEC-07) only goes ahead if at least "
                     f"{inr(dec07['condition']['threshold_paise'])} is left over. Now {inr(forecast)} is left, "
                     "so it is marked 'at risk' until someone decides.")
    if ent.get("sponsor_wall_banner_logo") and not any(d["kind"] == "sponsor_wall_banner_logo" for d in deliverables):
        flags.append(f"{tier_after} sponsors should get a logo on the sponsor wall, but no such item exists yet. "
                     "The AI has not ordered a new print.")
    if tier_after is None:
        flags.append("The new amount is below every sponsor level, so the level is unclear. A person must decide.")

    unresolved = []
    if any(v in ("flag_human", "over_delivery") for v in dispositions.values()):
        unresolved.append("Irreversible or over-delivered items ("
                          + ", ".join(k for k, v in dispositions.items() if v in ("flag_human", "over_delivery"))
                          + ") remain flagged human matters.")
    if ent.get("sponsor_wall_banner_logo"):
        unresolved.append("Silver sponsor-wall coverage is missing; no main-stage substitution or replacement printing.")
    unresolved.append("Deficit remedy, DEC-07, and the pending Silver package are not solved by workflow approval.")

    # ---- actions
    actions: list[dict] = []

    def add_action(tool: str, kind: str, target_id: str, changes: dict, *, op: str = "update",
                   scope: str = "business_records", reversible: bool = True, reason: str = "",
                   depends_on: list[str] | None = None, summary: str = "") -> str:
        aid = f"A{len(actions) + 1}"
        rec = store.get(kind, target_id) if op == "update" else None
        before = {k: (rec or {}).get(k) for k in changes} if op == "update" else {}
        actions.append({
            "action_id": aid, "op": op, "tool": tool, "kind": kind, "target_id": target_id,
            "expected_version": (rec or {}).get("version") if op == "update" else None,
            "changes": changes, "before": before, "scope": scope, "reversible": reversible,
            "reason": reason, "depends_on": list(depends_on or []),
            "op_key": _op_key(store, proposal, tool, target_id, changes), "summary": summary,
        })
        return aid

    business: list[str] = []
    a_sponsor = add_action(
        "update_sponsor", "sponsor", sponsor_id, {"commitment_paise": new_paise, "tier": tier_after},
        reason=f"Authorized contact revised commitment to {inr(new_paise)}; policy selects {tier_after}.",
        summary=f"{sponsor_name}: {inr(proposal.get('current_paise'))} {tier_before} → {inr(new_paise)} {tier_after}")
    business.append(a_sponsor)

    if dec07_at_risk:
        cond = dec07["condition"]
        changes = {"status": "at_risk", "condition_evaluation": {
            "observed_paise": forecast, "satisfied": False, "evaluated_at": store.demo_now,
            "evidence_ids": list(cond.get("evidence_ids", []))}}
        business.append(add_action(
            "update_decision", "decision", "DEC-07", changes, depends_on=[a_sponsor],
            reason=f"Forecast {inr(forecast)} is below threshold {inr(cond['threshold_paise'])}.",
            summary=f"DEC-07 → at_risk (forecast {inr(forecast)} < {inr(cond['threshold_paise'])})"))

    dec05 = store.get("decision", "DEC-05") if "DEC-05" in impact["decisions"] else None
    if dec05 and tier_after and tier_after != tier_before:
        new_id = f"DEC-05-{tier_after.upper()}-01"
        a_create = add_action(
            "create_decision", "decision", new_id,
            {"decision_id": new_id, "title": f"Approve Aster's revised {tier_after} promotional package"
             if sponsor_id == "sponsor-aster" else f"Approve {sponsor_name}'s revised {tier_after} promotional package",
             "status": "pending", "owner_id": dec05.get("owner_id", "person-organizer"), "sponsor_id": sponsor_id,
             "condition": None, "optional_cost_paise": None, "currency": "INR", "condition_evaluation": None},
            op="create", depends_on=[a_sponsor],
            reason=f"Benefit reduction requires organizer approval of the {tier_after} package.",
            summary=f"Create {new_id} (pending organizer approval)")
        business.append(a_create)
        business.append(add_action(
            "update_decision", "decision", "DEC-05", {"status": "superseded", "superseded_by": new_id},
            depends_on=[a_create], reason=f"{tier_before} package approval no longer applies.",
            summary=f"DEC-05 → superseded by {new_id}"))

    cancel_ids: dict[str, str] = {}
    run_sheet_aid = None
    # D3 first: the time-sensitive scheduled post is cancelled before other reversible items.
    if dispositions.get("D3") == "cancel":
        cancel_ids["D3"] = add_action(
            "update_deliverable", "deliverable", "D3", {"status": "cancelled"}, depends_on=[a_sponsor],
            reason=f"{tier_after} allows {allowed_posts} social post; D2 already satisfies it and D3 is reversible.",
            summary="D3 second social post → cancelled before publication")
        business.append(cancel_ids["D3"])
    for did in sorted(dispositions):
        if dispositions[did] != "cancel" or did == "D3":
            continue
        d = store.get("deliverable", did)
        cancel_ids[did] = add_action(
            "update_deliverable", "deliverable", did, {"status": "cancelled"}, depends_on=[a_sponsor],
            reason=f"{d['kind'].replace('_', ' ')} is not a {tier_after} entitlement and is reversible.",
            summary=f"{did} {d['kind'].replace('_', ' ')} → cancelled")
        business.append(cancel_ids[did])
        for doc_id in d.get("document_ids", []):
            if doc_id == "doc-aster-benefits":
                continue
            doc = store.get("document", doc_id) or {}
            new_entries = [e for e in doc.get("entries", []) if e.get("deliverable_id") != did]
            run_sheet_aid = add_action(
                "update_document", "document", doc_id, {"entries": new_entries}, depends_on=[cancel_ids[did]],
                reason=f"Remove cancelled {did} entry; leave unrelated entries untouched.",
                summary=f"{doc.get('title', doc_id)}: remove {did} entry")
            business.append(run_sheet_aid)

    benefits = store.get("document", "doc-aster-benefits") if "doc-aster-benefits" in impact["documents"] else None
    a_benefits = None
    if benefits:
        social_owner = _person_name(store, (store.get("deliverable", "D3") or {}).get("owner_id"))
        texts = {
            "flag_human": {
                "D1": "D1 main-stage banner logo (PrintHub order PH-2231) is already in production and irreversible; "
                      f"it is not a {tier_after} entitlement and is flagged for a human decision.",
            },
            "satisfied": {
                "D2": f"D2 first social post is already live and counts as {tier_after}'s one social post.",
            },
            "cancel": {
                "D3": "D3 second social post was cancelled before publication; it is not a "
                      f"{tier_after} entitlement.",
                "D4": f"D4 stage mention is cancelled and removed from the stage run sheet; {tier_after} includes no stage mention.",
            },
            "over_delivery": {
                "D3": f"D3 second social post was published externally by {social_owner}; over-delivery beyond "
                      f"{tier_after}, flagged.",
            },
        }
        new_entries = []
        for e in benefits.get("entries", []):
            did = e.get("deliverable_id")
            disp = dispositions.get(did)
            text = texts.get(disp, {}).get(did) if disp else None
            if text is None and disp:
                text = f"{did}: {disp.replace('_', ' ')} under the revised {tier_after} package."
            new_entries.append({**e, "text": text} if text else dict(e))
        deps = [x for x in (cancel_ids.get("D3"), cancel_ids.get("D4")) if x]
        a_benefits = add_action(
            "update_document", "document", "doc-aster-benefits", {"entries": new_entries}, depends_on=deps,
            reason=f"Benefits document must reflect the revised {tier_after} dispositions.",
            summary=f"{benefits.get('title', 'Benefits doc')}: rewrite D1–D4 entries for {tier_after}")
        business.append(a_benefits)

    a_cal = add_action(
        "create_calendar_item", "calendar", "cal-sponsor-review",
        {"calendar_id": "cal-sponsor-review", "logical_key": "cal-sponsor-review",
         "title": f"Aster sponsorship review ({inr(new_paise)}, {tier_after})"
         if sponsor_id == "sponsor-aster" else f"{sponsor_name} sponsorship review ({inr(new_paise)}, {tier_after})",
         "starts_at": "2026-11-15T12:00:00+05:30", "ends_at": "2026-11-15T12:30:00+05:30",
         "owner_id": "person-organizer", "sponsor_id": sponsor_id, "source_id": proposal["source_id"]},
        op="create", depends_on=[a_sponsor],
        reason="Organizer review of the revised package before the sponsor deadline.",
        summary="Calendar: sponsorship review 15 Nov 12:00 IST")
    business.append(a_cal)

    # ---- internal posts
    d3_line = _d3_status_line(dispositions, store)
    deficit = f"forecast balance {inr(forecast)}"
    post_texts = {
        "person-design": (f"Heads-up: {sponsor_name} revised to {inr(new_paise)} ({tier_after}). D1 main-stage banner "
                          f"(PH-2231) is irreversible and flagged for an organizer decision — no reprint or substitution "
                          f"has been ordered. {d3_line}"),
        "person-social": (f"{sponsor_name} is now {tier_after} ({inr(new_paise)}): one social post. D2 is live and "
                          f"satisfies it. {d3_line}"),
        "person-events": (f"{sponsor_name} is now {tier_after}: D4 stage mention cancelled and its run-sheet entry "
                          f"removed; welcome/housekeeping/closing entries unchanged. Sponsorship review booked "
                          f"15 Nov 12:00 IST. {d3_line}"),
        "person-finance": (f"{sponsor_name} commitment revised {inr(proposal.get('old_paise'))} → {inr(new_paise)}; "
                           f"{deficit}. DEC-07 marked at_risk (condition false); no expense cuts invented. {d3_line}"),
    }
    post_ids = []
    for pid in POST_RECIPIENTS:
        post_ids.append(add_action(
            "post_internal", "post", f"post-{pid}",
            {"post_id": f"post-{pid}", "recipient_id": pid, "channel": "team_chat", "text": post_texts[pid]},
            op="create", scope="internal_notifications", reversible=False, depends_on=list(business),
            reason="Owner of an affected item must be informed after business records are read back.",
            summary=f"Notify {_person_name(store, pid)}"))

    # ---- sponsor draft (never sent)
    priya = _person_name(store, proposal.get("sender_id")).split(" ")[0]
    dl_text = ("by 18:00 IST on 15 November 2026" if proposal.get("deadline") == "2026-11-15T18:00:00+05:30"
               else f"by {proposal.get('deadline')}")
    d3_sponsor = ("The second social post (D3) has already been published, so it stays live at no change to the "
                  "revised package." if dispositions.get("D3") == "over_delivery"
                  else "The scheduled second social post (D3) has been cancelled before publication.")
    body = (f"Hello {priya},\n\nThank you for letting us know. As requested {dl_text}, here is the updated "
            f"benefits proposal for {sponsor_name} at {inr(new_paise)}, which qualifies for the {tier_after} tier:\n"
            f"- Sponsor-wall banner logo\n- One social post (already live as D2)\n- No stage mention\n\n"
            f"The main-stage banner (D1) was already in production before your note; our organizer will confirm how "
            f"we handle it. {d3_sponsor}\n\nThe revised package is pending organizer approval, and we will confirm "
            f"once it is approved.\n\nRegards,\nKavya Iyer\nInnovision Campus Fest 2026")
    subject = f"Updated {sponsor_name} benefits proposal"
    a_draft = add_action(
        "create_draft", "draft", "draft-aster-reply",
        {"draft_id": "draft-aster-reply", "to_contact_id": proposal.get("contact_id"),
         "subject": subject, "body": body, "sent": False},
        op="create", scope="business_records", reversible=True,
        depends_on=[x for x in (a_sponsor, a_benefits) if x],
        reason="Sponsor asked for an updated proposal; drafts are not delivery.",
        summary=f"Draft reply to {_person_name(store, proposal.get('sender_id'))} (not sent)")
    # Sending is a separate action in its own scope: it only runs if 'sponsor_send' is approved,
    # and the exact body is part of its identity, so a changed v2 reply needs fresh approval.
    add_action(
        "send_email", "outbox", "sent-aster-reply",
        {"message_id": "sent-aster-reply", "draft_id": "draft-aster-reply",
         "to_contact_id": proposal.get("contact_id"), "subject": subject, "body": body},
        op="create", scope="sponsor_send", reversible=False, depends_on=[a_draft],
        reason="Deliver the approved reply to the sponsor contact.",
        summary=f"Send reply to {_person_name(store, proposal.get('sender_id'))}")

    plan = {
        "plan_id": f"plan-v{plan_version}", "version": plan_version, "parent_plan_id": parent_plan_id,
        "proposal_id": proposal["proposal_id"], "created_at": store.demo_now,
        "financials": fin_after, "tier_before": tier_before, "tier_after": tier_after,
        "dispositions": dispositions, "flags": flags, "unresolved": unresolved, "actions": actions,
    }
    store.log("Planning", f"Plan v{plan_version}: {len(actions)} actions, {len(flags)} flags.", "plan",
              {"plan_id": plan["plan_id"], "dispositions": dispositions})
    store.log("Planning", "Dispositions: " + ", ".join(f"{k}={v}" for k, v in dispositions.items()))
    for f in flags:
        store.log("Planning", f"Flag: {f}", "flag")
    return plan


# --------------------------------------------------------------------------- 6. verification

def verification_agent(store: "Store", plan: dict, receipts: dict[str, dict]) -> dict:
    """Read back every committed/reused action and the cross-record invariants."""
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    skipped = []
    for a in plan["actions"]:
        rcpt = receipts.get(a["op_key"])
        if not rcpt or rcpt.get("status") not in ("committed", "reused"):
            skipped.append(a["action_id"])
            continue
        rec = store.get(a["kind"], a["target_id"])
        if rec is None:
            check(f"{a['action_id']} {a['tool']} {a['target_id']}", False, "record not found on read-back")
            continue
        bad = [k for k, v in a["changes"].items() if rec.get(k) != v]
        check(f"{a['action_id']} {a['tool']} {a['target_id']}", not bad,
              "all fields match" if not bad else f"mismatch: {', '.join(bad)}")

    done_targets = {a["target_id"] for a in plan["actions"]
                    if (receipts.get(a["op_key"]) or {}).get("status") in ("committed", "reused")}

    fin = compute_financials(store)
    if "sponsor-aster" in done_targets:
        check("financials recomputed", fin == plan["financials"],
              f"forecast {inr(fin['forecast_balance_paise'])} vs plan "
              f"{inr(plan['financials']['forecast_balance_paise'])}")

    run = store.get("document", "doc-run-sheet") or {}
    entries = run.get("entries", [])
    if "doc-run-sheet" in done_targets:
        check("run sheet has no D4 entry", not any(e.get("deliverable_id") == "D4" for e in entries),
              f"{len(entries)} entries")
    seed = store.baseline("document", "doc-run-sheet") or {}
    original = {e["entry_id"]: e for e in (seed.get("entries") or [])}
    current = {e["entry_id"]: e for e in entries}
    missing = [eid for eid in UNRELATED_RUN_ENTRIES if eid not in current]
    changed = [eid for eid in UNRELATED_RUN_ENTRIES
               if eid in current and eid in original and current[eid] != original[eid]]
    check("unrelated run-sheet entries unchanged", not missing and not changed,
          "welcome/housekeeping/closing intact" if not (missing or changed)
          else f"missing {missing} changed {changed}")

    for sid, expected in OTHER_SPONSOR_COMMITMENTS.items():
        s = store.get("sponsor", sid) or {}
        check(f"{sid} commitment unchanged", s.get("commitment_paise") == expected,
              f"{inr(s.get('commitment_paise'))} (expected {inr(expected)})")

    reviews = [c for c in store.list("calendar") if c.get("logical_key") == "cal-sponsor-review"]
    want = 1 if "cal-sponsor-review" in done_targets else 0
    check(f"exactly {want} sponsor review calendar item", len(reviews) == want, f"found {len(reviews)}")
    check("cal-volunteer-briefing still present", store.get("calendar", "cal-volunteer-briefing") is not None)

    failed = sum(1 for c in checks if not c["ok"])
    report = {"ok": failed == 0, "checks": checks, "failed": failed, "passed": len(checks) - failed,
              "skipped_action_ids": skipped}
    for c in checks:
        if not c["ok"]:
            store.log("Verification", f"FAILED {c['name']}: {c['detail']}", "error")
    store.log("Verification", f"Read-back of changed records {'passed' if failed == 0 else 'FAILED'}: "
                              f"{report['passed']} passed, {failed} failed"
                              + (f"; {len(skipped)} planned action(s) not run because they were not approved "
                                 f"or not reached ({', '.join(skipped)})" if skipped else "") + ".",
              "verify" if failed == 0 else "error")
    return report
