"""Mk2 — ZIP-code market layer.

Combines three independent market sources at ZIP-code level for Allegheny County:
  * Zillow home value index (ZHVI)       -> zip_home_value
  * Zillow observed rent index (ZORI)    -> zip_rent
  * County recorded sales ('VALID SALE') -> zip_sales_count, zip_median_price

Every ZIP is compared with the typical Allegheny County ZIP (or the county
total, for sales). Outputs use the same case-file shape as neighborhoods, so
the UI can show both. All calculations are deterministic.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import config
from .analytics import anomaly_level, classify_agreement, similarity
from .indicators import INDICATORS, ZIP_SCORED
from .narrative import fmt_pct, fmt_value
from .stats import percentile_rank, poisson_residual, robust_z, safe_pct_change

B, R = config.BASELINE_YEARS, config.RECENT_YEARS
COUNTY = "Allegheny County"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_sales(path=None) -> Tuple[pd.DataFrame, dict]:
    path = path or config.RAW / config.SOURCES["county_sales"]["file"]
    df = pd.read_csv(path, dtype={"PARID": str, "PROPERTYZIP": str}, low_memory=False)
    qa = {"rows_raw": int(len(df))}
    df["sale_date"] = pd.to_datetime(df["SALEDATE"], errors="coerce")
    qa["dropped_bad_date"] = int(df.sale_date.isna().sum())
    df = df[df.sale_date.notna()]
    df["year"] = df.sale_date.dt.year
    qa["valid_share_by_year"] = {int(y): round(float(v), 3) for y, v in df.groupby("year")["SALEDESC"].apply(lambda s: (s == "VALID SALE").mean()).items()}
    valid = df[df["SALEDESC"] == "VALID SALE"]
    qa["valid_sales"] = int(len(valid))
    valid = valid[valid.year >= config.SALES_FIRST_COMPARABLE_YEAR]
    qa["valid_sales_2020_on"] = int(len(valid))
    low = valid["PRICE"].isna() | (valid["PRICE"] < config.MIN_SALE_PRICE)
    qa["dropped_nominal_price"] = int(low.sum())
    valid = valid[~low]
    dup = valid.duplicated(["PARID", "SALEDATE", "PRICE"])
    qa["dropped_duplicates"] = int(dup.sum())
    valid = valid[~dup]
    valid = valid.assign(zip=valid["PROPERTYZIP"].astype(str).str[:5])
    bad_zip = ~valid.zip.str.fullmatch(r"\d{5}")
    qa["dropped_bad_zip"] = int(bad_zip.sum())
    valid = valid[~bad_zip]
    qa["rows_analysed"] = int(len(valid))
    qa["last_sale_date"] = str(valid.sale_date.max().date())
    return valid, qa


def load_zillow_zip(source_id: str) -> pd.DataFrame:
    df = pd.read_csv(config.RAW / config.SOURCES[source_id]["file"], dtype={"RegionName": str})
    df = df.set_index("RegionName")
    return df


def _monthly(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if c[:2] == "20" and len(c) == 10]
    m = df[cols].astype(float)
    m.columns = pd.to_datetime(cols)
    return m


def _annual_mean(m: pd.DataFrame, min_months: int = 12) -> Dict[str, Dict[int, Tuple[float, int]]]:
    """zip -> year -> (mean, months present)."""
    out: Dict[str, Dict[int, Tuple[float, int]]] = defaultdict(dict)
    for z, row in m.iterrows():
        s = row.dropna()
        for y, grp in s.groupby(s.index.year):
            out[z][int(y)] = (float(grp.mean()), int(len(grp)))
    return out


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------
def _prov(ind: str, start: str, end: str) -> dict:
    m = INDICATORS[ind]
    s = config.SOURCES[m["source_id"]]
    return {"source": s["name"], "source_id": m["source_id"], "source_file": s["file"], "geography": "zip",
            "period_start": start, "period_end": end, "time_resolution": m["time_resolution"]}


def _base(ind: str, bp: str, rp: str) -> dict:
    m = INDICATORS[ind]
    return {"indicator": ind, "label": m["label"], "short": m["short"], "category": m["category"], "unit": m["unit"],
            "baseline_period": bp, "recent_period": rp, "notes": [], "comparison_label": COUNTY,
            "method": "Log change of this ZIP vs. the typical Allegheny County ZIP (or county total), standardised across ZIPs"}


def build_tables(sales: pd.DataFrame, zips: List[str]) -> dict:
    zhvi = _monthly(load_zillow_zip("zillow_zip_zhvi"))
    zori = _monthly(load_zillow_zip("zillow_zip_zori"))
    t = {
        "zhvi_monthly": zhvi, "zori_monthly": zori,
        "zhvi_annual": _annual_mean(zhvi), "zori_annual": _annual_mean(zori),
        "sales_count": sales.groupby(["zip", "year"]).size(),
        "median_price": sales.groupby(["zip", "year"])["PRICE"].median(),
        "county_sales": sales.groupby("year").size(),
        "county_median": sales.groupby("year")["PRICE"].median(),
    }
    return t


def zip_signals(t: dict, sales: pd.DataFrame, zips: List[str]) -> Dict[str, Dict[str, dict]]:
    out: Dict[str, Dict[str, dict]] = {z: {} for z in zips}
    raw: Dict[str, Dict[str, float]] = defaultdict(dict)
    bp, rp = f"{B[0]}–{B[-1]}", f"{R[0]}–{R[-1]}"

    # --- home values (annual averages, full years only)
    ann = t["zhvi_annual"]
    changes = {}
    for z in zips:
        a = ann.get(z, {})
        if all(y in a and a[y][1] == 12 for y in B + R):
            changes[z] = (np.mean([a[y][0] for y in B]), np.mean([a[y][0] for y in R]))
    typical = float(np.median([r / b - 1 for b, r in changes.values()])) if changes else None
    for z in zips:
        s = {**_base("zip_home_value", bp, rp), **_prov("zip_home_value", f"{B[0]}-01-01", f"{R[-1]}-12-31")}
        s["city_change_pct"] = typical
        s["city_baseline"] = s["city_recent"] = None
        if z in changes:
            b, r = changes[z]
            s.update(baseline_value=b, recent_value=r, change_pct=r / b - 1, status="scored",
                     expected_recent=b * (1 + typical) if typical is not None else None)
            raw["zip_home_value"][z] = math.log(r / b) - math.log(1 + typical)
        else:
            s.update(baseline_value=None, recent_value=None, change_pct=None, expected_recent=None, status="insufficient_data")
            s["notes"].append("Zillow has no complete 2020–2025 home value series for this ZIP.")
        s["notes"].append("Comparison is the median change across Allegheny County ZIPs with data.")
        out[z]["zip_home_value"] = s

    # --- rents (point-to-point window; coverage grows over time)
    zori = t["zori_monthly"]
    d0, d1 = pd.Timestamp(config.RENT_WINDOW[0]), pd.Timestamp(config.RENT_WINDOW[1])
    rch = {}
    for z in zips:
        if z in zori.index and d0 in zori.columns and d1 in zori.columns:
            v0, v1 = zori.at[z, d0], zori.at[z, d1]
            if pd.notna(v0) and pd.notna(v1) and v0 > 0:
                rch[z] = (float(v0), float(v1))
    rtyp = float(np.median([v1 / v0 - 1 for v0, v1 in rch.values()])) if rch else None
    for z in zips:
        s = {**_base("zip_rent", "Aug 2023", "Aug 2026"), **_prov("zip_rent", config.RENT_WINDOW[0], config.RENT_WINDOW[1])}
        s["city_change_pct"] = rtyp
        s["city_baseline"] = s["city_recent"] = None
        if z in rch:
            v0, v1 = rch[z]
            s.update(baseline_value=v0, recent_value=v1, change_pct=v1 / v0 - 1, status="scored",
                     expected_recent=v0 * (1 + rtyp) if rtyp is not None else None)
            raw["zip_rent"][z] = math.log(v1 / v0) - math.log(1 + rtyp)
        else:
            s.update(baseline_value=None, recent_value=None, change_pct=None, expected_recent=None, status="insufficient_data")
            s["notes"].append("Zillow does not publish a rent index for this ZIP for the whole Aug 2023 – Aug 2026 window (too few rental listings).")
        s["notes"].append("Different time window from the other indicators (Aug 2023 → Aug 2026) because rent coverage was thin before 2023.")
        out[z]["zip_rent"] = s

    # --- sales count
    sc, cs = t["sales_count"], t["county_sales"]
    cb, cr = float(sum(cs.get(y, 0) for y in B)), float(sum(cs.get(y, 0) for y in R))
    for z in zips:
        b = float(sum(sc.get((z, y), 0) for y in B))
        r = float(sum(sc.get((z, y), 0) for y in R))
        s = {**_base("zip_sales_count", bp, rp), **_prov("zip_sales_count", f"{B[0]}-01-01", f"{R[-1]}-12-31")}
        s.update(baseline_value=b, recent_value=r, city_baseline=cb, city_recent=cr, city_change_pct=safe_pct_change(cr, cb),
                 expected_recent=b * cr / cb if cb else None)
        s["comparison_label"] = "Allegheny County total"
        if b >= config.MIN_ZIP_SALES_BASE and r > 0:
            s.update(change_pct=r / b - 1, status="scored")
            raw["zip_sales_count"][z] = math.log(r / b) - math.log(cr / cb)
        else:
            s.update(change_pct=None, status="insufficient_data")
            s["notes"].append(f"Too few valid sales to measure change ({int(b)} in the baseline; minimum {config.MIN_ZIP_SALES_BASE}).")
        out[z]["zip_sales_count"] = s

    # --- median price (per period, from individual sales)
    per = sales.assign(period=np.where(sales.year.isin(B), "b", np.where(sales.year.isin(R), "r", "x")))
    med = per[per.period != "x"].groupby(["zip", "period"])["PRICE"].agg(["median", "size"])
    cmed = per[per.period != "x"].groupby("period")["PRICE"].median()
    for z in zips:
        s = {**_base("zip_median_price", bp, rp), **_prov("zip_median_price", f"{B[0]}-01-01", f"{R[-1]}-12-31")}
        s.update(city_baseline=float(cmed["b"]), city_recent=float(cmed["r"]), city_change_pct=float(cmed["r"] / cmed["b"] - 1))
        s["comparison_label"] = "Allegheny County (all valid sales)"
        nb = int(med["size"].get((z, "b"), 0))
        nr = int(med["size"].get((z, "r"), 0))
        s["baseline_n"], s["recent_n"] = nb, nr
        if nb >= config.MIN_ZIP_SALES_FOR_MEDIAN and nr >= config.MIN_ZIP_SALES_FOR_MEDIAN:
            b, r = float(med["median"][(z, "b")]), float(med["median"][(z, "r")])
            s.update(baseline_value=b, recent_value=r, change_pct=r / b - 1, status="scored",
                     expected_recent=b * cmed["r"] / cmed["b"])
            raw["zip_median_price"][z] = math.log(r / b) - math.log(cmed["r"] / cmed["b"])
        else:
            s.update(baseline_value=None, recent_value=None, change_pct=None, expected_recent=None, status="insufficient_data")
            s["notes"].append(f"Too few valid sales for a reliable median ({nb} baseline, {nr} recent; minimum {config.MIN_ZIP_SALES_FOR_MEDIAN} each).")
        out[z]["zip_median_price"] = s

    for ind, stats in raw.items():
        zs = robust_z(stats)
        pop = list(stats.values())
        for z, zval in zs.items():
            s = out[z][ind]
            s.update(residual=stats[z], z_score=float(zval), percentile=percentile_rank(stats[z], pop), n_compared=len(pop),
                     direction="above_city_trend" if stats[z] > 0 else "below_city_trend")
    return out


# ---------------------------------------------------------------------------
# Timeline + onsets
# ---------------------------------------------------------------------------
YEARS = list(range(2020, 2027))


def zip_timelines(t: dict, zips: List[str], last_sale: str) -> Dict[str, dict]:
    ann, rann = t["zhvi_annual"], t["zori_annual"]
    sc, cs, mp, cm = t["sales_count"], t["county_sales"], t["median_price"], t["county_median"]
    # typical ZIP index (median across ZIPs of value / own 2020-21 mean)
    def typical_index(a: dict, base_years) -> Dict[int, float]:
        idx = defaultdict(list)
        for z, yrs in a.items():
            base = [yrs[y][0] for y in base_years if y in yrs]
            if len(base) == len(base_years):
                b = float(np.mean(base))
                for y, (v, _) in yrs.items():
                    idx[y].append(v / b)
        return {y: float(np.median(v)) for y, v in idx.items()}
    hv_idx = typical_index(ann, (2020, 2021))
    rent_idx = typical_index(rann, (2023,))
    out = {}
    for z in zips:
        series, onsets = {}, []

        def level_series(ind, a, idx, base_years, county_vals=None):
            yrs = a.get(z, {})
            base = [yrs[y][0] for y in base_years if y in yrs]
            b = float(np.mean(base)) if len(base) == len(base_years) else None
            rows, onset = [], None
            for y in YEARS:
                v = yrs.get(y)
                val = v[0] if v else None
                exp = b * idx[y] if (b is not None and y in idx) else None
                partial = None if (not v or v[1] == 12) else f"partial_year:{v[1]}_months"
                dev = None
                if val is not None and exp and y >= base_years[-1] + 1 and y <= 2025 and not partial:
                    dev = val / exp - 1
                    if onset is None and abs(dev) >= 0.05:
                        onset = (y, "up" if dev > 0 else "down", dev)
                rows.append({"year": y, "value": val, "city_value": county_vals.get(y) if county_vals else None,
                             "expected_from_2020_21_share": exp, "deviation": dev, "partial": partial})
            return rows, onset

        rows, on = level_series("zip_home_value", ann, hv_idx, (2020, 2021))
        series["zip_home_value"] = rows
        onsets.append(("zip_home_value", on))
        rows, on = level_series("zip_rent", rann, rent_idx, (2023,))
        series["zip_rent"] = rows
        onsets.append(("zip_rent", on))

        # sales count: share of county activity in 2020–21
        cb = float(sum(cs.get(y, 0) for y in (2020, 2021)))
        zb = float(sum(sc.get((z, y), 0) for y in (2020, 2021)))
        share = zb / cb if cb else None
        rows, onset = [], None
        for y in YEARS:
            v = float(sc.get((z, y), 0))
            cv = float(cs.get(y, 0))
            exp = share * cv if share is not None else None
            partial = f"partial_year:ends_{last_sale}" if y == int(last_sale[:4]) else None
            dev = None
            if exp is not None and 2022 <= y <= 2025:
                dev = poisson_residual(v, exp)
                if onset is None and abs(dev) >= 2 and max(v, exp) >= 3:
                    onset = (y, "up" if dev > 0 else "down", dev)
            rows.append({"year": y, "value": v, "city_value": cv, "expected_from_2020_21_share": exp, "deviation": dev, "partial": partial})
        series["zip_sales_count"] = rows
        onsets.append(("zip_sales_count", onset))

        # median price: follow county median index from the ZIP's 2020–21 level
        base = [mp.get((z, y)) for y in (2020, 2021)]
        b = float(np.mean(base)) if all(v is not None and not pd.isna(v) for v in base) else None
        cbase = float(np.mean([cm.get(2020), cm.get(2021)]))
        rows, onset = [], None
        for y in YEARS:
            v = mp.get((z, y))
            v = float(v) if v is not None and not pd.isna(v) else None
            n = int(sc.get((z, y), 0))
            exp = b * float(cm.get(y)) / cbase if (b is not None and y in cm.index) else None
            partial = f"partial_year:ends_{last_sale}" if y == int(last_sale[:4]) else None
            dev = None
            if v is not None and exp and 2022 <= y <= 2025 and n >= 10:
                dev = v / exp - 1
                if onset is None and abs(dev) >= 0.10:
                    onset = (y, "up" if dev > 0 else "down", dev)
            rows.append({"year": y, "value": v, "city_value": float(cm.get(y)) if y in cm.index else None,
                         "expected_from_2020_21_share": exp, "deviation": dev, "partial": partial})
        series["zip_median_price"] = rows
        onsets.append(("zip_median_price", onset))

        ordered, none = [], []
        for ind, on in onsets:
            m = INDICATORS[ind]
            if on:
                y, d, dev = on
                ordered.append({"indicator": ind, "label": m["label"], "short": m["short"], "year": y, "direction": d, "deviation": dev,
                                "statement": f"{m['short']} first moved {'above' if d == 'up' else 'below'} the path of the typical Allegheny County ZIP in {y}."})
            else:
                none.append({"indicator": ind, "label": m["label"], "short": m["short"], "year": None, "direction": None,
                             "statement": f"{m['short']}: no clear departure from the typical county path in 2022–2025."})
        ordered.sort(key=lambda o: (o["year"], -abs(o["deviation"])))
        rank, last = 0, None
        for o in ordered:
            if o["year"] != last:
                rank += 1
                last = o["year"]
            o["order"] = rank
        out[z] = {"series": series, "what_changed_first": {
            "ordered": ordered, "no_clear_change": none,
            "method": ("Each year 2022–2025 is compared with the path the ZIP would have followed if it had changed like the typical "
                       "Allegheny County ZIP since 2020–21 (2023 for rents). Home values and rents depart at ±5%, median prices at ±10% "
                       "(with at least 10 sales), sales counts at (obs − exp)/√(exp+1) = ±2."),
            "caution": "Order of change does not establish causation. An earlier change did not necessarily cause a later one.",
        }}
    return out


# ---------------------------------------------------------------------------
# Conflicts, confidence, text
# ---------------------------------------------------------------------------
def price_conflict(sig: Dict[str, dict], label: str) -> Optional[dict]:
    hv, mp = sig["zip_home_value"], sig["zip_median_price"]
    if hv["status"] != "scored" or mp["status"] != "scored":
        return None
    a, b = hv["change_pct"], mp["change_pct"]
    status = classify_agreement(a, b)
    same = (a > 0) == (b > 0)
    return {
        "id": f"price-{label}", "scope": label, "concept": "Home prices",
        "sources": [
            {"label": "Zillow home value index (ZHVI)", "source_id": "zillow_zip_zhvi", "file": config.SOURCES["zillow_zip_zhvi"]["file"],
             "geography": "ZIP code", "baseline": hv["baseline_value"], "recent": hv["recent_value"], "change_pct": a},
            {"label": "County median sale price", "source_id": "county_sales", "file": config.SOURCES["county_sales"]["file"],
             "geography": "ZIP code", "baseline": mp["baseline_value"], "recent": mp["recent_value"], "change_pct": b},
        ],
        "baseline_period": hv["baseline_period"], "recent_period": hv["recent_period"], "status": status,
        "evidence_agrees_on": [f"Both sources show home prices {'rising' if a > 0 else 'falling'}."] if same else ["Nothing: the two sources moved in different directions."],
        "remains_uncertain": [f"How much prices changed: {fmt_pct(a)} (Zillow index) vs {fmt_pct(b)} (median of recorded sales)."] if status != "agree" else ["No material disagreement."],
        "possible_reasons": [
            "Zillow's index estimates the value of all typical homes; the County median reflects only the homes that happened to sell, so it moves when the mix of sold homes changes.",
            "The sales file includes all property types; Zillow's index covers single-family homes and condos.",
            "Zillow's series is smoothed and seasonally adjusted.",
        ],
        "reason_basis": "Reasons come from how each dataset is defined. They are possible explanations, not verified causes.",
    }


def zip_confidence(sig: Dict[str, dict], total_sales: int, conflict: Optional[dict]) -> dict:
    f = []
    scored = [s for s in sig.values() if s["status"] == "scored"]
    if total_sales < 60:
        f.append({"severity": "major", "factor": "Few sales", "detail": f"Only {total_sales} valid sales in 2020–2025."})
    elif total_sales < 200:
        f.append({"severity": "moderate", "factor": "Limited sales", "detail": f"{total_sales} valid sales in 2020–2025; medians can move a lot."})
    if len(scored) < 2:
        f.append({"severity": "major", "factor": "Missing indicators", "detail": f"Only {len(scored)} of {len(sig)} indicators could be measured."})
    elif len(scored) < len(sig):
        missing = ", ".join(s["short"].lower() for s in sig.values() if s["status"] != "scored")
        f.append({"severity": "minor", "factor": "Some indicators missing", "detail": f"Not measurable here: {missing}."})
    if conflict and conflict["status"] == "direction":
        f.append({"severity": "moderate", "factor": "Sources disagree", "detail": "Zillow's index and County sale prices moved in opposite directions."})
    elif conflict and conflict["status"] == "magnitude":
        f.append({"severity": "minor", "factor": "Sources differ in size", "detail": "Zillow's index and County sale prices agree on direction but not on size."})
    f.append({"severity": "minor", "factor": "Approximate ZIP boundary", "detail": "ZIP areas are built from 2010 Census blocks; only the Allegheny County part of a ZIP is included."})
    f.append({"severity": "minor", "factor": "Mixed property types", "detail": "County sales include all property types (no property-class field)."})
    majors = sum(x["severity"] == "major" for x in f)
    mods = sum(x["severity"] == "moderate" for x in f)
    level = "LOW" if majors or mods >= 3 else ("MODERATE" if mods else "HIGH")
    return {"level": level, "factors": f,
            "rule": "LOW if any major factor or 3+ moderate factors; MODERATE if 1–2 moderate factors; HIGH if none. ZIP evidence can reach HIGH because two independent sources (Zillow and County records) are compared."}


ZIP_TITLES = {
    ("zip_home_value", "up"): "The Case of the Soaring Home Values",
    ("zip_home_value", "down"): "The Case of the Lagging Home Values",
    ("zip_rent", "up"): "The Case of the Rising Rents",
    ("zip_rent", "down"): "The Case of the Cooling Rents",
    ("zip_sales_count", "up"): "The Case of the Busy Market",
    ("zip_sales_count", "down"): "The Case of the Quiet Market",
    ("zip_median_price", "up"): "The Case of the Climbing Sale Prices",
    ("zip_median_price", "down"): "The Case of the Slipping Sale Prices",
}
PLAIN_ZIP = {
    "zip_home_value": "home values (Zillow estimate)",
    "zip_rent": "asking rents",
    "zip_sales_count": "home sales",
    "zip_median_price": "the typical sale price",
}
PLAIN_ZIP_HEADLINE = {
    ("zip_home_value", "up"): "home values grew faster than in most of Allegheny County",
    ("zip_home_value", "down"): "home values grew more slowly than in most of Allegheny County",
    ("zip_rent", "up"): "asking rents rose faster than in most of Allegheny County",
    ("zip_rent", "down"): "asking rents rose more slowly than in most of Allegheny County",
    ("zip_sales_count", "up"): "home sales held up better than across the county",
    ("zip_sales_count", "down"): "home sales fell more than across the county",
    ("zip_median_price", "up"): "sale prices climbed faster than across the county",
    ("zip_median_price", "down"): "sale prices climbed more slowly than across the county",
}


def _v(ind, x):
    return fmt_value(ind, x) if ind != "zip_rent" else (f"${x:,.0f}/mo" if x is not None else "n/a")


def zip_sentence(s: dict) -> str:
    ind = s["indicator"]
    return (f"{s['label']}: {_v(ind, s['baseline_value'])} ({s['baseline_period']}) → {_v(ind, s['recent_value'])} ({s['recent_period']}), "
            f"{fmt_pct(s['change_pct'])}; typical for {COUNTY}: {fmt_pct(s['city_change_pct'])}.")


def zip_finding(case: dict) -> str:
    sigs = [s for s in case["evidence"]["signals"] if s["status"] == "scored"]
    strong = sorted([s for s in sigs if abs(s["z_score"]) >= 1], key=lambda s: -abs(s["z_score"]))
    p = []
    if strong:
        p.append(f"{len(strong)} of {len(sigs)} measured market indicators in {case['name']} moved noticeably differently from the typical {COUNTY} ZIP.")
        p.append(" ".join(zip_sentence(s) for s in strong[:3]))
    else:
        p.append(f"The housing market in {case['name']} broadly tracked the rest of {COUNTY}.")
    conf = case["conflicting_evidence"]["neighborhood"]
    if conf:
        c = conf[0]
        p.append(("Zillow's home value index and County sale prices agree on the direction of price change."
                  if c["status"] in ("agree", "magnitude") else
                  "Zillow's home value index and County sale prices point in different directions, so the price trend here is uncertain.")
                 + (" They differ on how large it was." if c["status"] == "magnitude" else ""))
    p.append("The available evidence does not establish why these changes happened or who was affected: "
             "no income, population or tenure data is loaded, and ZIP codes do not match neighborhood boundaries.")
    return "\n\n".join(p)


def zip_plain(case: dict) -> dict:
    sigs = [s for s in case["evidence"]["signals"] if s["status"] == "scored"]
    strong = sorted([s for s in sigs if abs(s["z_score"]) >= 1], key=lambda s: -abs(s["z_score"]))
    name = case["name"]
    if strong:
        top = strong[0]
        headline = f"In {name}, {PLAIN_ZIP_HEADLINE[(top['indicator'], 'up' if top['z_score'] > 0 else 'down')]}."
    elif case["level"] == "INSUFFICIENT DATA":
        headline = f"There isn't enough market data for {name} to spot a clear pattern."
    else:
        headline = f"The housing market in {name} has moved much like the rest of {COUNTY}."
    bullets = []
    for s in strong[:3]:
        ind = s["indicator"]
        bullets.append(f"In {name}, {PLAIN_ZIP[ind]} went from {_v(ind, s['baseline_value'])} ({s['baseline_period']}) to "
                       f"{_v(ind, s['recent_value'])} ({s['recent_period']}). The typical change across {COUNTY} was {fmt_pct(s['city_change_pct'])}.")
    conf = case["confidence"]["level"]
    text = {"HIGH": "High — Zillow and County sales records agree.",
            "MODERATE": "Medium — treat this as a lead rather than a conclusion.",
            "LOW": "Low — there are few sales here or the sources disagree."}[conf]
    similar = [s["name"] for s in case.get("similar_cases", [])[:3]]
    return {
        "level_label": {"HIGH": "Very unusual", "MEDIUM": "Somewhat unusual", "LOW": "About typical", "INSUFFICIENT DATA": "Not enough data"}[case["level"]],
        "headline": headline, "bullets": bullets, "timing": None, "confidence": text,
        "keep_in_mind": [
            "ZIP codes don't line up with neighborhood borders.",
            "Rents are asking rents for listed homes, not what current tenants pay.",
            "Unusual doesn't mean good or bad — it means different from the rest of the county.",
        ],
        "similar": similar,
        "similar_text": (f"ZIP codes with a similar pattern: {', '.join(similar)}." if similar else None),
    }


def zip_limitations(case: dict) -> List[str]:
    out = [
        "No dataset in this analysis establishes causal relationships.",
        "ZIP codes are mail-delivery areas; they do not match neighborhood or municipal boundaries. ZIP areas here are built from 2010 Census blocks and include only the Allegheny County part.",
        "Zillow rents are asking rents for listed homes, not rents paid by current tenants. Rent changes cover Aug 2023 → Aug 2026, a different window from the other indicators.",
        "County sales use only transfers coded 'VALID SALE'. Coding practice changed in 2020, so earlier years are not used.",
        "The sales file has no property-type field, so medians can include non-residential sales.",
        "No income, population, household or vacancy-rate data is loaded, so affordability for residents cannot be assessed.",
    ]
    for s in case["evidence"]["signals"]:
        if s["status"] != "scored":
            out.append(f"{s['label']}: UNKNOWN — not enough data.")
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def build(neighborhood_names: Dict[str, str], national_conflicts: List[dict], metro_signals: List[dict]) -> dict:
    import json
    geo = json.load(open(config.PROCESSED / "zips.geojson"))
    zips_poly = sorted(f["properties"]["zip"] for f in geo["features"])
    sales, qa = load_sales()
    zhvi_idx = set(load_zillow_zip("zillow_zip_zhvi").index)
    sales_zips = set(sales.zip.unique())
    zips = [z for z in zips_poly if z in zhvi_idx or z in sales_zips]
    city_of = load_zillow_zip("zillow_zip_zhvi")["City"].to_dict()
    names = {z: f"ZIP {z}" + (f" ({city_of[z]})" if city_of.get(z) else "") for z in zips}
    t = build_tables(sales, zips)
    sig = zip_signals(t, sales, zips)
    tl = zip_timelines(t, zips, qa["last_sale_date"])
    sim = similarity(sig, names, {}, features=ZIP_SCORED)
    for lst in sim.values():
        for item in lst:
            item["area_id"] = f"zip-{item['area_id']}"

    # neighborhoods overlapping each ZIP
    xw = pd.read_csv(config.PROCESSED / "neighborhood_zip_crosswalk.csv", dtype={"zip": str})
    total_sales = sales[sales.year.between(config.PERMIT_FIRST_FULL_YEAR, config.PERMIT_LAST_FULL_YEAR)].groupby("zip").size()

    cases, areas = [], []
    for z in zips:
        s = sig[z]
        zs = [x["z_score"] for x in s.values() if x["status"] == "scored"]
        score, level = anomaly_level(zs)
        conflict = price_conflict(s, "this ZIP code")
        conf = zip_confidence(s, int(total_sales.get(z, 0)), conflict)
        ranked = sorted([x for x in s.values() if x["status"] == "scored"], key=lambda x: -abs(x["z_score"]))
        nb = xw[xw.zip == z].sort_values("share_of_zip_land", ascending=False)
        case = {
            "area_id": f"zip-{z}", "zip": z, "name": names[z], "geography": "zip", "comparison_label": COUNTY,
            "geography_note": "ZIP code (approximate area built from 2010 Census blocks; Allegheny County part only). Compared with the typical Allegheny County ZIP.",
            "anomaly_score": score, "level": level, "max_abs_z": max((abs(v) for v in zs), default=None),
            "title": ZIP_TITLES[(ranked[0]["indicator"], "up" if ranked[0]["z_score"] > 0 else "down")] if ranked else "Insufficient evidence",
            "permit_last_date": qa["last_sale_date"],
            "timeline_expected_label": "If it had changed like the typical county ZIP",
            "why_noticed": [{
                "indicator": x["indicator"], "label": x["label"], "short": x["short"],
                "headline": f"{x['short']} {fmt_pct(x['change_pct'])} vs. county {fmt_pct(x['city_change_pct'])}",
                "change_pct": x["change_pct"], "city_change_pct": x["city_change_pct"],
                "baseline_value": x["baseline_value"], "recent_value": x["recent_value"], "expected_recent": x.get("expected_recent"),
                "z_score": x["z_score"], "percentile": x.get("percentile"), "direction": x.get("direction"),
                "source": x["source"], "geography": "zip", "period": f"{x['baseline_period']} vs {x['recent_period']}",
            } for x in ranked if abs(x["z_score"]) >= 1],
            "evidence": {"signals": [s[i] for i in ZIP_SCORED], "context": {
                "neighborhoods": [{"neighborhood": r.neighborhood, "area_id": r.neighborhood_id, "share_of_zip_land": float(r.share_of_zip_land)}
                                  for r in nb.itertuples() if r.share_of_zip_land >= 0.02],
                "metro": {"note": "Regional context, not a ZIP measurement.", "signals": metro_signals},
            }},
            "timeline": tl[z]["series"], "what_changed_first": tl[z]["what_changed_first"],
            "similar_cases": sim.get(z, []),
            "conflicting_evidence": {"neighborhood": [conflict] if conflict else [], "citywide_and_regional": [], "national": national_conflicts,
                                     "note": "At ZIP level Sherlock compares two independent price sources: Zillow's home value index and County recorded sale prices."},
            "confidence": conf,
        }
        case["finding"] = {"text": zip_finding(case), "generated_by": "deterministic template", "llm_status": "not requested"}
        case["limitations"] = zip_limitations(case)
        case["plain"] = zip_plain(case)
        cases.append(case)
        areas.append({"id": f"zip-{z}", "zip": z, "name": names[z], "geography": "zip", "anomaly_score": score, "level": level,
                      "confidence": conf["level"], "top_signal": ranked[0]["short"] if ranked else None,
                      "top_signal_headline": case["why_noticed"][0]["headline"] if case["why_noticed"] else None, "case_id": None})

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INSUFFICIENT DATA": 3}
    cases.sort(key=lambda c: (order[c["level"]], -(c["anomaly_score"] or 0)))
    by = {a["id"]: a for a in areas}
    n = 0
    for c in cases:
        if c["level"] in ("HIGH", "MEDIUM"):
            n += 1
            c["case_number"] = n
            c["case_label"] = f"Z-{n:03d}"
            c["id"] = f"zcase-{n:03d}"
        else:
            c["case_number"] = None
            c["case_label"] = None
            c["id"] = f"zipfile-{c['zip']}"
        by[c["area_id"]]["case_id"] = c["id"]
    return {"cases": cases, "areas": areas, "signals": sig, "qa": qa, "names": names}


def neighborhood_market_context(nid: str, zip_result: dict) -> dict:
    """ZIP-level market evidence for a neighborhood (clearly labelled as ZIP level)."""
    xw = pd.read_csv(config.PROCESSED / "neighborhood_zip_crosswalk.csv", dtype={"zip": str})
    rows = xw[(xw.neighborhood_id == nid)].sort_values("share_of_neighborhood_land", ascending=False)
    by_zip = {c["zip"]: c for c in zip_result["cases"]}
    items = []
    for r in rows.itertuples():
        if r.share_of_neighborhood_land < 0.10 or r.zip not in by_zip:
            continue
        c = by_zip[r.zip]
        items.append({
            "zip": r.zip, "name": c["name"], "case_id": c["id"], "level": c["level"],
            "share_of_neighborhood_land": float(r.share_of_neighborhood_land),
            "share_of_zip_land": float(r.share_of_zip_land),
            "signals": [{k: s.get(k) for k in ("indicator", "label", "short", "unit", "status", "change_pct", "city_change_pct", "z_score",
                                                "baseline_value", "recent_value", "baseline_period", "recent_period", "source")}
                        for s in c["evidence"]["signals"]],
            "price_conflict": c["conflicting_evidence"]["neighborhood"][0] if c["conflicting_evidence"]["neighborhood"] else None,
        })
    plain = None
    if items:
        d = items[0]
        parts = []
        for s in d["signals"]:
            if s["status"] == "scored" and s["indicator"] in ("zip_home_value", "zip_rent"):
                what = "Home values" if s["indicator"] == "zip_home_value" else "Asking rents"
                parts.append(f"{what} {('rose' if s['change_pct'] > 0 else 'fell')} {abs(s['change_pct']) * 100:.0f}% "
                             f"({s['baseline_period']} to {s['recent_period']}; typical county ZIP: {fmt_pct(s['city_change_pct'])})")
        if parts:
            plain = (f"In ZIP {d['zip']}, which covers about {d['share_of_neighborhood_land'] * 100:.0f}% of this neighborhood: "
                     + "; ".join(parts) + ".")
    return {"note": "ZIP-code level evidence. ZIP codes do not match neighborhood boundaries; shares show how much of the neighborhood's land each ZIP covers.",
            "zips": items, "plain": plain}
