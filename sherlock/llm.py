"""Optional LLM rephrasing of Sherlock's deterministic finding.

The LLM never sees raw data and never computes anything. It receives the
structured case file and the deterministic finding, and may only rephrase.
Its output is rejected (and the deterministic text used instead) if it:
  * contains a number not present in the case file, or
  * uses causal language.

Enabled only when ANTHROPIC_API_KEY is set. Uses the standard library so no
SDK is required.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Optional, Tuple

from .narrative import CAUSAL_PHRASES, allowed_numbers, finding

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = os.environ.get("SHERLOCK_LLM_MODEL", "claude-sonnet-4-5")

SYSTEM = (
    "You are Sherlock Homes, a careful housing-data analyst. Rewrite the provided FINDING as clear, "
    "plain English for community members (max 170 words). Rules: use ONLY facts and numbers present in "
    "the FINDING or CASE JSON; do not add statistics, places, history or outside knowledge; never claim or "
    "imply causation (do not use words like caused, led to, drove, due to, because of, resulted in); "
    "keep the final sentence about what the evidence cannot establish. Output plain text only."
)


def validate(text: str, case: dict) -> Tuple[bool, str]:
    low = text.lower()
    for p in CAUSAL_PHRASES:
        if re.search(rf"\b{re.escape(p)}\b", low):
            return False, f"causal phrase '{p}'"
    allowed = allowed_numbers(case)
    for tok in re.findall(r"\d[\d,]*\.?\d*", text):
        t = tok.rstrip(".,")
        if t and t not in allowed and t.replace(",", "") not in {a.replace(",", "") for a in allowed}:
            return False, f"unsupported number '{t}'"
    return True, "ok"


def explain(case: dict, timeout: float = 25.0) -> dict:
    base = case.get("finding", {}).get("text") or finding(case)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"text": base, "generated_by": "deterministic template", "llm_status": "disabled (no ANTHROPIC_API_KEY)"}
    compact = {k: case[k] for k in ("name", "title", "level") if k in case}
    compact["signals"] = [{k: s.get(k) for k in ("label", "baseline_period", "recent_period", "baseline_value", "recent_value",
                                                   "change_pct", "city_change_pct", "expected_recent", "status")}
                          for s in case["evidence"]["signals"]]
    body = {
        "model": DEFAULT_MODEL, "max_tokens": 450, "system": SYSTEM,
        "messages": [{"role": "user", "content": f"CASE JSON:\n{json.dumps(compact, default=str)}\n\nFINDING:\n{base}"}],
    }
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST", headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    except Exception as e:  # network, auth, model name…
        return {"text": base, "generated_by": "deterministic template", "llm_status": f"error: {type(e).__name__}"}
    ok, why = validate(text, case)
    if not ok:
        return {"text": base, "generated_by": "deterministic template", "llm_status": f"rejected: {why}"}
    return {"text": text, "generated_by": f"LLM ({DEFAULT_MODEL}) rephrasing of deterministic finding; numbers verified",
            "llm_status": "ok", "deterministic_text": base}
