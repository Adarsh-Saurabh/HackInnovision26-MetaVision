# workDone: Ujjwal

Read **Resume here** first. This is Ujjwal's file; teammates' files are in the same folder. Session log is newest first.

## Resume here

_Updated: 2026-11-14 03:10 IST by Ujjwal session 1. Commit `e4ac995` on `main`; uncommitted changes: `temp/PROJECT_B_BLUEPRINT.md` (revision 2), `.claude/`, `.agents/`, `CLAUDE.md`, `AGENTS.md`, `workDone/`, untracked `Screenshot 2026-11-14 013203.png`._

**Working on:** session hand-off tooling (done). No implementation area assigned yet.

**Next action:** Commit blueprint rev 2 and the hand-off files, then write S1 fixtures in `data/fixtures/` and hand-written `expected_outcomes.json` (blueprint §4, §17, §26 "Next task"), unless a teammate already owns that.

**Team P0 progress (§3.1)**, as known at this update
| # | Item | Status | Owner | Where / notes |
|---|---|---|---|---|
| 1 | Seed workspace from fixtures (simulated clock) | not started | | |
| 2 | Communication: entity extraction with spans | not started | | |
| 3 | Knowledge: resolve sponsor, context bundle, traversal incl. DEC-07 | not started | | |
| 4 | Planning: mid-stream classification, versioned plan | not started | | |
| 5 | Approval gate (LangGraph interrupt), three scopes | not started | | |
| 6 | Execution with operation keys + fail-once tracker retry | not started | | |
| 7 | Adaptive replan on concurrent D3 edit, delta re-approval | not started | | |
| 8 | Verification read-back, summary, ledger, agent timeline | not started | | |
| 9 | Replay source message: zero duplicate effects | not started | | |
| 10 | Paused approval survives process restart | not started | | |

**Schedule (§19.2):** 03:10 IST is inside the 02:30-04:00 slot (deterministic S1 test should be in progress), but the 01:45-02:30 fixtures/schema/tools work has not started. Behind by ~1 slot. If still behind at 04:30, apply the §19.2 cuts (alias-only inferred edges, no live LLM until UI works).

**Run / test commands that work now:** none yet (no `pyproject.toml`, `uv.lock`, tests, or `app.py`).

**Blockers, open decisions, and needs from teammates:** split P0 work across Ujjwal / Adarsh / Vaibhav (§20, team size now 3); Gemini key and model on the team account; submission portal and real cutoff (09:30 vs noon, §1); whether any live connector credential exists (§26). `git config user.name` is unset on this PC, so the skill will ask who is running it.

**Known broken / do not trust:** nothing implemented; all performance numbers in the blueprint are targets.

## Session log

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
