# workDone: Ujjwal

Read **Resume here** first. This is Ujjwal's file; teammates' files are in the same folder. Session log is newest first.

## Resume here

_Updated: 2026-11-14 04:02 IST by Ujjwal session 3. Commit `f418738` on `main` (pushed, in sync with `origin/main`); uncommitted changes: `.claude/settings.json` only (kept local on purpose: contains a machine-specific path)._

**Working on:** planning docs are now consistent: the blueprint, Adarsh's flowchart (`temp/PROJECT_B_SYSTEM_FLOWCHART.md`) and the new plain-language guide (`temp/PROJECT_B_ARCHITECTURE_SIMPLE.md`). Next area: S1 fixtures and expected outcomes, §4/§17.

**Next action:** Agree the P0 split with Adarsh and Vaibhav (§20, 3 people), then write `data/fixtures/` (incl. `scenarios.json`) and hand-written `expected_outcomes.json` for S1 exactly as in blueprint §4.1-§4.5 and §17. No more planning-doc work before code.

**Team P0 progress (§3.1, now 11 items)**, as known at this update
| # | Item | Status | Owner | Where / notes |
|---|---|---|---|---|
| 1 | Seed workspace from fixtures (simulated clock `DEMO_NOW`) | not started | | `data/fixtures/` |
| 2 | Communication: entity extraction with spans | not started | | |
| 3 | Knowledge: resolve sponsor, context bundle, traversal incl. DEC-07 | not started | | |
| 4 | Planning: `EVT-*` rules, mid-stream classification, versioned plan | not started | | §11.2, §11.5 |
| 5 | Verification preflight before approval | not started | | §11.5 |
| 6 | Approval gate (LangGraph interrupt), three scopes | not started | | §13.2 |
| 7 | Execution with operation keys + fail-once tracker retry | not started | | |
| 8 | Adaptive replan on concurrent D3 edit, delta re-approval | not started | | §11.3 |
| 9 | Verification read-back, summary, ledger, agent timeline | not started | | §15 |
| 10 | Replay source message: zero duplicate effects | not started | | |
| 11 | Paused approval survives process restart | not started | | |

**Schedule (§19.2):** 04:02 IST, end of the 02:30-04:00 slot where the deterministic S1 test should already pass; still no code (no fixtures, no `pyproject.toml`). Behind by ~2 slots. At 04:30 apply §19.2 cuts (alias-only inferred edges, no live LLM until UI works); at 06:00, replan at pre-execution revalidation instead of mid-execution.

**Run / test commands that work now:** none yet (no `pyproject.toml`, `uv.lock`, tests, or `app.py`). Git: `git push origin main` works from the agent shell.

**Blockers, open decisions, and needs from teammates:** P0 owner split (§20); Gemini key and model on the team account (§6 lists stable candidates); submission portal and real cutoff (09:30 vs noon, §1); any live connector credential (§26). Skill template in both `update-work-done/SKILL.md` copies says "all 10 P0 items"; blueprint §3.1 now has 11. Teammates: read `temp/PROJECT_B_ARCHITECTURE_SIMPLE.md` for a 10-minute overview.

**Known broken / do not trust:** nothing implemented; all blueprint performance numbers are targets. `uplan-ai` facts in blueprint §1.1 come from a user-supplied report, unverified.

## Session log

### Session 3: 2026-11-14 ~03:20-04:02 IST, flowchart review, simple architecture guide

- **Branch:** `main`
- **Start → end commit:** `a0f113e` → `f418738` (uncommitted changes: yes, `.claude/settings.json` only, intentional)
- **Goal:** Check a pasted "simulated-tools prototype" prompt against the brief; review Adarsh's new flowchart against the blueprint; make the architecture easy for the team to understand.

