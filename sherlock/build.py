"""Run the full Sherlock pipeline:  python -m sherlock.build

RAW DATA → geography → normalization → trends → anomaly detection →
cross-dataset evidence → confidence → structured case files → text.

Writes everything the API/UI needs into data/processed/.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import analytics as A
from . import build_geography, config, normalize, zipmarket
from .indicators import INDICATORS, NEIGHBORHOOD_SCORED
from .narrative import case_title, finding, limitations, plain_summary, signal_headline
from .stats import robust_z


def _clean(o):
    """Make objects JSON-safe (NaN → None, numpy → python)."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()
    return o


def _write(name: str, obj) -> None:
    with open(config.PROCESSED / name, "w") as f:
        json.dump(_clean(obj), f, indent=None if name == "cases.json" else 1, separators=(",", ":") if name == "cases.json" else None, default=str)


def run(verbose: bool = True) -> dict:
    t0 = time.time()
    log = print if verbose else (lambda *a, **k: None)
    log("[1/6] Geography: dissolving 2010 Census blocks → neighborhoods & tracts")
    from . import prepare_extracts
    if (config.RAW / "original").exists() and any((config.RAW / "original").iterdir()):
        log("[0] Preparing slim extracts from data/raw/original/")
        prepare_extracts.run()
    blocks = config.RAW / "blockcodes2016.zip"
    if blocks.exists():
        build_geography.build(verbose=verbose)
    elif (config.PROCESSED / "neighborhoods.geojson").exists():
        log("  blockcodes2016.zip not in data/raw — reusing existing data/processed/neighborhoods.geojson")
    else:
        raise FileNotFoundError("data/raw/blockcodes2016.zip is required to build neighborhood boundaries.")
    geo = json.load(open(config.PROCESSED / "neighborhoods.geojson"))
    names = {f["properties"]["id"]: f["properties"]["name"] for f in geo["features"]}
    land = {f["properties"]["id"]: f["properties"]["land_area_km2"] for f in geo["features"]}

    log("[2/6] Ingest + normalize (with provenance)")
    obs, permits, inv, qa = normalize.build(names, land)
    obs.to_csv(config.PROCESSED / "observations.csv", index=False)
    permit_last = str(permits.issue_date.max().date())

    log("[3/6] Trends + anomaly signals")
    signals = A.neighborhood_signals(obs, permits, names)
    tl = A.timelines(obs, names, signals)

    # vacancy context (snapshot, level only)
    vac = obs[obs.indicator == "city_owned_vacant_lots_per_km2"].set_index("area_id")["value"]
    vac_n = obs[obs.indicator == "city_owned_vacant_lots"].set_index("area_id")["value"]
    vac_z = robust_z({nid: float(vac.get(nid)) for nid in names if vac.get(nid) is not None})
    snapshot = qa["inventory"]["snapshot_last_updated_max"]

    log("[4/6] Similarity, conflicts, metro context")
    sim = A.similarity(signals, names, vac_z)
    national = A.national_conflicts()
    supply = A.supply_conflict(obs)
    metro = A.metro_context()

    log("[5/6] Scores, confidence, case files")
    total_permits = (permits[permits.year.between(config.PERMIT_FIRST_FULL_YEAR, config.PERMIT_LAST_FULL_YEAR)]
                     .groupby("neighborhood_id").size())
    areas, cases = [], []
    for nid, name in names.items():
        sig = signals[nid]
        zs = [s["z_score"] for s in sig.values() if s["status"] == "scored"]
        score, level = A.anomaly_level(zs)
        mixed = A.neighborhood_mixed_signals(sig)
        conf = A.confidence(sig, int(total_permits.get(nid, 0)), mixed)
        ranked = sorted([s for s in sig.values() if s["status"] == "scored"], key=lambda s: -abs(s["z_score"]))
        area = {
            "id": nid, "name": name, "geography": "neighborhood",
            "anomaly_score": score, "level": level,
            "max_abs_z": max((abs(z) for z in zs), default=None),
            "signals_scored": len(zs), "confidence": conf["level"],
            "top_signal": ranked[0]["short"] if ranked else None,
            "top_signal_headline": signal_headline(ranked[0]) if ranked else None,
            "top_signal_direction": ("above" if ranked[0]["z_score"] > 0 else "below") if ranked else None,
            "land_area_km2": land.get(nid),
            "case_id": None,
        }
        areas.append(area)
        case = {
            "area_id": nid, "name": name, "geography": "neighborhood",
            "geography_note": "City of Pittsburgh neighborhood (boundaries dissolved from 2010 Census blocks).",
            "anomaly_score": score, "level": level, "max_abs_z": area["max_abs_z"],
            "title": case_title(ranked[0]) if ranked else "Insufficient evidence",
            "permit_last_date": permit_last,
            "why_noticed": [{
                "indicator": s["indicator"], "label": s["label"], "short": s["short"], "headline": signal_headline(s),
                "change_pct": s.get("change_pct"), "city_change_pct": s.get("city_change_pct"),
                "baseline_value": s["baseline_value"], "recent_value": s["recent_value"],
                "expected_recent": s.get("expected_recent"),
                "z_score": s["z_score"], "percentile": s.get("percentile"), "direction": s.get("direction"),
                "source": s["source"], "geography": s["geography"],
                "period": f"{s['baseline_period']} vs {s['recent_period']}",
            } for s in ranked if abs(s["z_score"]) >= 1.0] or [],
            "evidence": {
                "signals": [sig[i] for i in NEIGHBORHOOD_SCORED],
                "context": {
                    "city_owned_vacant_lots": {
                        "value": vac_n.get(nid), "per_km2": vac.get(nid), "z_vs_neighborhoods": vac_z.get(nid),
                        "city_per_km2": vac.get("city-pittsburgh"), "snapshot": snapshot,
                        "source": config.SOURCES["city_inventory"]["name"], "source_file": config.SOURCES["city_inventory"]["file"],
                        "geography": "neighborhood", "time_resolution": "snapshot",
                        "caveats": INDICATORS["city_owned_vacant_lots"]["caveats"],
                    },
                    "metro": {
                        "note": "Regional context, not a neighborhood measurement.",
                        "signals": [m for m in metro["signals"] if m["window"] == "5-year"],
                    },
                },
            },
            "timeline": tl[nid]["series"],
            "what_changed_first": tl[nid]["what_changed_first"],
            "similar_cases": sim[nid],
            "conflicting_evidence": {
                "neighborhood": mixed,
                "citywide_and_regional": [supply],
                "national": national,
                "note": ("No second neighborhood-level dataset measures the same concepts as the permit file, so direct "
                         "neighborhood-level conflicts can only be checked between related permit measures. City-vs-metro "
                         "and national cross-source checks are shown for context."),
            },
            "confidence": conf,
        }
        case["finding"] = {"text": finding(case), "generated_by": "deterministic template",
                           "llm_status": "not requested (use /cases/{id}/explain)"}
        case["limitations"] = limitations(case)
        case["plain"] = plain_summary(case)
        cases.append(case)

    # Mk2: ZIP-code market layer (Zillow home values + rents, County sales)
    log("[5b] ZIP market layer: Zillow ZHVI/ZORI + County sales")
    zres = zipmarket.build(names, national, [m for m in metro["signals"] if m["window"] == "5-year"])
    for case in cases:
        mk = zipmarket.neighborhood_market_context(case["area_id"], zres)
        case["evidence"]["context"]["zip_market"] = mk
        case["plain"]["market"] = mk["plain"]
        if mk["zips"] and mk["zips"][0]["price_conflict"]:
            pc = dict(mk["zips"][0]["price_conflict"])
            pc["id"] = f"price-zip-{mk['zips'][0]['zip']}"
            pc["scope"] = f"ZIP {mk['zips'][0]['zip']} (about {mk['zips'][0]['share_of_neighborhood_land'] * 100:.0f}% of this neighborhood)"
            case["conflicting_evidence"]["citywide_and_regional"].append(pc)
        case["comparison_label"] = "City of Pittsburgh"
    # Optional Census ACS tract evidence (only if data/raw/acs/acs_<year>.json files exist)
    from . import acs
    acs_data = acs.neighborhood_acs(acs.load_all())
    for case in cases:
        case["evidence"]["context"]["acs"] = acs_data.get(case["area_id"])

    # number the cases: HIGH then MEDIUM, by score
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INSUFFICIENT DATA": 3}
    cases.sort(key=lambda c: (order[c["level"]], -(c["anomaly_score"] or 0)))
    area_by_id = {a["id"]: a for a in areas}
    n = 0
    for c in cases:
        if c["level"] in ("HIGH", "MEDIUM"):
            n += 1
            c["case_number"] = n
            c["case_label"] = f"{n:03d}"
            c["id"] = f"case-{n:03d}"
        else:
            c["case_number"] = None
            c["case_label"] = None
            c["id"] = f"file-{c['area_id']}"
        area_by_id[c["area_id"]]["case_id"] = c["id"]

    # metro case
    metro_case = {**metro, "id": "case-metro", "title": "The Regional Backdrop",
                  "limitations": [
                      "Metro values cover 7 counties and say nothing about individual neighborhoods.",
                      "The home value file's name is a UUID; it was identified as Zillow ZHVI by structure and values.",
                      "Sales counts for recent months are Zillow nowcasts and may be revised.",
                      "Income needed to buy is modeled from prices and mortgage rates, not measured incomes.",
                      "The forecast is a Zillow model prediction and is never used in scoring.",
                  ]}

    log("[6/6] Writing outputs")
    _write("areas.json", sorted(areas, key=lambda a: a["name"]))
    _write("cases.json", cases)
    _write("zip_areas.json", sorted(zres["areas"], key=lambda a: a["zip"]))
    _write("zip_cases.json", zres["cases"])
    _write("metro.json", metro_case)
    _write("conflicts.json", {"national": national, "citywide_and_regional": [supply]})
    _write("indicators.json", {k: {"id": k, **v} for k, v in INDICATORS.items()})
    _write("sources.json", config.SOURCES)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "areas": len(areas),
        "cases_worth_investigating": sum(1 for c in cases if c["case_number"]),
        "levels": {lvl: sum(1 for a in areas if a["level"] == lvl) for lvl in order},
        "confidence": {lvl: sum(1 for a in areas if a["confidence"] == lvl) for lvl in ("HIGH", "MODERATE", "LOW")},
        "baseline_years": list(config.BASELINE_YEARS), "recent_years": list(config.RECENT_YEARS),
        "permit_last_date": permit_last,
        "city_trends": {i: {"baseline": signals[next(iter(names))][i]["city_baseline"],
                            "recent": signals[next(iter(names))][i]["city_recent"],
                            "change_pct": signals[next(iter(names))][i]["city_change_pct"]} for i in NEIGHBORHOOD_SCORED},
        "zip": {
            "areas": len(zres["areas"]),
            "cases_worth_investigating": sum(1 for c in zres["cases"] if c["case_number"]),
            "levels": {lvl: sum(1 for a in zres["areas"] if a["level"] == lvl) for lvl in order},
            "last_sale_date": zres["qa"]["last_sale_date"],
        },
        "qa": {**qa, "county_sales": zres["qa"]},
        "seconds": round(time.time() - t0, 1),
    }
    _write("summary.json", summary)
    export_static(log)
    log(f"Done in {summary['seconds']}s — {summary['cases_worth_investigating']} neighborhood cases, "
        f"{summary['zip']['cases_worth_investigating']} ZIP cases; levels {summary['levels']} / ZIP {summary['zip']['levels']}")
    return summary


def export_static(log=print) -> None:
    """Copy what the web app needs into web/public/data for offline/demo mode."""
    from .service import Store
    out = config.ROOT / "web" / "public" / "data"
    out.mkdir(parents=True, exist_ok=True)
    st = Store()
    files = {
        "summary_home.json": st.home(), "areas.json": st.areas, "cases.json": st.cases,
        "metro.json": st.metro, "neighborhoods.geojson": st.neighborhoods_geojson,
        "zip_cases.json": st.zip_cases, "zips.geojson": st.zips_geojson,
    }
    for name, obj in files.items():
        with open(out / name, "w") as f:
            json.dump(obj, f, separators=(",", ":"))
    log(f"  exported static demo data → {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    run()
