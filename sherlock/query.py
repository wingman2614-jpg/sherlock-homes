"""Natural-language questions → structured queries over Sherlock's analytics.

The answer is always computed from case files. Language understanding is
rule-based by default; if ANTHROPIC_API_KEY is set, an LLM may translate the
question into the same JSON query schema, which is validated before use.
The LLM never answers the question itself.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Dict, List, Optional

# indicator id -> trigger patterns
INDICATOR_TERMS = {
    "res_new_construction_permits": [r"new construction", r"construction", r"new (homes|housing|units|buildings?)",
                                     r"housing supply", r"supply", r"development", r"build(ing)?\b", r"new build",
                                     r"\bpermits?\b", r"permit activity"],
    "demolition_permits": [r"demoli\w*", r"tear(ing)? down", r"teardowns?", r"razed?"],
    "res_alteration_permits": [r"renovat\w*", r"alteration\w*", r"remodel\w*", r"rehab\w*", r"repairs?", r"additions?"],
    "res_permit_value": [r"investment", r"permit value", r"value of permits", r"spending", r"dollars?", r"money", r"project value"],
    "city_owned_vacant_lots_per_km2": [r"vacant (land|lots?|parcels?)", r"city[- ]owned", r"land bank", r"empty lots?"],
    # ZIP-level market indicators (Mk2)
    "zip_rent": [r"\brents?\b", r"\brental", r"asking rent"],
    "zip_home_value": [r"home values?", r"house values?", r"property values?", r"zhvi", r"\bvalues?\b"],
    "zip_median_price": [r"sale prices?", r"\bprices?\b", r"selling for", r"cost of homes?"],
    "zip_sales_count": [r"\bsales\b", r"homes? sold", r"transactions?", r"turnover"],
}
ZIP_INDICATORS = {"zip_rent", "zip_home_value", "zip_median_price", "zip_sales_count"}
UP = r"(increas\w*|ris\w*|rose|grow\w*|grew|more|surg\w*|up\b|higher|jump\w*|boom\w*|accelerat\w*|most|faster|high)"
DOWN = r"(decreas\w*|declin\w*|fall\w*|fell|drop\w*|fewer|less|down\b|lower|slow\w*|shrink\w*|least|low)"
UNSUPPORTED = {
    "assessed values": r"assess\w*",
    "income": r"\bincomes?\b|\bwages?\b|\bearn\w*",
    "population / households": r"\bpopulation\b|\bhouseholds?\b|\bresidents?\b",
    "vacancy (rate or change over time)": r"\bvacanc\w*",
    "evictions": r"evict\w*",
    "affordability / cost burden": r"afford\w*|cost burden",
}
SIMILAR = r"(similar|resembl\w*|like|comparable|same as|look like)"


def _find_area(q: str, cases: List[dict]) -> Optional[dict]:
    ql = q.lower()
    m = re.search(r"\b(15\d{3})\b", ql)
    if m:
        for c in cases:
            if c.get("zip") == m.group(1):
                return c
    best = None
    for c in cases:
        n = c["name"].lower()
        if c.get("geography") == "zip":
            continue
        if n in ql and (best is None or len(n) > len(best["name"])):
            best = c
    return best


def parse(question: str, cases: List[dict]) -> dict:
    q = question.lower().strip()
    query = {"conditions": [], "similar_to": None, "rank": None, "unsupported": [], "parser": "rule-based"}
    for concept, pat in UNSUPPORTED.items():
        if re.search(pat, q):
            query["unsupported"].append(concept)
    area = _find_area(q, cases)
    if area and re.search(SIMILAR, q):
        query["similar_to"] = area["area_id"]
        return query
    clauses = re.split(r"\band\b|\bbut\b|\bwhile\b|\bwhere\b|,|;", q)
    for clause in clauses:
        for ind, pats in INDICATOR_TERMS.items():
            if any(re.search(p, clause) for p in pats):
                if any(c["indicator"] == ind for c in query["conditions"]):
                    continue
                d = "up" if re.search(UP, clause) else ("down" if re.search(DOWN, clause) else None)
                query["conditions"].append({"indicator": ind, "direction": d or "up", "direction_stated": d is not None})
                break
    if re.search(r"\b(most|largest|biggest|fastest|highest|least|lowest|top)\b", q) and query["conditions"]:
        query["rank"] = query["conditions"][0]["indicator"]
    return query


def _llm_parse(question: str, cases: List[dict]) -> Optional[dict]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    schema = {
        "conditions": [{"indicator": "|".join(INDICATOR_TERMS), "direction": "up|down"}],
        "similar_to": "neighborhood name or null", "rank": "indicator id or null",
        "unsupported": ["concepts asked about that are not among the indicators"],
    }
    prompt = (f"Translate the question into JSON matching this schema, using only these indicator ids: "
              f"{list(INDICATOR_TERMS)}. Neighborhood names: {[c['name'] for c in cases]}. "
              f"Schema: {json.dumps(schema)}. Output JSON only.\nQuestion: {question}")
    body = {"model": os.environ.get("SHERLOCK_LLM_MODEL", "claude-sonnet-4-5"), "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(), method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            text = "".join(b.get("text", "") for b in json.loads(r.read()).get("content", []))
        raw = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    except Exception:
        return None
    # validate strictly
    out = {"conditions": [], "similar_to": None, "rank": None, "unsupported": [], "parser": "LLM (validated)"}
    for c in raw.get("conditions", []) or []:
        if c.get("indicator") in INDICATOR_TERMS and c.get("direction") in ("up", "down"):
            out["conditions"].append({"indicator": c["indicator"], "direction": c["direction"], "direction_stated": True})
    if raw.get("similar_to"):
        a = _find_area(str(raw["similar_to"]), cases)
        out["similar_to"] = a["area_id"] if a else None
    if raw.get("rank") in INDICATOR_TERMS:
        out["rank"] = raw["rank"]
    out["unsupported"] = [str(u)[:60] for u in (raw.get("unsupported") or [])][:5]
    return out


def _zip_signal(case: dict, ind: str) -> Optional[dict]:
    """For a neighborhood, the ZIP-level signal of the ZIP covering most of it."""
    mk = case["evidence"]["context"].get("zip_market") or {}
    zips = mk.get("zips") or []
    if not zips:
        return None
    for s in zips[0]["signals"]:
        if s["indicator"] == ind:
            return {**s, "via_zip": zips[0]["zip"]}
    return None


def _z(case: dict, ind: str) -> Optional[float]:
    if ind in ZIP_INDICATORS and case.get("geography") != "zip":
        s = _zip_signal(case, ind)
        return s.get("z_score") if s and s.get("status") == "scored" else None
    if ind == "city_owned_vacant_lots_per_km2":
        v = case["evidence"]["context"].get("city_owned_vacant_lots")
        return v.get("z_vs_neighborhoods") if v else None
    for s in case["evidence"]["signals"]:
        if s["indicator"] == ind:
            return s.get("z_score") if s["status"] == "scored" else None
    return None


def _evidence_line(case: dict, ind: str, indicators: dict) -> str:
    if ind == "city_owned_vacant_lots_per_km2":
        v = case["evidence"]["context"]["city_owned_vacant_lots"]
        return f"{v['value']} City-owned vacant lots ({v['per_km2']:.1f}/km² vs {v['city_per_km2']:.1f} citywide; {v['snapshot']} snapshot)"
    sigs = case["evidence"]["signals"]
    via = ""
    if ind in ZIP_INDICATORS and case.get("geography") != "zip":
        zs = _zip_signal(case, ind)
        sigs = [zs] if zs else []
        via = f" (ZIP {zs['via_zip']})" if zs else ""
    for s in sigs:
        if s["indicator"] == ind:
            unit = "$" if s["unit"].startswith("USD") else ""
            b, r = s["baseline_value"], s["recent_value"]
            if b is None or r is None:
                return f"{s['short']}: UNKNOWN"

            def fmt(x):
                if not unit:
                    return f"{x:,.0f}"
                return f"${x / 1e6:.1f}M" if x >= 1e6 else (f"${x / 1e3:.0f}K" if x >= 1e4 else f"${x:,.0f}")
            ch = f" ({s['change_pct'] * 100:+.0f}%)" if s.get("change_pct") is not None else ""
            city = f"{s['city_change_pct'] * 100:+.0f}%" if s.get("city_change_pct") is not None else "n/a"
            where = "county" if (case.get("geography") == "zip" or ind in ZIP_INDICATORS) else "city"
            return f"{s['short']}{via}: {fmt(b)} → {fmt(r)}{ch}; {where} {city}"
    return ""


def investigate(question: str, cases: List[dict], indicators: dict, threshold: float = 0.5, limit: int = 10) -> dict:
    if not question or not question.strip():
        return {"question": question, "query": None, "results": [], "message": "Ask a question about the neighborhoods."}
    query = _llm_parse(question, cases) or parse(question, cases)
    by_area = {c["area_id"]: c for c in cases}
    notes = []
    if query["unsupported"]:
        notes.append("UNKNOWN for: " + ", ".join(query["unsupported"]) +
                     ". These are not in the loaded data. Rents, home values and sales are available at ZIP-code level; "
                     "income and population need Census ACS data.")
    if query["similar_to"]:
        c = by_area[query["similar_to"]]
        return {"question": question, "query": query,
                "interpretation": f"{'ZIP codes' if c.get('geography') == 'zip' else 'Neighborhoods'} whose pattern of change most resembles {c['name']}",
                "results": [{"area_id": s["area_id"], "name": s["name"], "case_id": by_area[s["area_id"]]["id"],
                             "score": s["similarity"], "evidence": [x["text"] for x in s["shared"]] or ["Similar overall direction of change"]}
                            for s in c["similar_cases"]],
                "notes": notes, "method": "Cosine similarity of standardised change signals (see METHODOLOGY.md)."}
    if not query["conditions"]:
        return {"question": question, "query": query, "results": [],
                "interpretation": "No measurable indicator recognised.",
                "notes": notes or ["Try asking about rents, home values, sale prices, home sales, new construction, demolitions, renovations, permit value or City-owned vacant land."],
                "message": "Sherlock can only answer from indicators it has calculated."}
    results = []
    only_zip = all(cd["indicator"] in ZIP_INDICATORS for cd in query["conditions"])
    pool = [c for c in cases if (c.get("geography") == "zip") == only_zip]
    if not only_zip and any(cd["indicator"] in ZIP_INDICATORS for cd in query["conditions"]):
        notes.append("Market conditions (rents, home values, sales, prices) are checked using the ZIP code that covers most of each neighborhood.")
    for c in pool:
        zs = {}
        ok = True
        for cond in query["conditions"]:
            z = _z(c, cond["indicator"])
            if z is None:
                ok = False
                break
            if (cond["direction"] == "up" and z < threshold) or (cond["direction"] == "down" and z > -threshold):
                ok = False
                break
            zs[cond["indicator"]] = z
        if ok:
            strength = sum(abs(v) for v in zs.values())
            results.append({"area_id": c["area_id"], "name": c["name"], "case_id": c["id"], "level": c["level"],
                            "score": strength, "z_scores": zs,
                            "evidence": [_evidence_line(c, i, indicators) for i in zs]})
    if query["rank"]:
        sign = next(cd["direction"] for cd in query["conditions"] if cd["indicator"] == query["rank"])
        results.sort(key=lambda r: -r["z_scores"][query["rank"]] if sign == "up" else r["z_scores"][query["rank"]])
    else:
        results.sort(key=lambda r: -r["score"])
    parts = []
    for cd in query["conditions"]:
        lab = indicators.get(cd["indicator"], {}).get("short", cd["indicator"])
        rel = "higher than" if cd["direction"] == "up" else "lower than"
        if cd["indicator"] in ZIP_INDICATORS:
            parts.append(f"{lab} {'higher' if cd['direction'] == 'up' else 'lower'} than the typical Allegheny County ZIP (ZIP-code level)")
        elif cd["indicator"] == "city_owned_vacant_lots_per_km2":
            parts.append(f"{lab} {'above' if cd['direction'] == 'up' else 'below'} the typical neighborhood")
        else:
            parts.append(f"{lab} {rel} the citywide trend implies (2023–25 vs 2020–22)")
    return {"question": question, "query": query,
            "interpretation": ("ZIP codes where " if only_zip else "Neighborhoods where ") + " AND ".join(parts) + f" (|z| ≥ {threshold})",
            "results": results[:limit], "total_matches": len(results), "notes": notes,
            "method": "Filters Sherlock's precomputed z-scores; no values are generated by a language model.",
            "caution": "Matching patterns do not establish that one change caused another."}