**Done**
- Reviewed the pasted prompt (fabricated data + SQLite-backed simulated Gmail/Sheets/Calendar, one real connector later). Verdict: matches what blueprint line 11, §12 and §17 already decided. Its first milestone was missing the adaptive replan (P0 #8), mid-stream D1-D4, DEC-07, the knowledge graph and the six agents, so the blueprint stays the source of truth.
- Reviewed `temp/PROJECT_B_SYSTEM_FLOWCHART.md` (Adarsh, `0f2edd8`) against the blueprint: no real conflicts, but too dense. Found 6 small gaps and fixed all of them in `f418738`:
  - §1: a blocking preflight finding now returns to Planning (it had gone to Knowledge), and goes to partial once the replan budget is used up.
  - §13: build order now copies blueprint §19.1.
  - §12: UI panels 3 and 8 marked P1.
  - §6: S1 execution order added (§11.4).
  - §10: run state renamed to `rejected`.
  - Gemini named as the live model.
- Blueprint §14.4: added a `rejected` run status. Rejecting a v2 delta after some effects committed counts as `partial`.
- New `temp/PROJECT_B_ARCHITECTURE_SIMPLE.md`: plain-language team guide. Has the 7-step flow, six agents as jobs, data stores, graph, D1-D4 table, 8 rules, approval, a single execution/reliability diagram, run states, glossary, and a map to the full docs. Every diagram has 10 boxes or fewer. The blueprint wins on any conflict.
- Explained why `/update-work-done` is missing from the model's skill list: `disable-model-invocation: true` hides it on purpose, and the user can still run it.

**Decisions and blueprint deviations**
- The blueprint stays authoritative. The flowchart and the simple guide are companions, edited to match it.
- DEVIATION from setup.md (`codex/<task>` branches): pushed docs straight to `main` again. Use task branches once code starts.

**Verification**
- `git push origin main` succeeded (`0f2edd8..f418738`); `git fetch` showed no newer remote commits first.
- Mermaid diagrams not rendered or checked. No automated tests exist.

### Session 2: 2026-11-14 ~01:35-03:16 IST, blueprint revision 2, merge with Adarsh, push

- **Branch:** `main`
- **Start → end commit:** `e4ac995` → `85bb227` (uncommitted changes: yes, `.claude/settings.json` only, intentional)
- **Goal:** Review the blueprint against the highlighted Track B brief (`Screenshot 2026-11-14 013203.png`), research current APIs, fix and improve the blueprint, reconcile with Adarsh's parallel edit, push.

**Done**
- Reviewed `temp/PROJECT_B_BLUEPRINT.md` against the highlighted brief; found gaps on "multi-agent orchestration", "across email threads", "mid-stream", and "adaptive replanning" (was only P1).
- Rewrote the blueprint as revision 2: replanning in P0 via an injected concurrent edit on D3 (§11.3); mid-stream deliverables D1-D4 with lifecycle status (§4.3, §11.2); second-order cascade via `DEC-07` contingent approval (§4.1, §4.4); multi-source evidence (email thread + team chat, §4.2); declared vs. inferred edges and bi-temporal facts (§9); `AgentMessage` handoff log and agent timeline (§7.2); simulated clock `DEMO_NOW` (§4.1); LangGraph interrupt rules (§13.2).
- Merged Adarsh's `95be237` (uplan-ai lessons §1.1, `EVT-*` rules, `RuleFinding`, Verification preflight phase, compact context, `scenarios.json`, deferred connectors) into rev 2; added `EVT-DLV-001` and `EVT-DEC-001` for the new features (§11.5). P0 grew from 10 to 11 items (preflight is item 5).
- Commits: `e57be24` (merged blueprint), `85bb227` (`AGENTS.md`, `CLAUDE.md`, `workDone/*.md`, both `update-work-done` skill copies, screenshot, `.gitignore` entry for `.claude/settings.local.json`). Both pushed to `origin/main`.

**How**
- Research: LangGraph interrupts docs (node re-runs from start on resume; `Command(resume=...)` same `thread_id`), PyPI `langgraph-checkpoint-sqlite` 3.1.3 (Oct 30 2026), Gemini models page (`gemini-2.5-flash` deprecated, routes to `gemini-3.5-flash-lite` from Dec 1), Graphiti for the bi-temporal pattern.
- Conflict avoidance: `git fetch` + `git diff e4ac995 origin/main` instead of pulling; backed up both versions to the session scratchpad; built the merged file; `git checkout -- temp/PROJECT_B_BLUEPRINT.md`; `git pull --ff-only`; restored the merged file on top; committed. No merge conflict.

**Decisions and blueprint deviations**
- Deadline moved from Nov 14 08:00 to Nov 15 18:00 IST and all time logic uses `DEMO_NOW`: the old deadline is before the 10:00-12:00 presentations.
- Approval node must be pure (no LLM call, no writes before `interrupt()`), because LangGraph re-runs the node on resume and a re-called model could change the plan hash.
- Checkpoints and domain data in separate SQLite files; `check_same_thread=False` + WAL for Streamlit threads.
- Business pending decisions (`decisions` table) kept separate from workflow approvals (`plan_approvals`).
- Merge conflict resolved: Adarsh's "fresh baseline per scenario" kept, with S2 declared as the one exception (it starts from S1's verified end state to show long-term memory).
- DEVIATION from setup.md §1/§7 (`codex/<task>` branches): pushed straight to `main`, matching how Adarsh pushed `95be237`.
- `.claude/settings.json` not committed: contains `//c/Users/ujjwa/...` (setup.md forbids machine-specific paths).

