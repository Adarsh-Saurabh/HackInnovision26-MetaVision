# MetaVision — speaker notes and run sheet

Deck: `presentation/MetaVision.pptx` (13 slides: 10 main + 3 backup).
Slot: **10 minutes including demo**. The event brief says 8 + 4, so an 8-minute cut is at the end.

---

## The through-line

> Tools store records. Teams remember dependencies. **MetaVision remembers both — and verifies that it acted correctly.**

Every slide serves one beat of that sentence. If you are running long, cut detail, never cut the demo, approval, or verification.

---

## Timing (10:00)

| Time | Slide | Say this, not everything on the slide |
|---|---|---|
| 0:00–0:40 | 1. Cover | The 6:10 email. One change, many stale promises. |
| 0:40–1:20 | 2. Problem | "The risk is the dependency, not the message." |
| 1:20–2:00 | 3. Idea | Read language; never move money without a human. |
| 2:00–2:50 | 4. Scenario | ₹30,000 cushion becomes a ₹10,000 deficit. Four deliverables, four answers. |
| 2:50–3:40 | 5. Impact map | Inferred vs. declared; second-order DEC-07; sponsor-scoped. |
| 3:40–6:40 | 6 → app → 7 | **Live demo.** Approve → retry → conflict → plan v2 → verify → replay. |
| 6:40–7:30 | 8. Proof | 21/21 checks, 0 duplicates, 78 tests — plus honest gaps. |
| 7:30–8:20 | 9. Architecture | Six narrow agents, one deterministic core. |
| 8:20–9:10 | 10. Close | The quote. Stop. Invite questions. |
| 9:10–10:00 | — | Buffer: overruns, a slow click, one judge question. |

Rehearse to **9:05**, not 10:00.

---

## Demo click order (memorise this)

1. `uv run --locked python -m streamlit run app.py` (Windows: always `python -m`).
2. Sidebar: scenario `S1-main-demo`, **Simulate problems = on**, Gemini off (rules-only is deterministic).
3. **Deliver Priya's email** → **Run the agents**.
4. Show the impact map for ~15 seconds: DEC-07 amber, D1 amber, budget rose.
5. **Approve as organiser (Kavya)** with *Business records* and *Internal notifications* ticked, *Send to sponsor* **unticked**.
6. **Execute approved plan.** Let the tracker retry happen. Do not talk over the log.
7. At the D3 conflict: stop clicking. Read the two lines: "record changed underneath (expected v1, found v2); no write made."
8. **Approve 6 changed actions** → **Execute approved plan**.
9. **Verify the results** → **Replay the email 10 times**.
10. Land on: **Checked: 21 passed, 0 failed** and **0 records changed again**.

If the app misbehaves: switch to `presentation/assets/` screenshots and keep narrating. Do not debug on stage.

---

## Slide-by-slide script

### 1. Cover — 0:40
"At 6:10 this morning, a sponsor cuts their commitment by forty thousand rupees. Somewhere in this team's tools, a banner is already printing and a social post is already scheduled. Nothing in their software connects those facts.

MetaVision is the second brain that notices the change, finds everything it affects, proposes a safe plan, and proves it happened."

### 2. Problem — 0:40
"This is not a missing-data problem. Every app has the right data. The failure is the relationship between them. The print order only exists in chat; the tracker never knew it existed.

So the banner prints, the post goes live, and the deficit is discovered days later."

### 3. Idea — 0:40
"Six small agents: detect, trace, plan, approve, execute, verify. The model is allowed to read language and infer links. It is not allowed to decide money, skip approval, overwrite a newer record, or claim success without reading the record back."

### 4. Scenario — 0:50
"Before: ₹2.5 lakh committed against ₹2.2 lakh of costs — a ₹30,000 cushion. After: ₹2.1 lakh against the same costs — a ₹10,000 hole. Aster drops from Gold to Silver.

Four deliverables, four different answers. The banner is already printing, so a human decides. The published post already satisfies Silver. The scheduled post and the stage mention can be cancelled.

And DEC-07, the optional DJ upgrade, needs a ₹25,000 surplus. It is now at risk — not rejected."

### 5. Impact map — 0:50
"This is the real rendered graph from the run. Three things to notice.

The dashed edge is inferred: chat mentions PH-2231, and PH-2231 is D1's print order. We label inference instead of treating it as fact.

DEC-07 is found by walking backwards over a contingent-on relationship. No keyword search finds that.

