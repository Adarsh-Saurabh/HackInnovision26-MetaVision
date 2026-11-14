# Shared setup: MetaVision / Second Brain

Use this guide on every teammate's computer. Standardize the project environment, Git workflow, and AI assistance without copying anyone's credentials or machine-specific settings.

**Current state:** the prototype is implemented (`app.py`, `second_brain/`, `tests/`, committed `pyproject.toml` and `uv.lock`). See [README.md](README.md) for run commands. Sections below marked **after implementation starts** now apply.

## 1. Team defaults

| Area | Shared decision |
|---|---|
| Project | HackInnovision 2026, Track B / Second Brain |
| Repository | `https://github.com/Adarsh-Saurabh/HackInnovision26-MetaVision.git` |
| Development baseline | Python 3.12, managed by uv |
| Python environment | Repository-local `.venv`, never a global package environment |
| Dependencies | One committed `pyproject.toml` and `uv.lock`, once implemented |
| Architecture | Python, LangGraph, Pydantic, SQLite, Streamlit |
| Initial connectors | Simulated; real services only when explicitly configured |
| Runtime files | Ignored `runtime/`; synthetic fixtures committed separately |
| Time | Explicit timezone; event-facing times use `Asia/Kolkata` / IST |
| Money | Integer paise plus explicit currency; no floating-point financial totals |
| Code style | UTF-8, LF, four spaces for Python; honor `.editorconfig` |
| AI implementation style | Ponytail full: smallest complete change, appropriate checks |
| AI response style | Caveman for brief task updates; detailed explanations when requested |
| Git | Small commits; `codex/<task>` branches; no force-pushing shared branches |

Different usernames, folder paths, editors, and operating systems are fine. Dependency versions and shared behavior matter more than identical desktops.

Read [README.md](README.md), then the [Project B blueprint](temp/PROJECT_B_BLUEPRINT.md). The blueprint defines the proposed agent contracts, dataset, approval rules, and demo.

## 2. Install the small set of prerequisites

Install these through their official distribution instructions:

- Git and a working GitHub sign-in for your own account.
- uv: [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).
- Codex desktop, CLI, or IDE extension, using your own account. Use the same client release across teammates where practical.
- An editor that honors `.editorconfig`. VS Code is optional, not a runtime requirement.

Node.js is needed only if you choose a skill/plugin installer or lifecycle hooks that require it. The Python application itself does not need Node. No Docker, GPU, or database server is required for the proposed MVP.

Open a new terminal after installing tools. The examples below use PowerShell; Git and uv command arguments are also suitable for macOS/Linux shells, while environment-variable syntax differs.

```powershell
git --version
uv --version
uv python install 3.12
uv python find 3.12
```

Record the Python, uv, and Codex versions in the team's working notes. Once the first working environment is committed, keep the same Python patch version where practical and resolve any platform-specific differences through the shared lockfile. Do not upgrade tools or dependencies independently during the final demo sprint.

On Windows, `python` may resolve to a Microsoft Store alias. Use `uv run python` inside the implemented project instead of assuming the bare `python` command is the intended interpreter.

## 3. Clone and configure Git

### New teammate / new computer

Run from the parent folder where you keep projects:

```powershell
git clone https://github.com/Adarsh-Saurabh/HackInnovision26-MetaVision.git
Set-Location HackInnovision26-MetaVision
git remote -v
git status --short
```

### Existing checkout

Open the existing repository folder. Do not clone into it or run `git init` again.

```powershell
git status --short
git remote -v
```

If there are local changes, commit or deliberately preserve them before updating. With a clean working tree:

```powershell
git switch main
git pull --ff-only
```

Set your own identity for this repository, replacing the example values:

```powershell
git config --local user.name "Your Name"
git config --local user.email "your-own-github-email@example.com"
```

Use your own GitHub credentials and request repository access from the owner if needed. Do not copy another person's Git credential files, tokens, SSH private keys, or Codex account files. Public cloning does not grant permission to push.

## 4. Reproduce the application environment - after implementation starts

One teammate initializes dependencies once, tests them, and commits `pyproject.toml`, `uv.lock`, and `.python-version`. Everyone else consumes those files. Do not run `uv init` or independently reconstruct the dependency list on each PC.

When those files exist:

```powershell
uv sync --locked
uv run --locked python --version
```