**Problems / dead ends**
- Push from the agent shell failed: `fatal: could not read Username for 'https://github.com': terminal prompts disabled`. `! git push` from chat failed the same way. Fixed by running `git push origin main` in the VS Code terminal (Git Credential Manager browser login); later pushes worked from the agent shell.
- WebFetch of the LangGraph durable-execution page returned the persistence page; used the official-doc search summary instead.
- Session 1 (hand-off tooling) ran in a parallel conversation during this session's time window; its entry predates these commits.

**Verification**
- `git status -sb` → `## main...origin/main` (in sync) at `85bb227`.
- Grep of the merged blueprint confirmed Adarsh's items present (`EVT-SRC-001`, `RuleFinding`, `scenarios.json`, `PyMuPDF`, "Prototype scope, confirmed") alongside rev 2 items.
- Scenario arithmetic checked by hand: S1 250k → 210k vs 220k expenses = −10k; S2 Brightline +10k → balance 0, DEC-07 still blocked.
- No automated tests (none exist yet).

### Session 1: 2026-11-14 ~02:45-03:10 IST, session hand-off tooling

- **Branch:** `main`
- **Start → end commit:** `e4ac995` → `e4ac995` (uncommitted changes: yes)
- **Goal:** Make every future session resumable from files in the repo, for a 3-person team on Claude Code and Codex.

**Done**
- Skill `update-work-done` in two copies: `.claude/skills/update-work-done/SKILL.md` (Claude Code, manual-only via `disable-model-invocation: true`, run `/update-work-done [note]`) and `.agents/skills/update-work-done/SKILL.md` + `agents/openai.yaml` (Codex, `allow_implicit_invocation: false`, run `$update-work-done`).
- `workDone/` folder with one file per teammate: `ujjwal.md`, `adarsh.md`, `vaibhav.md`. Replaced the earlier single `workDone.md`.
- `CLAUDE.md` and `AGENTS.md`: tell new sessions to read all `workDone/*.md` files first.

**How**
- Each file: "Resume here" snapshot overwritten each run + newest-first session log. A new session reads the top of each file.
- Skill picks the file by matching `git config user.name`, asks if unset; edits only that file, reads the others to build a team-wide P0 table (§3.1) with an Owner column.
- Evidence first: git log/diff since the person's previous end commit, test run if available; `verified` only with proof.

**Decisions and blueprint deviations**
- One file per person instead of one shared file: parallel updates from three people would conflict in Git on every push.
- Two skill copies because Claude Code scans `.claude/skills/` and Codex scans `.agents/skills/`; they differ only in frontmatter and the note line. Edit both together.
- Not committed: user asked to hold. No `git pull` run.

**Problems / dead ends**
- First draft told the skill to find an `End commit:` line that entries never write; fixed to read the `Start → end commit` line.

**Verification**
- `diff` of the two skill copies shows only the intended frontmatter/note differences. No automated tests; these entries were written by following the skill's steps by hand.
