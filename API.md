# Gemini API setup

How to use the team's Gemini API key for MetaVision / Second Brain. The key itself is **not** in this repository. Get it from Ujjwal over a private channel (WhatsApp/Signal), never through Git, issues, or screenshots.

## 1. Put the key in `.env`

From the repository root:

```powershell
Copy-Item .env.example .env
```

Open `.env` and paste the key after `GEMINI_API_KEY=`. `.env` is listed in `.gitignore`; check with `git status` that it never shows up as a change. If a key is ever committed or pushed, tell the team: the key must be rotated, because deleting the file does not remove it from Git history.

```dotenv
CONNECTOR_MODE=simulated
LLM_MODE=fixture            # fixture = no API calls; live = call Gemini
MODEL_NAME=gemini-3.5-flash-lite
GEMINI_API_KEY=<paste key here>
DEMO_NOW=2026-11-14T06:30:00+05:30
LANGGRAPH_STRICT_MSGPACK=true
```

Tests always run with `LLM_MODE=fixture` (blueprint §18). Use `live` only for the live-extraction step.

## 2. Models

Checked on 2026-11-14 with this key (`GET /v1beta/models`, models supporting `generateContent`):

| Model | Use | Structured-output test |
|---|---|---|
| `gemini-3.5-flash-lite` | **Default.** Fastest and cheapest; extraction and drafts | Pass (71 tokens) |
| `gemini-3.6-flash` | Fallback if lite misreads messages | Pass (439 tokens, includes thinking) |
| `gemini-3.8-flash` | Listed, not tested | — |

Do not use `gemini-2.5-flash`: it is deprecated and routes to `gemini-3.5-flash-lite` from December 1, 2026 (blueprint §6). Keep the model in `MODEL_NAME`, never hard-coded.

## 3. Quick test (PowerShell)

Loads the key from `.env` into this terminal only, then lists models:

```powershell
Get-Content .env | Where-Object { $_ -match '^GEMINI_API_KEY=' } | ForEach-Object { $env:GEMINI_API_KEY = $_.Split('=',2)[1] }
curl.exe -s -H "x-goog-api-key: $env:GEMINI_API_KEY" "https://generativelanguage.googleapis.com/v1beta/models?pageSize=5"
```

A JSON list of models means the key works. An `error` object with `API_KEY_INVALID` or `PERMISSION_DENIED` means the key is wrong or revoked.

## 4. Python (structured output)

Install once the project environment exists: `uv add google-genai` (already in blueprint §21). Pass a Pydantic model as the schema; do not repeat the schema in the prompt.

```python
import os
from google import genai
from pydantic import BaseModel


class CommitmentChange(BaseModel):
    sponsor: str
    old_inr: int | None
    new_inr: int


client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
response = client.models.generate_content(
    model=os.environ.get("MODEL_NAME", "gemini-3.5-flash-lite"),
    contents="Extract: We need to revise Aster Labs' commitment from INR 100,000 to INR 60,000.",
    config={
        "response_mime_type": "application/json",
        "response_schema": CommitmentChange,
    },
)
change: CommitmentChange = response.parsed
print(change)
```

Tested result (REST equivalent): `{"sponsor": "Aster Labs", "old_inr": 100000, "new_inr": 60000}`.

## 5. Rules for this project

- The model only interprets language and writes drafts. Arithmetic, authority, conflicts, approvals, and verification are deterministic code (blueprint §6).
- Schema-valid output is not enough: check every extracted value against its source span before use (§8).
- Never send denied confidential sources or raw sensitive values to the model (§13.3).
- Every call has a timeout and a per-run call cap; on failure use the fallback path in §14.5, never loop.
- Cache extraction by source content hash only (§24). Log tokens per run.
- Never print or log the key. Never paste it into prompts, issues, commits, or screenshots.