`--locked` fails if the manifest and lockfile disagree instead of silently accepting a new dependency resolution. See [uv project guidance](https://docs.astral.sh/uv/guides/projects/). If it fails, fix and commit the shared manifest/lockfile together; do not delete the lockfile as a workaround.

After the application and tests exist:

```powershell
uv run --locked pytest
uv run --locked streamlit run app.py
```

No environment activation is needed when using `uv run`. In an editor, select the repository's `.venv` interpreter: `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on macOS/Linux.

For a new dependency, one developer runs `uv add <package>` on a task branch, verifies the affected code, and commits both manifest and lockfile. Avoid mixing global pip installs, manually edited lockfiles, and separate per-person requirements files.

## 5. Local configuration and secrets - after implementation starts

The first implementation should provide a committed `.env.example` containing key names and safe placeholders. Each teammate creates their own ignored `.env` if the application supports loading it. A `.env` file is not loaded automatically by Python.

Example proposed settings, not implemented behavior yet:

```dotenv
CONNECTOR_MODE=simulated
LLM_MODE=fixture
MODEL_NAME=
GEMINI_API_KEY=
```

Only live-model mode needs a real API key and supported model name. Each teammate uses their own key, or an explicitly authorized team key delivered outside Git. Never put real values into `.env.example`, screenshots, prompts, logs, or commits.

For a temporary PowerShell session, environment variables can be set directly:

```powershell
$env:CONNECTOR_MODE = "simulated"
$env:LLM_MODE = "fixture"
```

Use the same synthetic fixtures on every PC. Do not share runtime databases as the source of truth; seed a fresh ignored workspace from committed fixtures. Fixture mode must be visibly labeled and must not imply that live inference or real email delivery occurred.

## 6. AI skills: Ponytail and Caveman

These skills guide the **coding assistant**. They are separate from the six agents we will implement inside Second Brain. Installing skills does not build the application or authorize its runtime agents to send messages.

### Shared behavior

| Skill | Use it for | Keep intact |
|---|---|---|
| Ponytail, full | Implementation, fixes, refactoring, dependency choices | Complete scope, boundary validation, error handling, security, accessibility, meaningful checks |
| Caveman | Brief progress updates, concise debugging explanations | Exact commands, paths, numbers, errors, and technical meaning |

Ponytail controls implementation scope; Caveman controls response length. Neither is a reason to skip a required feature, omit a material risk, or shorten documentation the user asked to be detailed.

Upstream sources: [Ponytail installation](https://github.com/DietrichGebert/ponytail/blob/main/INSTALL.md) and [Caveman skill](https://github.com/JuliusBrussee/caveman/blob/main/skills/caveman/SKILL.md). Third-party skills are not built-in OpenAI commands.

### Install the same skill revisions on each computer

The following full upstream commit IDs were resolved on November 14, 2026. They are the team's initial reproducibility baseline, not a claim that this PC's existing plugin matches them.

| Skill | Repository | Skill directory | Pinned commit |
|---|---|---|---|
| Ponytail | `DietrichGebert/ponytail` | `skills/ponytail` | `96608e078b2d5ea607c5c3b8b5a54d1c1fba6846` |
| Caveman | `JuliusBrussee/caveman` | `skills/caveman` | `b4ee71d557d96e3cbc14f88fa6e953a1362865f5` |

In **Codex chat**, ask the built-in installer:

```text
Use $skill-installer to install these instruction-only skills from their exact commits:
1. Repository DietrichGebert/ponytail, path skills/ponytail,
   ref 96608e078b2d5ea607c5c3b8b5a54d1c1fba6846.
2. Repository JuliusBrussee/caveman, path skills/caveman,
   ref b4ee71d557d96e3cbc14f88fa6e953a1362865f5.
Read the source instructions before using them. Do not install lifecycle hooks,
change global agent instructions, or overwrite existing skills/plugins.
If a skill already exists, report its source and let me resolve the duplicate.
```

This is a prompt, not a terminal command. The install requires network access and may require local permission. Installation is per person; pulling this repository does not install third-party skills. Start a new chat or restart Codex if the installed skills do not appear.

On the originating PC, Ponytail was already available through plugin version 5.3.3; Caveman was not found during this setup review. Do not assume another PC has either. If a plugin and a separately installed skill have the same name, choose one source deliberately rather than enabling duplicate definitions. Existing plugin hooks may also affect behavior; instruction-only installation does not remove them.

For exact cross-PC matching, confirm the same source revisions are selected on every client. Update the table in a reviewed commit when the team changes versions; do not independently follow upstream `main` during the event.

### Invoke the skills correctly

In Codex CLI/IDE, use `$ponytail` and `$caveman`, or choose them through the skill selector. Slash-command support depends on the host/plugin; `/ponytail` and `/caveman` are not universal Codex commands. The [official Codex skills documentation](https://developers.openai.com/codex/skills/) explains explicit invocation and discovery.

Examples to type into the **AI chat**, not PowerShell:

```text
Use $ponytail at full level and $caveman for concise replies.
Read setup.md, README.md, and the relevant blueprint sections first.
Implement the sponsor-change vertical slice with approval, duplicate protection,
and read-back verification. Keep the change small and run the relevant checks.
```

If your installed host/plugin exposes slash commands, the equivalent requests are:

```text
/ponytail full
/caveman
```

Without a picker, say “Use the installed Ponytail skill at full level” and “Use the installed Caveman skill.” Ask the assistant to name the actual loaded skill paths; if it cannot find a skill, it must say so rather than claim it is active. For detailed design work, explicitly request detailed output. Say “stop caveman” when you only want to disable terse replies; “normal mode” may affect both skills.

### Skill locations and portability

Codex supports repository skills in `.agents/skills/<name>/SKILL.md` and personal skills in `~/.agents/skills/<name>/SKILL.md`. Some installers/older clients also use `~/.codex/skills`; confirm what the installed client actually discovers. Plugin-managed skills have their own paths. Do not copy a version-specific plugin cache path from one PC into another's settings.

This commit intentionally does not vendor third-party skills or add hooks. `setup.md` is a human setup guide, not an automatically loaded agent policy. Ask the assistant to read it at the start of a task. If the team later needs automatic repository-wide rules, add a short reviewed `AGENTS.md`; if vendoring skills, include their source revision and license.

## 7. Standard task workflow

1. Start from a clean, updated checkout and create `codex/<short-task-name>`.
2. Give the assistant a concrete outcome and acceptance check. Include Ponytail and Caveman when available.
3. Read the affected code and callers before editing. Reuse existing helpers and dependencies.
4. Implement the smallest complete change, including affected tests/configuration.
5. Run the relevant checks; report failures and skipped checks honestly.
6. Review the diff for accidental files, secrets, unrelated edits, and behavior changes.
7. Commit and push the task branch; merge through the team's agreed review process.

Example terminal workflow from a clean, current checkout; change the task name each time:

```powershell
git switch -c codex/sponsor-change-flow
# Make the change and run checks, then:
git diff --check
git diff
git status --short
# Stage explicit intended paths, commit, then:
git push -u origin codex/sponsor-change-flow
```

Do not blindly use `git add .`, reset someone else's work, or force-push a shared branch. Coordinate before two teammates edit the same workflow/schema files.

## 8. Verify every PC before integrating work

### Available now

- Repository origin is correct and the intended commit is checked out.
- `README.md`, this guide, the blueprint, and original PDF are present.
- Git and uv run in a fresh terminal; a real Python 3.12 interpreter is discoverable.
- The assistant can find the installed Ponytail/Caveman skills and identify their source.
- No credentials or machine-specific absolute paths have been committed.

### Once the application exists

- `uv sync --locked` succeeds without rewriting the lockfile.
- `uv run --locked pytest` passes.
- The app starts using the agreed command and simulated connectors.
- The same fixture gives the same financial totals and affected records on both PCs.
- No consequential write happens before approval.
- A fail-once tool recovers and duplicate replay produces no duplicate effects.
- A paused approval survives the restart behavior supported by the chosen storage.

## 9. Troubleshooting

| Symptom | First action |
|---|---|
| `git` or `uv` not found | Reopen the terminal; verify the installation and PATH |
| Windows `python` opens the Store | Use uv's interpreter; select `.venv` in the editor |
| `uv sync` says no project exists | Expected at the planning stage; wait for the committed manifest and lockfile |
| Locked sync fails | Compare Python/uv versions and inspect manifest/lockfile changes; do not regenerate independently |
| Skill missing | Verify install location and selected client; restart or open a new chat |
| Slash command missing | Use the skill picker, `$skill` syntax where supported, or explicit natural-language invocation |
| Duplicate skill names | Check plugin and personal sources; select one deliberately |
| Push denied | Authenticate as yourself and confirm repository write access |
| Different results across PCs | Compare Git SHA, lockfile, fixture version, mode, and runtime state before changing code |
| Live API fails | Check your own configuration/quota; use clearly labeled fixture mode for deterministic testing |

**Not done by this document:** installing software, installing/enabling skills, modifying global PC settings, or testing the future application. Each teammate completes their own setup; exact model outputs can vary even with matching prompts and dependencies.