And the policy is shared, but the walk only follows it for Aster. Brightline and Corvex stay untouched — verification checks that."

### 6. Approval — 0:30
"Fifteen exact diffs, and three independent permissions. The organiser can approve business records and internal messages while the sponsor reply stays a draft.

The amber list is what we refuse to decide: the printing banner, the deficit, the at-risk decision, and the missing Silver wall logo."

### 7. Demo — 3:00
Use the click order above. Useful lines while clicking:

- "Nothing has been written yet."
- "The tracker failed before writing, so a retry is safe. Same operation key."
- "Rohan published D3 first. Our write was refused. Retrying would be wrong — the world changed, so we replan."
- "Plan v2 reuses four finished actions, keeps three covered, and asks approval for six changed ones."
- "Verification reopens every record; it does not trust the tool's OK."
- "Same email, ten more times. Zero new effects."

### 8. Proof — 0:50
"Twenty-one checks passed after execution. The budget was recomputed from scratch: minus ₹10,000, not copied from the plan. Brightline and Corvex are untouched.

Then replay: ten deliveries, thirteen actions reused, zero records changed again.

And the honest column: 20 of 24 scenarios pass, three are not tested, one known gap. Restart/resume is not built. The connectors are simulated. We would rather say that than be caught."

### 9. Architecture — 0:50
"The coordinator owns order and gates. Communication is the only place a model is genuinely in the loop, and only as a cross-check on extraction. Knowledge walks the graph. Planning is rules. Execution is versioned tool calls. Verification is independent.

State is one SQLite file: versioned records, an idempotency ledger, an append-only log, and a fixed demo clock.

Why not one agent? Separate permissions, logged handoffs, and a verifier that did not do the work."

### 10. Close — 0:50
"Your tools remember records. MetaVision remembers how they depend on each other.

Thank you. We are happy to take the uncomfortable questions."

Then stop talking.

---

## 8-minute cut (if the organisers hold you to the brief)

Target 7:40.

- Slide 1: 0:30
- Slide 2: 0:30
- Slide 3: 0:30
- Slide 4: 0:40
- Slide 5: 0:35
- Demo: **2:30** (skip the impact-map pause; go straight from approval to execute)
- Slide 8: 0:35
- Slide 9: 0:30
- Slide 10: 0:30
- Buffer: 0:20

Skip nothing in the demo except the graph pause. Keep retry, conflict, delta approval, verify, replay.

---

## Q&A — short answers

**Why multi-agent?** Separate permissions and an independent verifier. Handoffs are typed and logged. Only Communication uses a model, and only as a cross-check.

**Why not a script?** Arithmetic and writes are deterministic by design. The graph handles policy-aware impact and recovery; the model handles language.

**Where is the replan?** Concurrent D3 edit → version conflict → plan v2 with a delta classification → fresh approval → reuse of committed actions. It is in the demo.

**Is it really a graph?** Typed nodes, evidence-backed edges with provenance, declared vs. inferred, and a traversal path that selects each affected record.

**What if the model invents an amount?** Span grounding, authority check, agreement with rules, exact-diff approval, integer recomputation, read-back.

**Timeout after a write?** Operation key plus read-back reconciliation. Unknown outcome pauses; it never blindly retries.

**What is live?** Gemini extraction (optional) and the Python engine. Gmail, Slack, Sheets and Calendar are simulated. Simulated sends are not real email.

**Scale?** Each simulated tool becomes a connector with the same contract: versioned read/write, idempotency key, reconcile on timeout. Hosted Postgres and auth are roadmap, not built.

**Two sponsor contacts disagree?** Both in scope → contested, clarification to the primary contact, zero financial writes. We do not pick a winner.

**What is not done?** Restart/resume, calendar outage fallback, live connectors, long-term memory across events (S2). All listed on slide 8.

---

## Numbers to quote (verified today)

- Main demo: **15 actions**, **4 flags**; plan v2 **14 actions**: 4 reused, 3 covered, 7 new/changed (6 in scope for approval).
- Verification: **21 passed, 0 failed**.
- Replay: **10 deliveries, 10 duplicates ignored, 13 actions reused, 0 new effects**.
- Tests: **78 passed** (`uv run --locked python -m pytest -q`).
- Scenario suite: **20 / 24 pass, 1 fail, 3 not tested**.

Do not quote a number you have not seen in today's run.
