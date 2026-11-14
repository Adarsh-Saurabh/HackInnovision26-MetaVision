"""Optional live Gemini extraction for the Communication agent.

The model only interprets language. Its output is accepted only if every value is
grounded in the source text and agrees with the deterministic rule extraction;
otherwise the rule result is kept and the disagreement is logged. Any API error
falls back to rules. One call per run, with a timeout. API key comes from .env only.
"""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(override=False)

DEFAULT_MODEL = "gemini-3.5-flash-lite"
TIMEOUT_MS = 20000
MAX_CALLS = 2


class CommitmentChange(BaseModel):
    sponsor_name: str
    old_amount_inr: int | None
    new_amount_inr: int
    currency: str
    is_firm_request: bool
    deadline_phrase: str | None


def model_name() -> str:
    return os.environ.get("MODEL_NAME") or DEFAULT_MODEL


def live_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def live_default() -> bool:
    return os.environ.get("LLM_MODE", "fixture").strip().lower() == "live" and live_available()


def gemini_extract(body: str) -> CommitmentChange:
    """Single structured-output call. Raises on any failure."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                          http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    prompt = ("You read one message sent to an event organiser. Extract the sponsorship commitment change "
              "it requests. Amounts are whole rupees without separators. If no old amount is stated use null. "
              "deadline_phrase is the exact deadline wording from the message, or null.\n\nMessage:\n" + body)
    resp = client.models.generate_content(
        model=model_name(), contents=prompt,
        config={"response_mime_type": "application/json", "response_schema": CommitmentChange,
                "temperature": 0})
    parsed = resp.parsed
    if not isinstance(parsed, CommitmentChange):
        raise ValueError("model returned no parseable structured output")
    return parsed


def _numbers(body: str) -> set[int]:
    """Every whole number written in the text, with any digit grouping (100,000 or 1,00,000)."""
    return {int(tok.replace(",", "")) for tok in re.findall(r"\d+(?:,\d+)*", body)}


def _in_text(amount: int | None, body: str) -> bool:
    """Exact whole-number match only: 60 must not match inside '60,000' or '160,000'."""
    return amount is not None and amount in _numbers(body)


def cross_check(store, proposal: dict, extractor=None) -> dict:
    """Run Gemini on the trigger message and reconcile it with the rule-based proposal."""
    extractor = extractor or gemini_extract  # looked up at call time so tests can block it
    model = model_name()
    src = store.source(proposal["source_id"])
    if src is None or not proposal.get("authorized"):
        # Never send text from an unverified sender (or an invisible source) to an external model.
        store.log("Communication", "Live Gemini skipped: sender not verified or source not visible", "info")
        return {**proposal, "llm": {"model": model, "status": "skipped"}}
    store.log("Communication", f"Live mode: asking Gemini ({model}) to interpret {proposal['source_id']}", "llm")
    got, last_exc = None, None
    for attempt in range(1, MAX_CALLS + 1):  # bounded: at most MAX_CALLS calls per run
        try:
            got = extractor(src["body"])
            break
        except Exception as exc:  # network, quota, timeout, schema: never block the workflow
            last_exc = exc
            if attempt < MAX_CALLS:
                store.log("Communication", f"Gemini call failed ({type(exc).__name__}); one retry", "retry")
    if got is None:
        store.log("Communication", f"Gemini unavailable ({type(last_exc).__name__}); using rule-based "
                  "extraction", "error")
        return {**proposal, "llm": {"model": model, "status": "error", "error": type(last_exc).__name__}}

    body = src["body"]
    name = got.sponsor_name.strip()
    deadline = (got.deadline_phrase or "").strip()
    rule_old = proposal.get("old_paise")
    grounded = {
        "sponsor named in message": bool(name) and name.lower() in body.lower(),
        "new amount appears in message": _in_text(got.new_amount_inr, body),
        "old amount appears in message": got.old_amount_inr is None or _in_text(got.old_amount_inr, body),
        "deadline wording appears in message": not deadline or deadline.lower() in body.lower(),
        "currency is INR": got.currency.strip().upper() in ("INR", "RUPEES", "₹"),
    }
    agrees = {
        "sponsor matches rules": name.lower() == str(proposal.get("sponsor_name", "")).lower(),
        "new amount matches rules": got.new_amount_inr * 100 == proposal["new_paise"],
        "old amount matches rules": (got.old_amount_inr is None) == (rule_old is None)
        and (rule_old is None or got.old_amount_inr * 100 == rule_old),
        "firm request": got.is_firm_request,
    }
    failed = [k for k, ok in {**grounded, **agrees}.items() if not ok]
    llm = {"model": model, "status": "agree" if not failed else "disagree", "failed_checks": failed,
           "extracted": got.model_dump()}
    if failed:
        store.log("Communication", f"Gemini output rejected ({', '.join(failed)}); keeping grounded "
                  "rule-based extraction", "error", llm)
        return {**proposal, "llm": llm}
    old = f"INR {got.old_amount_inr:,}" if got.old_amount_inr is not None else "(old amount not stated)"
    store.log("Communication", f"Gemini read: {got.sponsor_name}, {old} → "
              f"INR {got.new_amount_inr:,}, deadline '{got.deadline_phrase}'. Grounded in the message text "
              "and matches rule-based extraction.", "llm", llm)
    return {**proposal, "llm": llm, "method": f"gemini:{model} + rules (agree)", "confidence": 0.99}
