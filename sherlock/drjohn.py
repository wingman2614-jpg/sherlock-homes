"""Dr. John — Sherlock's assistant chatbot.

Answers questions using two kinds of evidence, always cited:
  [D#] Sherlock's own calculated data (case files, ZIP/neighborhood signals,
       dataset definitions, methodology) — retrieved deterministically.
  [W#] Free online sources that need no API key: Wikipedia, DuckDuckGo
       Instant Answers and the WPRDC open-data catalog.

The language model only writes the answer from that evidence. Providers,
in order of preference (all optional):
  1. Anthropic API        — if ANTHROPIC_API_KEY is set
  2. Ollama (local, free) — if running on http://localhost:11434
  3. No model             — Dr. John lists what he found, cited

Every answer is checked: numbers that don't appear in the evidence and
causal language are flagged to the user.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

from . import config

UA = "SherlockHomesMk2/2.0 (housing hackathon project; contact: local user)"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
ANTHROPIC_MODEL = os.environ.get("SHERLOCK_LLM_MODEL", "claude-sonnet-4-5")
CAUSAL = ["caused", "causing", "because of", "led to", "leads to", "resulted in", "drove", "driven by", "due to", "triggered"]

Fetcher = Callable[[str, Optional[dict], float], dict]


def http_json(url: str, body: Optional[dict] = None, timeout: float = 12.0, headers: Optional[dict] = None) -> dict:
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _default_fetch(url: str, body: Optional[dict] = None, timeout: float = 12.0) -> dict:
    return http_json(url, body, timeout)


# ---------------------------------------------------------------------------
# Local data retrieval
# ---------------------------------------------------------------------------
def _fmt_pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:+.0f}%"


def _signal_line(s: dict, comp: str) -> str:
    if s.get("status") != "scored":
        return f"{s['label']}: UNKNOWN (not enough data)"
    unit = s.get("unit", "")

    def v(x):
        if x is None:
            return "n/a"
        if unit == "USD per month":
            return f"${x:,.0f}/month"
        if unit.startswith("USD"):
            return f"${x:,.0f}"
        return f"{x:,.0f}"
    return (f"{s['label']}: {v(s.get('baseline_value'))} ({s['baseline_period']}) → {v(s.get('recent_value'))} ({s['recent_period']}), "
            f"change {_fmt_pct(s.get('change_pct'))}; {comp} {_fmt_pct(s.get('city_change_pct'))}")


def case_snippet(c: dict) -> str:
    comp = "typical Allegheny County ZIP" if c.get("geography") == "zip" else "citywide"
    lines = [f"{c['name']} ({'ZIP code' if c.get('geography') == 'zip' else 'City of Pittsburgh neighborhood'}): "
             f"unusualness {c['level']}, data confidence {c['confidence']['level']}. {c.get('plain', {}).get('headline', '')}"]
    for s in c["evidence"]["signals"]:
        lines.append("- " + _signal_line(s, comp))
    mk = c["evidence"]["context"].get("zip_market")
    if mk and mk.get("plain"):
        lines.append("- Wider market (ZIP level): " + mk["plain"])
    vac = c["evidence"]["context"].get("city_owned_vacant_lots")
    if vac and vac.get("value") is not None:
        lines.append(f"- City-owned vacant lots: {vac['value']:.0f} (snapshot {vac['snapshot']})")
    first = c.get("what_changed_first", {}).get("ordered", [])
    if first:
        lines.append("- Timing (not causation): " + "; ".join(f"{o['short']} {o['direction']} from {o['year']}" for o in first[:3]))
    lines.append("- Key limits: " + " ".join(c.get("limitations", [])[:3]))
    return "\n".join(lines)


def find_areas(question: str, store) -> List[dict]:
    q = question.lower()
    found = []
    for z in re.findall(r"\b(15\d{3})\b", q):
        for c in store.zip_cases:
            if c.get("zip") == z:
                found.append(c)
    names = sorted(store.cases, key=lambda c: -len(c["name"]))
    taken = q
    for c in names:
        n = c["name"].lower()
        if len(n) >= 4 and re.search(rf"\b{re.escape(n)}\b", taken):
            found.append(c)
            taken = taken.replace(n, " ")
    return found[:3]


def local_evidence(question: str, store, case_id: Optional[str] = None) -> List[dict]:
    items: List[dict] = []

    def add(title: str, text: str, ref: Optional[str] = None):
        items.append({"type": "data", "title": title, "text": text, "case_id": ref})

    seen = set()
    if case_id:
        try:
            c = store.get_case(case_id)
            if "evidence" in c:
                add(f"Case file open on screen: {c['name']}", case_snippet(c), c["id"])
                seen.add(c["id"])
        except Exception:
            pass
    for c in find_areas(question, store):
        if c["id"] not in seen:
            add(f"Case file: {c['name']}", case_snippet(c), c["id"])
            seen.add(c["id"])

    r = store.investigate(question)
    if r.get("results"):
        lines = [r.get("interpretation", "")] + [f"- {x['name']}: " + "; ".join(x["evidence"]) for x in r["results"][:6]]
        add("Sherlock search across all areas", "\n".join(lines))
    unknown = [n for n in r.get("notes", []) if "UNKNOWN" in n]
    if unknown:
        add("What Sherlock cannot measure", " ".join(unknown))

    s = store.summary
    trends = "; ".join(f"{k.replace('_', ' ')}: {v['change_pct'] * 100:+.0f}%" for k, v in s["city_trends"].items() if v.get("change_pct") is not None)
    zs = s.get("zip") or {}
    add("Overview",
        f"Sherlock analyses {s['areas']} City of Pittsburgh neighborhoods (permits {s['baseline_years'][0]}–{s['baseline_years'][-1]} vs "
        f"{s['recent_years'][0]}–{s['recent_years'][-1]}; {s['cases_worth_investigating']} flagged) and {zs.get('areas', 'n/a')} Allegheny County "
        f"ZIP codes ({zs.get('cases_worth_investigating', 'n/a')} flagged). Citywide permit changes: {trends}.")

    ql = question.lower()
    if re.search(r"\b(data|dataset|source|where.*from|method|how (do|does|is|are)|score|confiden|calculat|flag)", ql):
        srcs = "; ".join(f"{v['name']} ({v['geography']}, {v['coverage']})" for v in config.SOURCES.values())
        add("Datasets Sherlock uses", srcs)
        add("How Sherlock scores areas",
            "Each area's change is compared with the city (neighborhoods) or the typical county ZIP (ZIP codes); robust z-scores "
            "(median/MAD) are combined as a root-mean-square score. HIGH if score ≥ 1.5 or any |z| ≥ 3; MEDIUM if ≥ 1.0 or any |z| ≥ 2. "
            "Confidence depends on record counts, missing indicators, and whether independent sources agree. Unusual does not mean good or bad.")
    if "metro" in ql or "region" in ql or "pittsburgh area" in ql:
        m = store.metro
        lines = [f"- {x['short']} ({x['window']}): Pittsburgh {x['change'] * 100 if x['transform'] != 'diff' else x['change']:+.1f}"
                 f"{'%' if x['transform'] != 'diff' else ''} vs peer median" for x in m["signals"][:8]]
        add("Pittsburgh metro vs other metros (Zillow)", "\n".join(lines))
    return items[:7]


# ---------------------------------------------------------------------------
# Free web retrieval (no API keys)
# ---------------------------------------------------------------------------
LOCAL_HINT = re.compile(r"pittsburgh|allegheny|neighborhood|neighbourhood|\b15\d{3}\b|here|our city|this area", re.I)


def web_evidence(question: str, fetch: Fetcher = _default_fetch, limit: int = 3) -> List[dict]:
    out: List[dict] = []
    q = question.strip()
    wq = q if re.search(r"pittsburgh|allegheny", q, re.I) or not LOCAL_HINT.search(q) else f"{q} Pittsburgh"
    # Wikipedia
    try:
        s = fetch("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "list": "search", "srsearch": wq, "format": "json", "srlimit": 2}), None, 10)
        for hit in s.get("query", {}).get("search", [])[:2]:
            title = hit["title"]
            summ = fetch("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_")), None, 10)
            text = (summ.get("extract") or "").strip()
            if text:
                out.append({"type": "web", "title": f"Wikipedia: {title}", "text": text[:900],
                            "url": summ.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}")})
    except Exception:
        pass
    # DuckDuckGo Instant Answer
    try:
        d = fetch("https://api.duckduckgo.com/?" + urllib.parse.urlencode({"q": q, "format": "json", "no_html": 1, "skip_disambig": 1}), None, 8)
        if d.get("AbstractText"):
            out.append({"type": "web", "title": f"DuckDuckGo: {d.get('Heading') or q}", "text": d["AbstractText"][:700],
                        "url": d.get("AbstractURL") or "https://duckduckgo.com/?q=" + urllib.parse.quote(q)})
    except Exception:
        pass
    # WPRDC open-data catalog (useful for "where can I find data on …")
    if re.search(r"data|dataset|where can i|find|download|source", q, re.I):
        try:
            w = fetch("https://data.wprdc.org/api/3/action/package_search?" + urllib.parse.urlencode({"q": re.sub(r"[^\w\s]", " ", q), "rows": 3}), None, 10)
            for p in w.get("result", {}).get("results", [])[:3]:
                out.append({"type": "web", "title": f"WPRDC dataset: {p.get('title')}",
                            "text": (p.get("notes") or "")[:400], "url": f"https://data.wprdc.org/dataset/{p.get('name')}"})
        except Exception:
            pass
    return out[:limit + 2]


# ---------------------------------------------------------------------------
# Language model providers (all optional)
# ---------------------------------------------------------------------------
def ollama_model(fetch: Fetcher = _default_fetch) -> Optional[str]:
    want = os.environ.get("DRJOHN_OLLAMA_MODEL")
    try:
        tags = fetch(f"{OLLAMA_URL}/api/tags", None, 3)
    except Exception:
        return None
    names = [m.get("name") for m in tags.get("models", []) if m.get("name")]
    if not names:
        return None
    if want and any(n == want or n.startswith(want + ":") for n in names):
        return next(n for n in names if n == want or n.startswith(want + ":"))
    for pref in ("llama3", "qwen", "mistral", "gemma", "phi"):
        for n in names:
            if pref in n and "embed" not in n:
                return n
    return next((n for n in names if "embed" not in n), None)


def system_prompt(mode: str) -> str:
    style = ("Explain in plain, friendly language for non-experts, in at most 150 words. Avoid statistics jargon such as z-scores."
             if mode == "basic" else
             "Be precise and analytical, in at most 250 words. You may mention z-scores, periods and sources.")
    return (
        "You are Dr. John, the assistant in Sherlock Homes, a housing-data tool for Pittsburgh. Answer the user's question using ONLY the "
        "EVIDENCE provided. Cite every fact with its tag, e.g. [D1] for Sherlock data or [W2] for web sources. Prefer Sherlock data [D#] for "
        "anything about Pittsburgh areas; use web sources [W#] for background and definitions. If the evidence does not answer the question, "
        "say so plainly and suggest what data would help. Never invent numbers. Never claim that one change caused another; describe timing "
        "or co-occurrence instead. Do not give legal, financial or zoning advice. " + style
    )


def build_prompt(question: str, evidence: List[dict], history: List[dict]) -> str:
    ev = []
    for e in evidence:
        tag = e["tag"]
        src = f" (source: {e['url']})" if e.get("url") else ""
        ev.append(f"[{tag}] {e['title']}{src}\n{e['text']}")
    hist = "\n".join(f"{m['role'].upper()}: {m['content'][:500]}" for m in history[-6:])
    return f"EVIDENCE:\n\n" + "\n\n".join(ev) + (f"\n\nEARLIER CONVERSATION:\n{hist}" if hist else "") + f"\n\nQUESTION: {question}"


def ask_anthropic(system: str, prompt: str, fetch_post=http_json) -> Optional[str]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = {"model": ANTHROPIC_MODEL, "max_tokens": 700, "system": system, "messages": [{"role": "user", "content": prompt}]}
    data = fetch_post("https://api.anthropic.com/v1/messages", body, 45,
                      {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip() or None


def ask_ollama(model: str, system: str, prompt: str, fetch: Fetcher = _default_fetch) -> Optional[str]:
    body = {"model": model, "stream": False, "options": {"temperature": 0.2},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    data = fetch(f"{OLLAMA_URL}/api/chat", body, 180)
    return (data.get("message", {}) or {}).get("content", "").strip() or None


def no_model_answer(question: str, evidence: List[dict], mode: str) -> str:
    data = [e for e in evidence if e["type"] == "data" and e["title"] != "Overview"]
    web = [e for e in evidence if e["type"] == "web"]
    parts = []
    if data:
        parts.append("Here's what I found in Sherlock's data:")
        for e in data[:3]:
            lines = e["text"].split("\n")
            parts.append(f"• {lines[0]} [{e['tag']}]")
            detail = [l[2:] for l in lines[1:] if l.startswith("- ") and "UNKNOWN" not in l and not l.startswith("- Key limits")]
            for l in detail[:2 if mode == "basic" else 4]:
                parts.append(f"   – {l}")
    if web:
        parts.append("From the web:")
        for e in web[:2]:
            sent = re.split(r"(?<=[.!?])\s", e["text"])
            parts.append(f"• {' '.join(sent[:2])} [{e['tag']}]")
    if not parts:
        overview = next((e for e in evidence if e["title"] == "Overview"), None)
        parts.append("I couldn't find anything specific about that in Sherlock's data or online sources."
                     + (f" In general: {overview['text']} [{overview['tag']}]" if overview else ""))
    parts.append("(I'm running without an AI model, so I'm listing what I found. Install the free Ollama app to let me answer conversationally.)")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
NUM = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")


def _norm(tok: str) -> str:
    return tok.replace("$", "").replace(",", "").replace("%", "").rstrip(".")


def verify(answer: str, evidence: List[dict]) -> dict:
    ctx = " ".join(e["text"] + " " + e["title"] for e in evidence)
    allowed = {_norm(t) for t in NUM.findall(ctx)}
    # also allow rounded forms of percentages/values in the evidence
    for t in list(allowed):
        try:
            f = float(t)
            allowed.update({f"{f:.0f}", f"{f:.1f}", f"{abs(f):.0f}", f"{abs(f):.1f}"})
        except ValueError:
            pass
    unmatched = []
    for tok in NUM.findall(answer):
        n = _norm(tok)
        if not n or re.fullmatch(r"\d", n) or re.fullmatch(r"(19|20)\d\d", n):
            continue  # single digits and years
        if n not in allowed and n.lstrip("+-") not in allowed:
            unmatched.append(tok)
    low = answer.lower()
    causal = [p for p in CAUSAL if re.search(rf"\b{re.escape(p)}\b", low)]
    return {"unmatched_numbers": sorted(set(unmatched))[:8], "causal_language": causal,
            "ok": not unmatched and not causal}


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------
def chat(question: str, store, history: Optional[List[dict]] = None, case_id: Optional[str] = None,
         mode: str = "basic", use_web: bool = True, fetch: Fetcher = _default_fetch,
         anthropic_post=http_json) -> dict:
    question = (question or "").strip()[:800]
    history = history or []
    if not question:
        return {"answer": "Ask me anything about Pittsburgh housing or how Sherlock works.", "sources": [], "provider": "none", "verification": None}
    evidence = local_evidence(question, store, case_id)
    web_status = "disabled"
    if use_web:
        web = web_evidence(question, fetch)
        evidence += web
        web_status = f"{len(web)} results" if web else "no results or offline"
    d = w = 0
    for e in evidence:
        if e["type"] == "data":
            d += 1
            e["tag"] = f"D{d}"
        else:
            w += 1
            e["tag"] = f"W{w}"

    system = system_prompt(mode)
    prompt = build_prompt(question, evidence, history)
    answer, provider, note = None, "none", None
    try:
        answer = ask_anthropic(system, prompt, anthropic_post)
        if answer:
            provider = f"Claude ({ANTHROPIC_MODEL})"
    except Exception as e:  # noqa: BLE001
        note = f"Anthropic API unavailable ({type(e).__name__})."
    if not answer:
        model = ollama_model(fetch)
        if model:
            try:
                answer = ask_ollama(model, system, prompt, fetch)
                if answer:
                    provider = f"Local AI via Ollama ({model})"
            except Exception as e:  # noqa: BLE001
                note = f"Ollama did not answer ({type(e).__name__})."
    if not answer:
        answer = no_model_answer(question, evidence, mode)
        provider = "No AI model (search results only)"
    ver = verify(answer, evidence)
    return {
        "answer": answer,
        "provider": provider,
        "note": note,
        "web": web_status,
        "sources": [{"tag": e["tag"], "type": e["type"], "title": e["title"], "url": e.get("url"), "case_id": e.get("case_id"),
                     "excerpt": e["text"][:300]} for e in evidence],
        "verification": ver,
        "disclaimer": "Dr. John explains evidence; he does not establish causes or give legal, financial or zoning advice.",
    }
