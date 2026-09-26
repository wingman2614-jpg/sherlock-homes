"""Step 4 — deterministic analytics: change signals, anomaly scores,
timelines, 'what changed first', similarity, conflicts and confidence.

Nothing in this module uses an LLM. Every number it produces can be traced
back to rows in the observation table.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import config
from .indicators import INDICATORS, NEIGHBORHOOD_SCORED, meta
from .ingest import load_redfin_national, load_zillow_wide, zillow_date_columns
from .normalize import METRO_SOURCE
from .stats import (cosine_similarity, percentile_rank, poisson_residual, rms,
                    robust_center_scale, robust_z, safe_pct_change)

COUNT_INDICATORS = [i for i in NEIGHBORHOOD_SCORED if INDICATORS[i]["method"] == "count_vs_city_trend"]
VALUE_INDICATOR = "res_permit_value"


def _period_label(years) -> str:
    return f"{years[0]}–{years[-1]}"


def _source_block(indicator: str, start: str, end: str, geography: str) -> dict:
    m = INDICATORS[indicator]
    s = config.SOURCES[m["source_id"]]
    return {
        "source": s["name"], "source_id": m["source_id"], "source_file": s["file"],
        "geography": geography, "period_start": start, "period_end": end,
        "time_resolution": m["time_resolution"],
    }


# ---------------------------------------------------------------------------
# Annual pivots
# ---------------------------------------------------------------------------
def annual_table(obs: pd.DataFrame) -> Tuple[Dict, Dict, Dict]:
    """Return values[area][indicator][year], n_records[...], partial flag per year."""
    sub = obs[obs.geography.isin(["neighborhood", "city"]) & obs.indicator.isin(NEIGHBORHOOD_SCORED)].copy()
    sub["year"] = sub.period_start.str[:4].astype(int)
    values: Dict = defaultdict(lambda: defaultdict(dict))
    nrec: Dict = defaultdict(lambda: defaultdict(dict))
    partial: Dict[int, str] = {}
    for r in sub.itertuples(index=False):
        values[r.area_id][r.indicator][r.year] = r.value
        nrec[r.area_id][r.indicator][r.year] = r.n_records
        if isinstance(r.flags, str) and "partial_year" in r.flags:
            partial[r.year] = [f for f in r.flags.split(";") if f.startswith("partial_year")][0]
    return values, nrec, partial


def _sum_years(d: Dict[int, float], years) -> float:
    return float(sum(d.get(y, 0) or 0 for y in years))


def _indicator_permits(permits: pd.DataFrame, ind: str) -> pd.DataFrame:
    if ind == "res_new_construction_permits":
        return permits[(permits.category == "new_construction") & permits.is_residential]
    if ind == "demolition_permits":
        return permits[permits.category == "demolition"]
    if ind == "res_alteration_permits":
        return permits[(permits.category == "alteration") & permits.is_residential]
    raise KeyError(ind)


# ---------------------------------------------------------------------------
# Neighborhood change signals
# ---------------------------------------------------------------------------
def neighborhood_signals(obs: pd.DataFrame, permits: pd.DataFrame, names: Dict[str, str]) -> Dict[str, Dict[str, dict]]:
    values, nrec, _ = annual_table(obs)
    city = values["city-pittsburgh"]
    B, R = config.BASELINE_YEARS, config.RECENT_YEARS
    start, end = f"{B[0]}-01-01", f"{R[-1]}-12-31"
    out: Dict[str, Dict[str, dict]] = {nid: {} for nid in names}
    raw_stat: Dict[str, Dict[str, float]] = defaultdict(dict)

    for ind in COUNT_INDICATORS:
        cb, cr = _sum_years(city[ind], B), _sum_years(city[ind], R)
        city_ratio = cr / cb if cb else None
        for nid in names:
            b, r = _sum_years(values[nid][ind], B), _sum_years(values[nid][ind], R)
            m = INDICATORS[ind]
            sig = {
                "indicator": ind, "label": m["label"], "short": m["short"], "category": m["category"], "unit": m["unit"],
                "method": "Observed count vs. count expected if the neighborhood had followed the citywide trend",
                "baseline_period": _period_label(B), "recent_period": _period_label(R),
                "baseline_value": b, "recent_value": r,
                "change_pct": safe_pct_change(r, b) if b >= config.MIN_TOTAL_COUNT else None,
                "city_baseline": cb, "city_recent": cr, "city_change_pct": safe_pct_change(cr, cb),
                "notes": [],
                **_source_block(ind, start, end, "neighborhood"),
            }
            if b < config.MIN_TOTAL_COUNT and b > 0:
                sig["notes"].append(f"Percent change not shown: baseline of {int(b)} is below the minimum of {config.MIN_TOTAL_COUNT}.")
            if b == 0:
                sig["notes"].append("No permits of this type in the baseline period, so percent change is undefined.")
            expected = b * city_ratio if city_ratio is not None else None
            sig["expected_recent"] = expected
            if city_ratio is None or (b + r) < config.MIN_TOTAL_COUNT or (expected is not None and expected < config.MIN_EXPECTED_COUNT and r < config.MIN_EXPECTED_COUNT):
                sig["status"] = "insufficient_data"
                sig["notes"].append(f"Too few permits to score ({int(b + r)} across both periods; minimum {config.MIN_TOTAL_COUNT}, and expected or observed recent count must reach {config.MIN_EXPECTED_COUNT:g}).")
            else:
                sig["status"] = "scored"
                raw_stat[ind][nid] = poisson_residual(r, expected)
                sig["residual"] = raw_stat[ind][nid]
            sub = _indicator_permits(permits, ind)
            rec = sub[(sub.neighborhood_id == nid) & sub.year.isin(R)]
            if len(rec) >= 5:
                day_max = int(rec.groupby("issue_date").size().max())
                sig["largest_same_day_batch"] = day_max
                if day_max / len(rec) > 0.5:
                    sig["notes"].append(f"{day_max} of {len(rec)} recent permits were issued on the same day, which suggests one multi-lot project rather than many separate ones.")
            if ind == "demolition_permits":
                d = permits[(permits.category == "demolition") & (permits.neighborhood_id == nid) & permits.year.isin(R)]
                cf = int((d.demolition_kind == "city_funded").sum())
                if len(d):
                    sig["notes"].append(f"{cf} of {len(d)} recent demolition permits were City-funded (typically condemned structures).")
            out[nid][ind] = sig

    # value indicator: log ratio relative to city
    ind = VALUE_INDICATOR
    m = INDICATORS[ind]
    cvb, cvr = _sum_years(city[ind], B), _sum_years(city[ind], R)
    val_perm = permits[permits.is_residential & permits.category.isin(["new_construction", "alteration"]) & permits.project_value.notna()]
    for nid in names:
        vb, vr = _sum_years(values[nid][ind], B), _sum_years(values[nid][ind], R)
        nb, nr = _sum_years(nrec[nid][ind], B), _sum_years(nrec[nid][ind], R)
        sig = {
            "indicator": ind, "label": m["label"], "short": m["short"], "category": m["category"], "unit": m["unit"],
            "method": "Log ratio of recent to baseline permit value, relative to the same ratio citywide",
            "baseline_period": _period_label(B), "recent_period": _period_label(R),
            "baseline_value": vb, "recent_value": vr, "baseline_n": int(nb), "recent_n": int(nr),
            "change_pct": safe_pct_change(vr, vb) if nb >= config.MIN_VALUE_PERMITS else None,
            "city_baseline": cvb, "city_recent": cvr, "city_change_pct": safe_pct_change(cvr, cvb),
            "expected_recent": vb * (cvr / cvb) if cvb else None,
            "notes": [], **_source_block(ind, start, end, "neighborhood"),
        }
        recent = val_perm[(val_perm.neighborhood_id == nid) & val_perm.year.isin(R)]
        if len(recent) and vr > 0:
            top = recent.project_value.max()
            sig["largest_recent_permit_share"] = float(top / vr)
            if top / vr > 0.5:
                sig["notes"].append(f"One permit accounts for {top / vr:.0%} of recent declared value.")
        if nb < config.MIN_VALUE_PERMITS or nr < config.MIN_VALUE_PERMITS or vb <= 0 or vr <= 0 or cvb <= 0:
            sig["status"] = "insufficient_data"
            sig["notes"].append(f"Too few permits with a declared value to score ({int(nb)} baseline, {int(nr)} recent; minimum {config.MIN_VALUE_PERMITS} each).")
        else:
            sig["status"] = "scored"
            lr = math.log(vr / vb) - math.log(cvr / cvb)
            raw_stat[ind][nid] = lr
            sig["residual"] = lr
        out[nid][ind] = sig

    # standardise across neighborhoods
    for ind, stats in raw_stat.items():
        z = robust_z(stats)
        pop = list(stats.values())
        for nid, zval in z.items():
            s = out[nid][ind]
            s["z_score"] = float(zval)
            s["percentile"] = percentile_rank(stats[nid], pop)
            s["direction"] = "above_city_trend" if stats[nid] > 0 else ("below_city_trend" if stats[nid] < 0 else "in_line")
            s["n_compared"] = len(pop)
    return out


def anomaly_level(zs: List[float]) -> Tuple[Optional[float], str]:
    if len(zs) < 2:
        return (rms(zs) if zs else None), "INSUFFICIENT DATA"
    score = rms(zs)
    mx = max(abs(z) for z in zs)
    if score >= config.LEVEL_HIGH_RMS or mx >= config.LEVEL_HIGH_MAX:
        return score, "HIGH"
    if score >= config.LEVEL_MED_RMS or mx >= config.LEVEL_MED_MAX:
        return score, "MEDIUM"
    return score, "LOW"


# ---------------------------------------------------------------------------
# Timeline and "what changed first"
# ---------------------------------------------------------------------------
ONSET_BASE_YEARS = (2020, 2021)
ONSET_TEST_YEARS = (2022, 2023, 2024, 2025)
ONSET_RESIDUAL = 2.0
ONSET_VALUE_LOG = math.log(2.0)


def timelines(obs: pd.DataFrame, names: Dict[str, str], signals: Dict[str, Dict[str, dict]]) -> Dict[str, dict]:
    values, nrec, partial = annual_table(obs)
    city = values["city-pittsburgh"]
    years = sorted({y for ind in NEIGHBORHOOD_SCORED for y in city[ind]})
    out = {}
    for nid in names:
        series = {}
        onsets = []
        for ind in NEIGHBORHOOD_SCORED:
            rows = []
            nb = values[nid][ind]
            cb_base = _sum_years(city[ind], ONSET_BASE_YEARS)
            nb_base = _sum_years(nb, ONSET_BASE_YEARS)
            share = nb_base / cb_base if cb_base else None
            onset = None
            for y in years:
                v, cv = nb.get(y), city[ind].get(y)
                exp = share * cv if (share is not None and cv is not None) else None
                dev = None
                if y in ONSET_TEST_YEARS and exp is not None and v is not None:
                    if ind == VALUE_INDICATOR:
                        if (nrec[nid][ind].get(y) or 0) >= 3 and v > 0 and exp > 0:
                            dev = math.log(v / exp)
                            if onset is None and abs(dev) >= ONSET_VALUE_LOG:
                                onset = (y, "up" if dev > 0 else "down", dev)
                    else:
                        dev = poisson_residual(v, exp)
                        if onset is None and abs(dev) >= ONSET_RESIDUAL and max(v, exp) >= 3:
                            onset = (y, "up" if dev > 0 else "down", dev)
                rows.append({
                    "year": y, "value": v, "city_value": cv,
                    "expected_from_2020_21_share": exp, "deviation": dev,
                    "partial": partial.get(y),
                })
            series[ind] = rows
            m = INDICATORS[ind]
            if onset:
                y, d, dev = onset
                onsets.append({
                    "indicator": ind, "label": m["label"], "short": m["short"], "year": y, "direction": d,
                    "deviation": dev,
                    "statement": f"{m['short']} first departed from its 2020–21 share of citywide activity in {y} ({'higher' if d == 'up' else 'lower'} than that share implied).",
                })
            else:
                onsets.append({"indicator": ind, "label": m["label"], "short": m["short"], "year": None, "direction": None,
                               "statement": f"{m['short']}: no clear departure from its 2020–21 share of citywide activity in 2022–2025."})
        ordered = sorted([o for o in onsets if o["year"]], key=lambda o: (o["year"], -abs(o["deviation"])))
        # rank with ties
        rank, last = 0, None
        for o in ordered:
            if o["year"] != last:
                rank += 1
                last = o["year"]
            o["order"] = rank
        out[nid] = {
            "series": series,
            "what_changed_first": {
                "ordered": ordered,
                "no_clear_change": [o for o in onsets if not o["year"]],
                "method": ("For each year 2022–2025 Sherlock compares the neighborhood's count with the count expected "
                           "if it had kept its 2020–21 share of citywide permits. A count indicator 'departs' when "
                           "(observed − expected)/√(expected+1) reaches ±2 (with at least 3 permits observed or expected); "
                           "permit value departs when it is at least double or at most half the expected value."),
                "caution": "Order of change does not establish causation. An earlier change did not necessarily cause a later one.",
            },
            "partial_years": partial,
        }
    return out


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------
def similarity(signals: Dict[str, Dict[str, dict]], names: Dict[str, str], vacancy_z: Dict[str, float], top_k: int = 5,
               features: Optional[List[str]] = None) -> Dict[str, List[dict]]:
    feats = features or (NEIGHBORHOOD_SCORED + ["city_owned_vacant_lots_per_km2"])
    vecs, avail = {}, {}
    for nid in names:
        v, a = [], []
        for f in feats:
            if f not in signals[nid]:
                z = vacancy_z.get(nid)
            else:
                s = signals[nid][f]
                z = s.get("z_score") if s["status"] == "scored" else None
            a.append(z is not None)
            v.append(float(np.clip(z, -4, 4)) if z is not None else 0.0)  # clip so one extreme value can't dominate
        vecs[nid], avail[nid] = np.array(v), a
    out = {}
    for nid in names:
        if sum(avail[nid]) < 3:
            out[nid] = []
            continue
        cands = []
        for other in names:
            if other == nid or sum(avail[other]) < 3:
                continue
            mask = np.array([x and y for x, y in zip(avail[nid], avail[other])])
            if mask.sum() < 3:  # need at least 3 shared features for a meaningful comparison
                continue
            a, b = vecs[nid][mask], vecs[other][mask]
            cs = cosine_similarity(a, b)
            if cs is None:
                continue
            dist = float(np.linalg.norm(a - b))
            shared, differ = [], []
            for f, za, zb in zip(np.array(feats)[mask], a, b):
                lab = INDICATORS[f]["short"]
                if abs(za) >= 0.5 and abs(zb) >= 0.5 and np.sign(za) == np.sign(zb):
                    rel = "above" if za > 0 else "below"
                    shared.append({"indicator": f, "label": lab, "direction": rel, "z_self": float(za), "z_other": float(zb),
                                   "text": f"{lab}: both {rel} the typical pattern (z {za:+.1f} vs {zb:+.1f})"})
                elif abs(za - zb) >= 1.5:
                    differ.append({"indicator": f, "label": lab, "z_self": float(za), "z_other": float(zb),
                                   "text": f"{lab}: differs (z {za:+.1f} vs {zb:+.1f})"})
            cands.append({"area_id": other, "name": names[other], "similarity": max(cs, 0.0), "cosine": cs,
                          "distance": dist, "features_compared": int(mask.sum()), "shared": shared, "differences": differ})
        cands.sort(key=lambda c: (-c["cosine"], c["distance"]))
        out[nid] = cands[:top_k]
    return out


# ---------------------------------------------------------------------------
# Metro context (Pittsburgh MSA vs peer metros)
# ---------------------------------------------------------------------------
def _metro_change(wide: pd.DataFrame, transform: str, months: int) -> Tuple[pd.Series, str, str]:
    cols = zillow_date_columns(wide)
    data = wide.set_index("RegionID")[cols]
    data = data[wide.set_index("RegionID")["RegionType"] == "msa"]
    last = cols[-1]
    if transform == "pct_ttm":
        cur = data[cols[-12:]].sum(axis=1, min_count=12)
        prev = data[cols[-12 - months:-months]].sum(axis=1, min_count=12)
        ch = cur / prev - 1
        # tiny bases make percentages unstable
        ch[prev < 120] = np.nan
        p0 = cols[-12 - months]
    elif transform == "pct":
        prev = data[cols[-1 - months]]
        ch = data[last] / prev - 1
        p0 = cols[-1 - months]
    else:
        ch = data[last] - data[cols[-1 - months]]
        p0 = cols[-1 - months]
    return ch.replace([np.inf, -np.inf], np.nan).dropna(), p0, last


def metro_context() -> dict:
    wide_cache = {}
    signals = []
    for ind, sid in METRO_SOURCE.items():
        m = INDICATORS[ind]
        wide = wide_cache.setdefault(sid, load_zillow_wide(sid))
        size = wide.set_index("RegionID")["SizeRank"]
        for months, label in ((12, "1-year"), (60, "5-year")):
            cols = zillow_date_columns(wide)
            if len(cols) < months + (12 if m["transform"] == "pct_ttm" else 1):
                continue
            ch, p0, p1 = _metro_change(wide, m["transform"], months)
            pit = ch.get(config.PITTSBURGH_MSA_REGION_ID)
            if pit is None or (isinstance(pit, float) and math.isnan(pit)):
                continue
            large = ch[size.reindex(ch.index) <= 100]
            med, scale = robust_center_scale(list(ch.values))
            lmed, lscale = robust_center_scale(list(large.values))
            us_row = wide[wide.RegionID == config.US_REGION_ID]
            signals.append({
                "indicator": ind, "label": m["label"], "short": m["short"], "category": m["category"],
                "window": label, "transform": m["transform"],
                "change": float(pit), "change_kind": "difference" if m["transform"] == "diff" else "percent (fraction)",
                "peer_median": med, "peer_n": int(len(ch)),
                "z_score": float((pit - med) / scale) if scale else 0.0,
                "percentile": percentile_rank(float(pit), list(ch.values)),
                "large_metro_median": lmed, "large_metro_n": int(len(large)),
                "z_score_large_metros": float((pit - lmed) / lscale) if lscale else 0.0,
                "scored": m["scored"],
                "source": config.SOURCES[sid]["name"], "source_id": sid, "source_file": config.SOURCES[sid]["file"],
                "geography": "metro (Pittsburgh MSA, 7 counties)", "period_start": p0, "period_end": p1,
                "time_resolution": m["time_resolution"], "caveats": m["caveats"],
            })
    # forecast (display only)
    fc = load_zillow_wide("zillow_forecast")
    row = fc[fc.RegionID == config.PITTSBURGH_MSA_REGION_ID].iloc[0]
    us = fc[fc.RegionID == config.US_REGION_ID].iloc[0]
    forecast = {
        "base_date": row["BaseDate"],
        "horizons": {c: {"pittsburgh_pct": float(row[c]), "us_pct": float(us[c])} for c in zillow_date_columns(fc)},
        "source": config.SOURCES["zillow_forecast"]["name"], "source_file": config.SOURCES["zillow_forecast"]["file"],
        "note": "Zillow model forecast — a prediction, not an observation. Not used in any Sherlock score.",
    }
    scored5 = [s["z_score"] for s in signals if s["scored"] and s["window"] == "5-year"]
    scored1 = [s["z_score"] for s in signals if s["scored"] and s["window"] == "1-year"]
    s5, l5 = anomaly_level(scored5)
    s1, l1 = anomaly_level(scored1)
    return {"area_id": f"msa-{config.PITTSBURGH_MSA_REGION_ID}", "name": "Pittsburgh, PA metro area",
            "geography_note": "Zillow's Pittsburgh MSA covers 7 counties (Allegheny, Armstrong, Beaver, Butler, Fayette, Washington, Westmoreland). These values do not describe the City or any neighborhood.",
            "signals": signals, "forecast": forecast,
            "anomaly": {"5-year": {"score": s5, "level": l5}, "1-year": {"score": s1, "level": l1}}}


# ---------------------------------------------------------------------------
# Conflicting evidence
# ---------------------------------------------------------------------------
def classify_agreement(a: Optional[float], b: Optional[float], abs_tol: float = 0.03, rel_tol: float = 0.25) -> str:
    """Compare two changes expressed as fractions.

    agree            same direction and |a−b| ≤ max(abs_tol, rel_tol·max(|a|,|b|))
    magnitude        same direction, gap larger than tolerance
    direction        opposite signs, both beyond ±abs_tol
    unknown          either value missing
    """
    if a is None or b is None or (isinstance(a, float) and math.isnan(a)) or (isinstance(b, float) and math.isnan(b)):
        return "unknown"
    small_a, small_b = abs(a) < abs_tol, abs(b) < abs_tol
    if (a > 0) != (b > 0) and not (small_a or small_b):
        return "direction"
    gap = abs(a - b)
    if gap <= max(abs_tol, rel_tol * max(abs(a), abs(b))):
        return "agree"
    return "magnitude"


NATIONAL_PAIRS = [
    {
        "concept": "Home sales", "zillow": "zillow_sales", "zillow_label": "Zillow sales count (nowcast)",
        "redfin": "HOMES SOLD", "redfin_label": "Redfin homes sold",
        "definitional_differences": [
            "Zillow's recent months are nowcast estimates that are later revised; Redfin reports recorded closed sales.",
            "The two providers draw on different listing and public-record coverage.",
        ],
    },
    {
        "concept": "Homes for sale", "zillow": "zillow_inventory", "zillow_label": "Zillow for-sale inventory (smoothed)",
        "redfin": "ACTIVE LISTINGS", "redfin_label": "Redfin active listings",
        "definitional_differences": ["Zillow's series is smoothed; Redfin's is not.",
                                     "Zillow counts unique listings active during the month."],
    },
    {
        "concept": "Home prices", "zillow": "zillow_zhvi_inferred", "zillow_label": "Zillow home value index (inferred ZHVI)",
        "redfin": "MEDIAN SALE PRICE NSA ($)", "redfin_label": "Redfin median sale price (not seasonally adjusted)",
        "definitional_differences": ["An index of typical home values (all homes, smoothed, seasonally adjusted) vs. the median price of homes that actually sold that month.",
                                     "The mix of homes that sell changes month to month; an index tries to hold the mix constant."],
    },
    {
        "concept": "Speed of sale", "zillow": "zillow_days_pending", "zillow_label": "Zillow mean days to pending",
        "redfin": "MEDIAN DAYS ON MARKET (DAYS)", "redfin_label": "Redfin median days on market",
        "definitional_differences": ["Mean vs. median: a few slow-selling homes raise a mean more than a median.",
                                     "Days to pending vs. days on market measure different end points."],
    },
]


def national_conflicts() -> List[dict]:
    rf = load_redfin_national()
    rf.index = rf.index.to_period("M")
    out = []
    for pair in NATIONAL_PAIRS:
        wide = load_zillow_wide(pair["zillow"])
        cols = zillow_date_columns(wide)
        z = wide[wide.RegionID == config.US_REGION_ID][cols].iloc[0].astype(float)
        z.index = pd.to_datetime(z.index).to_period("M")
        r = rf[pair["redfin"]].astype(float)
        common = z.dropna().index.intersection(r.dropna().index)
        if len(common) == 0:
            continue
        end = common.max()
        comparisons = []
        for years in (1, 5):
            start = end - 12 * years
            if start not in common:
                continue
            zc = safe_pct_change(z[end], z[start])
            rc = safe_pct_change(r[end], r[start])
            comparisons.append({
                "window": f"{years}-year", "period_start": str(start), "period_end": str(end),
                "zillow_start": float(z[start]), "zillow_end": float(z[end]), "zillow_change_pct": zc,
                "redfin_start": float(r[start]), "redfin_end": float(r[end]), "redfin_change_pct": rc,
                "agreement": classify_agreement(zc, rc),
            })
        worst = "agree"
        for c in comparisons:
            if c["agreement"] == "direction" or (c["agreement"] == "magnitude" and worst == "agree"):
                worst = c["agreement"]
        agrees, uncertain = [], []
        for c in comparisons:
            same_dir = (c["zillow_change_pct"] or 0) * (c["redfin_change_pct"] or 0) > 0
            if same_dir:
                agrees.append(f"Over the {c['window']} window both sources moved in the same direction ({'up' if c['zillow_change_pct'] > 0 else 'down'}).")
            if c["agreement"] in ("magnitude", "direction"):
                uncertain.append(f"The size of the {c['window']} change: {c['zillow_change_pct']:+.1%} (Zillow) vs {c['redfin_change_pct']:+.1%} (Redfin).")
        out.append({
            "id": f"national-{pair['concept'].lower().replace(' ', '-')}",
            "scope": "national", "geography": "United States (both sources)",
            "concept": pair["concept"],
            "sources": [
                {"label": pair["zillow_label"], "source_id": pair["zillow"], "file": config.SOURCES[pair["zillow"]]["file"]},
                {"label": pair["redfin_label"], "source_id": "redfin_national", "file": config.SOURCES["redfin_national"]["file"]},
            ],
            "comparisons": comparisons, "status": worst,
            "evidence_agrees_on": agrees or ["Nothing: the sources moved in different directions."],
            "remains_uncertain": uncertain or ["No material disagreement at these windows."],
            "possible_reasons": pair["definitional_differences"],
            "reason_basis": "Reasons are taken from the published definitions/column names of each series. They are possible explanations, not verified causes of the gap.",
        })
    return out


def supply_conflict(obs: pd.DataFrame) -> dict:
    """City residential new-construction permits vs metro new-construction sales."""
    values, _, _ = annual_table(obs)
    city = values["city-pittsburgh"]["res_new_construction_permits"]
    B, R = config.BASELINE_YEARS, config.RECENT_YEARS
    cb, cr = _sum_years(city, B), _sum_years(city, R)
    wide = load_zillow_wide("zillow_newcon_sales")
    cols = zillow_date_columns(wide)
    s = wide[wide.RegionID == config.PITTSBURGH_MSA_REGION_ID][cols].iloc[0].astype(float)
    s.index = pd.to_datetime(s.index)
    annual = s.groupby(s.index.year).agg(["sum", "count"])
    full = annual[annual["count"] == 12]["sum"]
    mb = float(full.reindex(B).sum()) if all(y in full.index for y in B) else None
    mr = float(full.reindex(R).sum()) if all(y in full.index for y in R) else None
    cpc, mpc = safe_pct_change(cr, cb), safe_pct_change(mr, mb)
    status = classify_agreement(cpc, mpc)
    return {
        "id": "supply-city-vs-metro", "scope": "city vs metro", "concept": "New housing supply",
        "geography": "City of Pittsburgh (permits) vs. 7-county Pittsburgh metro (Zillow)",
        "sources": [
            {"label": "City residential new-construction permits", "source_id": "pli_permits", "file": config.SOURCES["pli_permits"]["file"],
             "geography": "City of Pittsburgh", "baseline": cb, "recent": cr, "change_pct": cpc},
            {"label": "Zillow new-construction sales", "source_id": "zillow_newcon_sales", "file": config.SOURCES["zillow_newcon_sales"]["file"],
             "geography": "Pittsburgh metro (7 counties)", "baseline": mb, "recent": mr, "change_pct": mpc},
        ],
        "baseline_period": _period_label(B), "recent_period": _period_label(R),
        "status": status,
        "evidence_agrees_on": (["Both measures of new construction declined between the two periods."] if (cpc or 0) < 0 and (mpc or 0) < 0
                               else ["Both measures of new construction increased between the two periods."] if (cpc or 0) > 0 and (mpc or 0) > 0
                               else ["The two measures moved in different directions."]),
        "remains_uncertain": [f"How much new-home activity changed: {cpc:+.1%} (City permits) vs {mpc:+.1%} (metro new-home sales)."] if cpc is not None and mpc is not None else ["One of the two measures is unavailable."],
        "possible_reasons": [
            "Different geography: the City of Pittsburgh vs. a 7-county metro area where most new homes are built outside the City.",
            "Different stage of the pipeline: a permit is issued before construction; a new-construction sale happens after completion, often a year or more later.",
            "Different units: permits do not record dwelling units; sales count homes.",
        ],
        "reason_basis": "Reasons come from dataset definitions and coverage. They are possible explanations, not measured causes.",
    }


def neighborhood_mixed_signals(sig: Dict[str, dict]) -> List[dict]:
    """Within-neighborhood tensions between related measures (same source)."""
    out = []
    alt, val = sig.get("res_alteration_permits"), sig.get(VALUE_INDICATOR)
    new = sig.get("res_new_construction_permits")
    count_dir = None
    counts = [s for s in (alt, new) if s and s["status"] == "scored"]
    if counts and val and val["status"] == "scored":
        cz = sum(s["z_score"] for s in counts)
        vz = val["z_score"]
        if abs(cz) >= 1 and abs(vz) >= 1 and np.sign(cz) != np.sign(vz):
            count_dir = "above" if cz > 0 else "below"
            out.append({
                "id": "count-vs-value", "scope": "within neighborhood", "concept": "Residential building activity",
                "status": "direction",
                "summary": f"Permit counts ran {count_dir} the citywide trend while declared permit value ran {'below' if count_dir == 'above' else 'above'} it.",
                "evidence_agrees_on": ["Residential building activity in this neighborhood departed from the citywide trend."],
                "remains_uncertain": ["Whether activity grew or shrank overall: fewer, larger projects and more, smaller projects produce these opposite readings."],
                "possible_reasons": ["A few large projects can dominate value totals.", "Declared values are applicant estimates."],
                "reason_basis": "Possible explanations based on how the fields are defined.",
            })
    return out


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------
def confidence(sig: Dict[str, dict], total_permits: int, conflicts: List[dict]) -> dict:
    factors = []
    scored = [s for s in sig.values() if s["status"] == "scored"]
    if total_permits < 30:
        factors.append({"severity": "major", "factor": "Few records", "detail": f"Only {total_permits} analysed permits in 2020–2025."})
    elif total_permits < 100:
        factors.append({"severity": "moderate", "factor": "Limited records", "detail": f"{total_permits} analysed permits in 2020–2025; single projects can move the signals."})
    if len(scored) < 2:
        factors.append({"severity": "major", "factor": "Missing indicators", "detail": f"Only {len(scored)} of {len(sig)} indicators had enough data to score."})
    elif len(scored) < len(sig):
        factors.append({"severity": "minor", "factor": "Some indicators missing", "detail": f"{len(scored)} of {len(sig)} indicators had enough data to score."})
    factors.append({"severity": "moderate", "factor": "Single source",
                    "detail": "Every neighborhood time series comes from one dataset (PLI permits). No independent neighborhood-level source (e.g. ACS rent/vacancy, property sales) is loaded to confirm these changes."})
    val = sig.get(VALUE_INDICATOR)
    if val and val.get("largest_recent_permit_share", 0) > 0.5 and val["status"] == "scored":
        factors.append({"severity": "moderate", "factor": "Concentrated value", "detail": f"One permit is {val['largest_recent_permit_share']:.0%} of recent declared value."})
    batches = [s for s in scored if s.get("largest_same_day_batch") and s["recent_value"] and s["largest_same_day_batch"] / s["recent_value"] > 0.5]
    if batches:
        factors.append({"severity": "moderate", "factor": "Concentrated activity",
                        "detail": "; ".join(f"{s['short']}: {s['largest_same_day_batch']} of {int(s['recent_value'])} recent permits issued on one day" for s in batches)})
    if any(c["status"] == "direction" for c in conflicts):
        factors.append({"severity": "moderate", "factor": "Mixed signals", "detail": "Related measures point in different directions."})
    factors.append({"severity": "minor", "factor": "Permit system change", "detail": "The City changed permit systems in 2024; categories were harmonised, but counting practice may differ."})
    factors.append({"severity": "minor", "factor": "Snapshot vacancy proxy", "detail": "City-owned vacant land is a single snapshot and covers only City-owned parcels."})
    majors = sum(f["severity"] == "major" for f in factors)
    mods = sum(f["severity"] == "moderate" for f in factors)
    level = "LOW" if majors or mods >= 3 else ("MODERATE" if mods else "HIGH")
    return {"level": level, "factors": factors,
            "rule": "LOW if any major factor or 3+ moderate factors; MODERATE if 1–2 moderate factors; HIGH only if none. HIGH requires an independent source agreeing, which is not yet loaded."}
