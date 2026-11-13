---
name: update-work-done
description: Use when the user runs /update-work-done at the end of a work session to record what was done, how, and where to resume, in their own file under workDone/.
disable-model-invocation: true
argument-hint: "[optional note to include, e.g. 'stopped mid-replan, D3 test failing']"
---

<!-- Claude Code copy. Keep in sync with .agents/skills/update-work-done/SKILL.md (Codex copy); only the frontmatter and the note line in step 2 differ. -->

# Update workDone

`workDone/` (repository root) holds one hand-off file per teammate, so parallel updates never touch the same file and never conflict in Git:

| Teammate | File |
|---|---|
| Ujjwal | `workDone/ujjwal.md` |
| Adarsh | `workDone/adarsh.md` |
| Vaibhav | `workDone/vaibhav.md` |

A new session reads all three and must be able to continue without this conversation. The plan they track against is [temp/PROJECT_B_BLUEPRINT.md](../../../temp/PROJECT_B_BLUEPRINT.md) (cite sections as `§N`).

Each file has two parts:

1. **Resume here**: a snapshot, **overwritten** every run, describing the state *now*.
2. **Session log**: one entry per session of that person, **newest first**, never deleted.

## Steps

### 1. Identify whose file to edit

Run `git config user.name`. Match it case-insensitively against the table (for example `Adarsh-Saurabh` → `adarsh.md`). If it is unset or matches nobody, ask the user which of the three they are. Edit **only** that file; read the other two, never write them.

### 2. Gather evidence (do not write from memory alone)

Run in one go and use the output:

```powershell
Get-Date -Format "yyyy-MM-dd HH:mm zzz"
git branch --show-current; git rev-parse --short HEAD
git log --oneline -15
git status --short
git diff --stat; git diff --cached --stat
```

Then:

- Read all three `workDone/*.md` files. Note each teammate's latest `_Updated:` line, phase, and P0 statuses.
- Find this person's previous end commit (second SHA in the newest entry's `Start → end commit` line of their own file) and run `git log --oneline <that-sha>..HEAD` to list commits since then.
- Review this conversation: files created/edited, commands run, decisions made, problems hit, things tried that failed.
- If tests exist (`tests/` and `pyproject.toml`), run `uv run --locked pytest -q` when it takes under ~1 minute and record the real pass/fail counts. Otherwise write "not run" and why.
- Include `$ARGUMENTS` if the user passed a note.
- Do not `git pull`; the user handles syncing.

### 3. Create the file if missing

If the person's file does not exist, create it with exactly this skeleton (with their name), then continue:

```markdown
# workDone: <Name>

Read **Resume here** first. This is <Name>'s file; teammates' files are in the same folder. Session log is newest first.

## Resume here

## Session log
```

### 4. Write the session entry

Insert it directly under `## Session log`, above older entries:

```markdown
### Session N: YYYY-MM-DD HH:MM-HH:MM IST, <one-line theme>

- **Branch:** `<branch>`
- **Start → end commit:** `<sha>` → `<sha>` (uncommitted changes: yes/no)
- **Goal:** <what this session set out to do, with blueprint §refs>

**Done**
- <what was built or changed: file paths, function names, outcome>

**How**
- <approach, key design choices, libraries/APIs used, non-obvious tricks>

**Decisions and blueprint deviations**
- <decision + reason; mark any change from the blueprint as "DEVIATION from §N: ...">

**Problems / dead ends**
- <errors hit (quote exact message), what fixed them, approaches tried and abandoned>

**Verification**
- <tests run with real counts, manual checks, demo steps exercised; or "none">
```

`N` is the previous session number **in this person's file** + 1 (start at 1). Omit a section heading only if it would be empty, except **Verification**, which always appears.

### 5. Overwrite "Resume here"

Replace everything between `## Resume here` and `## Session log` with:

```markdown
_Updated: YYYY-MM-DD HH:MM IST by <Name> session N. Commit `<sha>` on `<branch>`; uncommitted changes: <none / list>._

**Working on:** <one line: this person's current area, e.g. "storage + tools, §12/§14">

**Next action:** <the single concrete thing this person does first next session, with file path and blueprint §ref>

**Team P0 progress (§3.1)**, as known at this update
| # | Item | Status | Owner | Where / notes |
|---|---|---|---|---|
| 1 | Seed workspace from fixtures | not started / in progress / done / verified | <name> | <path> |
| ... all 10 P0 items ... |

**Schedule (§19.2):** <current IST time vs planned slot; ahead/on track/behind; which §19.2 cut applies if behind>

**Run / test commands that work now:** <exact commands, or "none yet">

**Blockers, open decisions, and needs from teammates:** <list, including §26 open decisions still unresolved>

**Known broken / do not trust:** <failing tests, stubbed parts, fixture-only paths>
```

Build the P0 table from this session's evidence plus the teammates' snapshots read in step 2; for each row, keep whichever status has the newer evidence. Status words: `done` = code exists; `verified` = a test or demo run proved it. Never mark `verified` without evidence. After P0 is fully verified, add a P1 table (§3.2) the same way.

### 6. Finish

- Keep the snapshot under ~60 lines. If the file passes ~500 lines, shorten session entries older than the latest five to their **Done** and **Decisions** bullets; keep every DEVIATION line.
- Never write secrets, API keys, `.env` values, or tokens into the file.
- Do not commit or push unless the user asks.
- Reply with 2-3 lines: which file and session number, the headline recorded, the next action. Remind them to commit and push only their own `workDone/<name>.md` so teammates see it.

## Common mistakes

| Mistake | Fix |
|---|---|
| Editing a teammate's file | Only the file from step 1; others are read-only |
| Logging from memory, claiming tests pass | Use step 2 output; failing or unrun tests are written as such |
| Appending the snapshot instead of replacing it | Exactly one "Resume here" section, always current |
| Vague bullets ("worked on planning") | Name files, functions, test counts, error text |
| Losing why something changed | Every blueprint deviation gets a DEVIATION line with the reason |
| Next action is a list of ten things | One concrete first step; the rest goes in the P0 table or blockers |
