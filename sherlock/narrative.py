"""Deterministic plain-English text generated only from structured evidence.

These templates are the default "Sherlock's Finding". An optional LLM
(see llm.py) may rephrase them, but its output is rejected unless every
number it uses already appears in the case file and it avoids causal
language.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from . import config
from .indicators import INDICATORS

CAUSAL_PHRASES = ["caused", "causing", "because of", "led to", "leads to", "resulted in", "results in",
                  "drove", "driven by", "due to", "triggered", "responsible for", "as a result"]


def fmt_pct(x: Optional[float], digits: int = 0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x * 100:+.{digits}f}%"


def fmt_num(x: Optional[float]) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:,.0f}"


def fmt_usd(x: Optional[float]) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:,.0f}K"
    return f"${x:,.0f}"


def fmt_value(indicator: str, x: Optional[float]) -> str:
    return fmt_usd(x) if INDICATORS[indicator]["unit"].startswith("USD") else fmt_num(x)


TITLES = {
    ("res_new_construction_permits", "up"): "The Case of the Construction Surge",
    ("res_new_construction_permits", "down"): "The Case of the Stalled Construction",
    ("demolition_permits", "up"): "The Case of the Rising Demolitions",
    ("demolition_permits", "down"): "The Case of the Fading Demolitions",
    ("res_alteration_permits", "up"): "The Case of the Renovation Wave",
    ("res_alteration_permits", "down"): "The Case of the Quiet Renovations",
    ("res_permit_value", "up"): "The Case of the Big-Ticket Permits",
    ("res_permit_value", "down"): "The Case of the Shrinking Investment",
}


def case_title(top_signal: dict) -> str:
    d = "up" if top_signal["z_score"] > 0 else "down"
    return TITLES.get((top_signal["indicator"], d), "The Case of the Unusual Pattern")


def signal_sentence(s: dict) -> str:
    ind = s["indicator"]
    v0, v1 = fmt_value(ind, s["baseline_value"]), fmt_value(ind, s["recent_value"])
    ch = f" ({fmt_pct(s['change_pct'])})" if s.get("change_pct") is not None else ""
    city = fmt_pct(s.get("city_change_pct"))
    exp = s.get("expected_recent")
    exp_txt = f" Had it followed the citywide trend, about {fmt_value(ind, exp)} would be expected." if exp is not None else ""
    return (f"{s['label']}: {v1} in {s['recent_period']} vs. {v0} in {s['baseline_period']}{ch}; "
            f"citywide the change was {city}.{exp_txt}")


def signal_headline(s: dict) -> str:
    """Short 'why Sherlock noticed' line."""
    ind = s["indicator"]
    rel = "faster" if s["z_score"] > 0 else "slower"
    if s.get("change_pct") is not None:
        return f"{s['short']} {fmt_pct(s['change_pct'])} vs. city {fmt_pct(s['city_change_pct'])}"
    return f"{s['short']}: {fmt_value(ind, s['recent_value'])} recent vs. {fmt_value(ind, s['baseline_value'])} baseline ({rel} than city trend)"


def finding(case: dict) -> str:
    name = case["name"]
    sigs = [s for s in case["evidence"]["signals"] if s["status"] == "scored"]
    strong = sorted([s for s in sigs if abs(s["z_score"]) >= 1.0], key=lambda s: -abs(s["z_score"]))
    B, R = sigs[0]["baseline_period"] if sigs else "", sigs[0]["recent_period"] if sigs else ""
    paras: List[str] = []
    if strong:
        paras.append(f"Between {B} and {R}, {len(strong)} of {len(sigs)} scored permit indicators in {name} "
                     f"moved noticeably differently from the citywide pattern.")
        paras.append(" ".join(signal_sentence(s) for s in strong[:3]))
    else:
        paras.append(f"Between {B} and {R}, permit activity in {name} broadly followed the citywide pattern; "
                     f"no scored indicator stood out strongly.")
    wcf = case.get("what_changed_first", {}).get("ordered", [])
    if len(wcf) >= 2:
        seq = ", then ".join(f"{o['short'].lower()} ({o['year']}, {'higher' if o['direction'] == 'up' else 'lower'})" for o in wcf)
        paras.append(f"Timing: the first departures from 2020–21 patterns appeared in this order: {seq}. "
                     f"This ordering is evidence about timing only; it does not show that one change produced another.")
    elif len(wcf) == 1:
        o = wcf[0]
        paras.append(f"Timing: {o['short'].lower()} first departed from its 2020–21 share of city activity in {o['year']}.")
    vac = case["evidence"].get("context", {}).get("city_owned_vacant_lots")
    if vac and vac.get("value") is not None:
        paras.append(f"Context: the City owns {fmt_num(vac['value'])} vacant lots here "
                     f"({vac['per_km2']:.1f} per km² vs. {vac['city_per_km2']:.1f} citywide), from a {vac['snapshot']} snapshot.")
    if strong:
        paras.append("Taken together, the permit record indicates that building activity in this neighborhood changed "
                     "differently from the rest of the city during this period.")
    paras.append("The available evidence does not establish why these changes happened, whether permitted work was completed, "
                 "or how rents, prices or residents were affected: no neighborhood-level rent, sales, income or vacancy-rate data is loaded.")
    return "\n\n".join(paras)


def limitations(case: dict) -> List[str]:
    out = [
        "No dataset in this analysis establishes causal relationships.",
        "A permit being issued does not mean construction started or was completed; permits do not record how many homes are created.",
        "No neighborhood-level rent, home price, income, household or vacancy-rate data is loaded, so Sherlock cannot say how residents or housing costs were affected.",
        "City-owned vacant lots come from a single snapshot and exclude privately owned vacant land.",
        "The City changed permit systems in 2024. Work types were mapped to common categories, but counting practices may differ before and after.",
        "Neighborhood boundaries are built from 2010 Census blocks; the permit file's own neighborhood labels are used to assign permits.",
        "Metro context comes from Zillow's 7-county Pittsburgh metro area and does not describe this neighborhood.",
        f"2019 (from June) and 2026 (through {case.get('permit_last_date', 'September')}) are partial years and are excluded from change calculations.",
    ]
    for s in case["evidence"]["signals"]:
        if s["status"] == "insufficient_data":
            out.append(f"{s['label']}: UNKNOWN — too few permits to score.")
    return out


def allowed_numbers(case: dict) -> set:
    """All numeric tokens that an LLM rephrasing is permitted to use."""
    import re
    text = (case.get("finding", {}).get("text") or finding(case)) + " " + " ".join(case.get("limitations") or limitations(case))
    for s in case["evidence"]["signals"]:
        for k in ("baseline_value", "recent_value", "expected_recent"):
            if s.get(k) is not None:
                text += " " + fmt_value(s["indicator"], s[k])
        for k in ("change_pct", "city_change_pct"):
            if s.get(k) is not None:
                text += " " + fmt_pct(s[k]) + " " + fmt_pct(s[k], 1)
        if s.get("z_score") is not None:
            text += f" {s['z_score']:.1f} {abs(s['z_score']):.1f}"
    text += f" {case.get('score', 0):.1f}"
    return set(re.findall(r"\d[\d,]*\.?\d*", text))


# ---------------------------------------------------------------------------
# Plain-language summary for the "Quick brief" view (non-specialists)
# ---------------------------------------------------------------------------
PLAIN_NOUN = {
    "res_new_construction_permits": "permits to build new homes",
    "demolition_permits": "demolition permits",
    "res_alteration_permits": "home renovation permits",
    "res_permit_value": "planned spending on home building and renovation (as declared on permits)",
}
PLAIN_HEADLINE = {
    ("res_new_construction_permits", "up"): "far more new-home building activity than the city trend would suggest",
    ("res_new_construction_permits", "down"): "much less new-home building activity than the city trend would suggest",
    ("demolition_permits", "up"): "more demolitions than the city trend would suggest",
    ("demolition_permits", "down"): "fewer demolitions than the city trend would suggest",
    ("res_alteration_permits", "up"): "more home renovations than the city trend would suggest",
    ("res_alteration_permits", "down"): "fewer home renovations than the city trend would suggest",
    ("res_permit_value", "up"): "much more money planned for home projects than the city trend would suggest",
    ("res_permit_value", "down"): "much less money planned for home projects than the city trend would suggest",
}
PLAIN_LEVEL = {"HIGH": "Very unusual", "MEDIUM": "Somewhat unusual", "LOW": "About typical", "INSUFFICIENT DATA": "Not enough data"}


def _plain_change(x: Optional[float]) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "changed"
    if abs(x) < 0.005:
        return "stayed about the same"
    return f"went {'up' if x > 0 else 'down'} {abs(x) * 100:.0f}%"


def plain_bullet(s: dict, name: str) -> str:
    ind = s["indicator"]
    noun = PLAIN_NOUN.get(ind, s["label"].lower())
    b, r = fmt_value(ind, s["baseline_value"]), fmt_value(ind, s["recent_value"])
    city = _plain_change(s.get("city_change_pct"))
    if ind == "res_permit_value":
        first = f"In {name}, {noun} went from {b} ({s['baseline_period']}) to {r} ({s['recent_period']})."
    else:
        first = f"{name} had {r} {noun} in {s['recent_period']}, compared with {b} in {s['baseline_period']}."
    what = "planned spending citywide" if ind == "res_permit_value" else f"{noun} citywide"
    return f"{first} Over the same period, {what} {city}."


def plain_summary(case: dict) -> dict:
    name = case["name"]
    sigs = [s for s in case["evidence"]["signals"] if s["status"] == "scored"]
    strong = sorted([s for s in sigs if abs(s["z_score"]) >= 1.0], key=lambda s: -abs(s["z_score"]))
    level = case["level"]
    if strong:
        top = strong[0]
        headline = f"{name} saw {PLAIN_HEADLINE[(top['indicator'], 'up' if top['z_score'] > 0 else 'down')]}."
    elif level == "INSUFFICIENT DATA":
        headline = f"There isn't enough permit activity in {name} to spot a clear pattern."
    else:
        headline = f"Building activity in {name} has broadly kept pace with the rest of Pittsburgh."
    bullets = [plain_bullet(s, name) for s in strong[:3]]

    timing = None
    if strong:
        top = strong[0]
        want = "up" if top["z_score"] > 0 else "down"
        onset = next((o for o in case.get("what_changed_first", {}).get("ordered", [])
                      if o["indicator"] == top["indicator"] and o["direction"] == want), None)
        if onset:
            timing = (f"This pattern first showed up in {onset['year']}, when {PLAIN_NOUN[top['indicator']]} "
                      f"{'rose above' if want == 'up' else 'fell below'} what this neighborhood's earlier share of city activity would suggest. "
                      f"Timing alone doesn't tell us why things changed.")

    conf = case["confidence"]["level"]
    factors = {f["factor"] for f in case["confidence"]["factors"]}
    conf_text = {
        "HIGH": "High — several independent sources agree.",
        "MODERATE": "Medium — this is based on one source (City building permits), so treat it as a lead rather than a conclusion.",
        "LOW": "Low — there are few permits here or the signals are mixed, so one project can swing the numbers.",
    }[conf]
    if "Concentrated activity" in factors:
        conf_text += " Many of these permits were issued on the same day, which usually means one large multi-lot project."

    keep_in_mind = [
        "Permits show plans to build, renovate or demolish — not finished homes.",
        "We don't yet have neighborhood data on rents, home prices, incomes or who lives here.",
        "Unusual doesn't mean good or bad — it means different from the rest of the city.",
    ]
    similar = [s["name"] for s in case.get("similar_cases", [])[:3]]
    return {
        "level_label": PLAIN_LEVEL[level],
        "headline": headline,
        "bullets": bullets,
        "timing": timing,
        "confidence": conf_text,
        "keep_in_mind": keep_in_mind,
        "similar": similar,
        "similar_text": (f"Other neighborhoods with a similar pattern: {', '.join(similar)}." if similar else None),
    }
