# Demo plan and viva guide

For teammates building the slides and preparing for the viva. It explains what we are building for the prototype, the ideas behind it, and what we deliberately left out. Full design detail is in `temp/PROJECT_B_BLUEPRINT.md`; the test data contract is in `data/fixtures/README.md`.

_Written 2026-11-14 06:40 IST. Implementation is in progress on branch `codex/demo-core`._

## 1. The problem in one paragraph

Event teams make promises across many tools: email, team chat, a tracker, a budget sheet, documents, a calendar. When one fact changes (a sponsor cuts their money), every dependent promise silently goes stale. People find out late, after a banner is printed or a post goes live. MetaVision is a "second brain" that notices the change, works out everything it affects, proposes a safe plan, asks a human to approve, carries the plan out across the apps, survives tool failures and conflicting edits, and proves the final state is correct.

## 2. The demo story (scenario `S1-main-demo`)

All data is synthetic (`data/fixtures/`). Fictional people, simulated Gmail/Slack/tracker.

**Before:** Aster Labs is a Gold sponsor at INR 100,000. Budget: commitments INR 2,50,000 (Aster 1,00,000 + Brightline 90,000 + Corvex 60,000) against planned expenses INR 2,20,000, so forecast balance is +INR 30,000. Aster's Gold deliverables are mid-stream:

| ID | Deliverable | State before | Can it be undone? |
|---|---|---|---|
| D1 | Main-stage banner logo (print order PH-2231) | in production | No |
| D2 | Social post #1 | published | No |
| D3 | Social post #2 | scheduled 16 Nov 10:00 | Yes, until published |
| D4 | Stage mention (in the run sheet) | planned | Yes |

Decision DEC-07 (optional INR 25,000 DJ upgrade) is approved only if forecast balance ≥ INR 25,000.

