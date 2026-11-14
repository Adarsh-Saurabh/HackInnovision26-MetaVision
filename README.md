# MetaVision · Second Brain

HackInnovision 2026, Track B: Agentic Workflow Automation & Context Engineering.

A college fest team keeps its work in email, team chat, a sponsor tracker, a budget sheet, docs and a calendar. When a key sponsor changes their money mid-way, a lot of other things must change too. Second Brain reads the sponsor's email, finds every record the change affects, writes a plan, asks a person to approve it, makes the changes (recovering from tool failures and teammates' edits), and then checks its own work.

All data is synthetic. The apps are simulated in SQLite; no real Gmail, Sheets or Calendar account is touched.

## Run it

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked
uv run streamlit run app.py              # the demo UI, opens http://localhost:8501
uv run pytest -q                         # 67 tests
uv run python scripts/run_scenarios.py   # all 24 dataset scenarios vs expected outcomes
```

Optional live AI reading of the email: copy `.env.example` to `.env`, set `GEMINI_API_KEY`, and turn on "Let Gemini AI read the email" in the sidebar. Without a key, everything runs offline on deterministic rules.

## The demo in 7 clicks

| Step | Button | What you see |
|---|---|---|
| 1 | Deliver Priya's email | Aster Labs cuts its sponsorship from INR 100,000 to INR 60,000 |
| 2 | Run the agents | Sponsor, amount and deadline extracted; impact map of every affected record |
| 3 | Approve as organiser | 15-step plan, 4 items the AI refuses to decide alone, approval by scope |
| 4 | Execute approved plan | Tracker fails once (503) and is retried safely; a teammate publishes a post at the same moment, so our write is refused |
| 5 | Approve 6 changed actions | Plan v2: work already done is reused, only the 6 new or changed steps need approval |
| 6 | Verify the results | Every changed record read back; budget recalculated: 21 checks pass |
| 7 | Replay the email 10 times | 0 duplicate changes |

The right-hand timeline shows every agent step, tool call, retry, conflict and approval as it happens.

## How it meets the brief

| Objective | Where it is shown |
|---|---|
| Extract entities (sponsor, amount, deadline, sender) | Communication agent, step 2; every value is checked against the email text |
| Resolve cross-application dependencies | Knowledge agent, impact map and "How it spreads" tab: sponsor → commitment → tier → deliverables, docs, budget → DJ-upgrade decision |
| Memory | Short-term: versioned records with full history, operations ledger and action log for the run. Long-term: see Limitations |
| Six specialised agents | Communication, Knowledge, Planning, Execution, Verification, Coordinator; each logs its own steps in the timeline |
| Tool failure handled gracefully | Fail-once tracker error retried with the same idempotency key; a timeout after the write is reconciled without writing twice |
| Idempotency | Every action has a key built from its exact content; replaying the email 10 times adds 0 effects |
| Human approval for high-consequence actions | Three approval scopes: business records, internal notifications, sending to the sponsor (off by default; the reply stays a draft) |
| Adaptive replanning | A teammate's concurrent edit causes a version conflict; nothing is overwritten; plan v2 plus re-approval of only the delta |
| Verification checks | Independent read-back of every changed record, recomputed budget, unrelated records unchanged |

## Architecture

```
email / chat ──► Coordinator ──► Communication ──► Knowledge ──► Planning ──► [human approval]
                     │              extract +         graph          plan v1        │
                     │              verify sender     traversal      flags          ▼
                     │                                                         Execution ──► simulated apps
                     │◄──────────── version conflict: replan (plan v2) ◄──────────┘    (tracker, docs,
                     ▼                                                                   calendar, chat, email)
               Verification ──► read back every record, recompute budget ──► summary, ledger, timeline
```

| Part | File |
|---|---|
| Agents (Communication, Knowledge, Planning, Verification) | `second_brain/agents.py` |
| Coordinator + Execution: state machine, approvals, retries, replanning, replay | `second_brain/workflow.py` |
| Simulated apps, fault injection, idempotent tool calls | `second_brain/tools.py` |
| Versioned record store, history, ledger, action log (SQLite) | `second_brain/storage.py` |
| Optional Gemini extraction, used only if grounded in the email and matching the rules | `second_brain/llm.py` |
| UI | `app.py` |
| Synthetic dataset: sources, sponsors, deliverables, decisions, docs, calendar, 24 scenarios, expected outcomes | `data/fixtures/` |

Design choice: the agents are deterministic Python with clear role boundaries, and the language model is kept at the edge (reading the email). Money and approvals are never left to a guess; when the input is unclear the system stops and asks.

## Measured results

- `pytest`: 67 passed.
- `scripts/run_scenarios.py`: **20 of 24 scenarios pass**, 1 fails, 3 are not tested.
  - Passing includes: main demo, tool failure, concurrent edit, timeout after write, replay, rejection, rejected delta, unknown sender (blocked), tentative wording and unclear currency (asks for clarification), conflicting sponsor contacts, prompt injection in an email, unauthorised WhatsApp sender ignored, stale chat, tracker vs chat mismatch, Gmail unavailable and privacy-agent failure (fail closed), privacy scope (confidential sources never reach any agent).
  - Fails: `S2-brightline-inherited` (needs long-term memory carried from run 1).
  - Not tested: `S1-calendar-outage` (permanent outage and fallback approval not simulated), `S1-short-term-approval-resume` and `S1-short-term-partial-resume` (process restart not simulated).

## Assumptions

- Simulated apps and synthetic data, as the brief allows. Amounts are in INR, stored as paise.
- A fixed demo clock (14 Nov 2026, 06:30 IST) so runs are reproducible.
- The dependency graph between records is given by the dataset; the Knowledge agent also infers extra links from chat messages (drawn dashed in the impact map).
- The organiser (Kavya) is the only approver.

## Limitations

- **No long-term memory across runs.** The store lives for one run, so a second scenario cannot recall the first (`S2-brightline-inherited` fails).
- **No restart recovery.** A run paused at approval does not survive a process restart.
- **No separate preflight review** by the Verification agent before approval; the Coordinator's checks before planning take its place.
- Plain Python state machine instead of LangGraph (the original plan); simpler to test within 12 hours.
- Planning texts (team messages, sponsor reply) are tailored to the main Aster scenario.
- No real connectors; the live-adapter design is in the blueprint only.

## More detail

- [Demo plan and viva guide](docs/demo-plan-and-viva-guide.md)
- [Project blueprint](temp/PROJECT_B_BLUEPRINT.md) and [system flowcharts](temp/PROJECT_B_SYSTEM_FLOWCHART.md)
- [Problem statement](HackInnovision2026_PS.pdf)
- [Team setup](setup.md)