**Trigger (14 Nov 06:10):** Priya (Aster's registered contact) emails: "revise Aster Labs' commitment from INR 100,000 to INR 60,000 … send an updated benefits proposal by 18:00 IST tomorrow."

**What the system works out:**

- INR 60,000 drops Aster from Gold to **Silver** (Silver = sponsor-wall logo, 1 social post, no stage mention).
- New budget: 2,10,000 − 2,20,000 = **−INR 10,000 deficit**.
- **DEC-07 becomes at risk**: its condition (balance ≥ 25,000) is now false. The system does not reject it and does not invent cost cuts; it flags it for a human.
- **D1**: irreversible, already printing → flag for human decision.
- **D2**: already published → counts as Silver's one post (satisfied).
- **D3**: still reversible → cancel.
- **D4**: Silver has no stage mention → cancel and remove it from the run sheet.
- DEC-05 (approve Aster's Gold package) is superseded by a new pending Silver package decision.
- A review meeting is booked for 15 Nov 12:00–12:30, before the 18:00 deadline.
- Internal messages are posted to design, social, events, finance; a reply to Priya is **drafted but not sent** (sending needs its own approval).

**Things that go wrong on purpose (fault injection), and how the system recovers:**

1. **Tracker fails once** while updating Aster's commitment. It is a transient error that happens before any write, so a bounded retry is safe. Second attempt succeeds.
2. **A teammate publishes D3** right after approval, just before our agent cancels it. The agent's cancel sees the record changed (version 1 → 2), so it **does not overwrite** it. It stops the dependent steps, re-reads the current state, and makes **plan v2**: D3 stays published and is flagged as over-delivery. Only the changed parts (benefits document, messages, draft) need **re-approval (delta approval)**. Work already done (sponsor update, DEC-07, D4) is reused, not repeated.
3. **Replay:** the same email is delivered again. Nothing happens twice (zero duplicate effects).

**After:** every changed record is read back and checked (verification), and every step is in the action log.

## 3. The six agents

| Agent | Job | In the demo |
|---|---|---|
| Communication | Reads messages, extracts the change, checks the sender is authorised | "Priya, verified Aster contact: 1,00,000 → 60,000, deadline 15 Nov 18:00" |
| Knowledge | Walks the dependency graph to find everything affected | Sponsor → commitment → budget → DEC-07; policy → D1–D4 → documents; chat-014 mentions PH-2231 = D1 |
| Planning | Turns the impact into exact actions with before/after diffs and flags | Plan v1 (≈13 actions, 5 flags), later plan v2 |
| Execution | Calls the simulated tools, with retries and version checks | Tracker retry; D3 version conflict |
| Verification | Reads every changed record back and checks it | Deficit, tiers, run sheet, one review meeting, untouched records |
| Coordinator | Runs the order, holds the approval gate, decides retry vs replan | Pauses for approval; routes conflict to replan |

## 4. Concepts to know for the viva

**Dependency graph.** Records are nodes (sponsor, commitment, budget, policy, deliverable, document, decision, person). Relations are edges (HAS_COMMITMENT, CONTRIBUTES_TO, ENTITLES_TO, DOCUMENTED_IN, CONTINGENT_ON…). Impact analysis is a graph walk. Example: DEC-07 is found by going *backwards* over "DEC-07 CONTINGENT_ON budget".

**Sponsor-scoped traversal.** The tier policy is shared by all sponsors, so a naive walk would drag in Brightline's and Corvex's items too. We only follow policy → deliverable when the deliverable belongs to the active sponsor. Brightline and Corvex stay untouched (and verification checks that).

**Inferred links.** chat-014 says "Aster … order PH-2231". PH-2231 is D1's print order, so the system infers "chat-014 MENTIONS D1". It is marked *inferred*, not treated as declared fact.

**Versioned records (optimistic concurrency).** Every record has a version number. An update says "I expect version 1". If someone else changed it (now version 2), the write is refused instead of silently overwriting their work. That is how the D3 conflict is caught.

**Retry vs replan.** A transient failure before writing (tracker blip) → retry the same action. A version conflict (the world changed) → retrying would be wrong; the system must re-read and re-plan. Telling these apart is a key reliability point.

**Idempotency keys.** Each action gets a key computed from what it does (target + exact changes). The ledger remembers committed keys. Same key again → reused, not repeated. That gives zero duplicates on replay and lets plan v2 reuse finished v1 work. Changed content → new key → needs fresh approval.

**Human-in-the-loop approval with scopes.** Three independent permissions: business records, internal notifications, sponsor send. In the demo the organiser approves the first two; the sponsor reply stays a draft. Plan v2 needs **delta approval**: only the changed actions are re-approved; the old approval cannot authorise new content.

**Read-back verification.** "The tool said OK" is not proof. After execution, Verification re-reads each record and compares it with the plan, and recomputes the money from scratch.

**Honest flags instead of invented fixes.** Deficit, DEC-07, D1, D3 over-delivery and missing sponsor-wall coverage are surfaced to humans. The system never invents expense cuts or extra print orders.

**Audit trail / action log.** Every agent step, tool call, retry, conflict, approval and verification is logged with time and actor.

## 5. Architecture (prototype)

- **Python 3.12 + uv**, **Streamlit** UI, **SQLite** for state (records, version history, operations ledger, action log).
- `second_brain/storage.py`: loads fixtures into SQLite, versioned reads/writes, ledger, log.
- `second_brain/tools.py`: simulated apps (tracker, budget, documents, calendar, chat, email drafts) with fault injection.
- `second_brain/agents.py`: Communication, Knowledge, Planning, Verification.
- `second_brain/workflow.py`: Coordinator and Execution (approval gate, retry, conflict → plan v2, replay).
- `app.py`: Streamlit screens (step panels, dependency graph, agent timeline, approve buttons, action log).
- Gemini extraction toggle is optional; the default is deterministic rules so the demo always works offline.

## 6. What we cut for the prototype (say this honestly if asked)

- LangGraph checkpointing and resume-after-crash (plain Python orchestrator instead; same logic, no durable restart).
- Live Gmail/Slack connectors (simulated with synthetic data).
- The other 23 test scenarios (unknown sender, conflicting claims, privacy denial, calendar outage, Brightline follow-up). The data for them exists in `data/fixtures/scenarios.json`; the prototype runs the main one.
- Full test suite (one end-to-end smoke test).

## 7. Suggested slide outline

1. Problem: one change, many stale promises (show the 5 apps).
2. Our idea: a second brain with six cooperating agents.
3. Demo scenario: Aster 1,00,000 → 60,000.
4. Impact graph (screenshot of cascade).
5. Plan with flags: D1 irreversible, DEC-07 at risk, −10,000 deficit.
6. Reliability: retry vs replan, version conflict, delta approval, zero duplicates.
7. Human in control: scoped approvals, drafts not sent.
8. Verification and audit log.
9. Architecture diagram.
10. Limitations and next steps (live connectors, LangGraph durability, more scenarios).

## 8. Likely viva questions

- *Why not let the AI just update everything?* Irreversible actions and money need human judgement; we propose, a human approves, then we verify.
- *How do you avoid doing something twice?* Idempotency keys plus a ledger; replay shows zero new effects.
- *What if two people edit the same thing?* Version check refuses the stale write; we re-plan instead of overwriting.
- *Why is DEC-07 "at risk" and not "rejected"?* Rejecting is a business decision for a human; we only report the condition is now false.
- *How do you know the final state is right?* Independent read-back of every record plus recomputed totals.
- *Where is the AI?* Extraction from free-text messages (rules by default, Gemini optional) and impact reasoning over the graph; the risky parts are deterministic and checked.
- *How does it scale to real tools?* Each simulated tool becomes a connector with the same interface (versioned read/write, idempotency key).
