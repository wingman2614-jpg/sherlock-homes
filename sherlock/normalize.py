"""Step 3 — build the normalized observation table.

One row = one value of one indicator for one area and one period, with its
full provenance. Original temporal resolution is preserved in
`time_resolution`; partial periods are flagged, never silently annualised.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from . import config
from .indicators import INDICATORS
from .ingest import load_inventory, load_permits, load_redfin_national, load_zillow_wide, zillow_series

OBS_COLUMNS = [
    "area_id", "area_name", "geography", "indicator", "period_start", "period_end",
    "time_resolution", "value", "unit", "n_records", "source_id", "source_file", "flags",
]

PERMIT_LAST_DATE = None  # filled at runtime from data


def _obs(area_id, area_name, geography, indicator, start, end, value, n=None, flags="", source_id=None, time_resolution=None):
    m = INDICATORS.get(indicator, {})
    sid = source_id or m.get("source_id")
    return {
        "area_id": area_id, "area_name": area_name, "geography": geography, "indicator": indicator,
        "period_start": str(start)[:10], "period_end": str(end)[:10],
        "time_resolution": time_resolution or m.get("time_resolution", ""),
        "value": value, "unit": m.get("unit", ""), "n_records": n,
        "source_id": sid, "source_file": config.SOURCES[sid]["file"] if sid in config.SOURCES else "",
        "flags": flags,
    }


def permit_annual_observations(permits: pd.DataFrame, neighborhoods: Dict[str, str]) -> List[dict]:
    """Annual permit indicators for every neighborhood (zero-filled) and the city."""
    last_date = permits["issue_date"].max()
    first_date = permits["issue_date"].min()
    years = range(first_date.year, last_date.year + 1)
    res = permits["is_residential"]
    subsets = {
        "res_new_construction_permits": permits[(permits.category == "new_construction") & res],
        "demolition_permits": permits[permits.category == "demolition"],
        "res_alteration_permits": permits[(permits.category == "alteration") & res],
    }
    value_df = permits[res & permits.category.isin(["new_construction", "alteration"])]
    rows: List[dict] = []
    areas = [(nid, name, "neighborhood") for nid, name in sorted(neighborhoods.items())] + [("city-pittsburgh", "City of Pittsburgh", "city")]
    for area_id, name, geo in areas:
        for y in years:
            start = pd.Timestamp(f"{y}-01-01")
            end = pd.Timestamp(f"{y}-12-31")
            flags = []
            if y == first_date.year and first_date > start:
                flags.append(f"partial_year:starts_{first_date.date()}")
                start = first_date
            if y == last_date.year and last_date < end:
                flags.append(f"partial_year:ends_{last_date.date()}")
                end = last_date
            for ind, sub in subsets.items():
                s = sub[sub.year == y]
                if geo == "neighborhood":
                    s = s[s.neighborhood_id == area_id]
                rows.append(_obs(area_id, name, geo, ind, start, end, int(len(s)), n=int(len(s)), flags=";".join(flags)))
            v = value_df[value_df.year == y]
            if geo == "neighborhood":
                v = v[v.neighborhood_id == area_id]
            known = v["project_value"].dropna()
            vflags = list(flags)
            if len(v) and len(known) < len(v):
                vflags.append(f"value_unknown_for_{len(v) - len(known)}_of_{len(v)}_permits")
            rows.append(_obs(area_id, name, geo, "res_permit_value", start, end,
                             float(known.sum()), n=int(len(known)), flags=";".join(vflags)))
    return rows


def inventory_observations(inv: pd.DataFrame, neighborhoods: Dict[str, str], land_km2: Dict[str, float], snapshot_date: str) -> List[dict]:
    rows = []
    counts = inv[inv.is_vacant_land_for_reuse].groupby("neighborhood_id").size()
    for nid, name in sorted(neighborhoods.items()):
        c = int(counts.get(nid, 0))
        rows.append(_obs(nid, name, "neighborhood", "city_owned_vacant_lots", snapshot_date, snapshot_date, c, n=c, flags="snapshot"))
        km2 = land_km2.get(nid)
        dens = round(c / km2, 2) if km2 else None
        rows.append(_obs(nid, name, "neighborhood", "city_owned_vacant_lots_per_km2", snapshot_date, snapshot_date, dens, n=c, flags="snapshot"))
    total = int(inv.is_vacant_land_for_reuse.sum())
    rows.append(_obs("city-pittsburgh", "City of Pittsburgh", "city", "city_owned_vacant_lots", snapshot_date, snapshot_date, total, n=total, flags="snapshot"))
    tot_km2 = sum(land_km2.values())
    rows.append(_obs("city-pittsburgh", "City of Pittsburgh", "city", "city_owned_vacant_lots_per_km2", snapshot_date, snapshot_date, round(total / tot_km2, 2), n=total, flags="snapshot"))
    return rows


METRO_SOURCE = {
    "metro_home_value": "zillow_zhvi_inferred",
    "metro_inventory": "zillow_inventory",
    "metro_days_to_pending": "zillow_days_pending",
    "metro_new_construction_sales": "zillow_newcon_sales",
    "metro_sales": "zillow_sales",
    "metro_income_needed": "zillow_income_needed",
    "metro_market_heat": "zillow_market_heat",
}


def metro_observations() -> List[dict]:
    """Monthly Zillow values for the Pittsburgh MSA and the United States."""
    rows = []
    for ind, sid in METRO_SOURCE.items():
        wide = load_zillow_wide(sid)
        for rid, name, geo in ((config.PITTSBURGH_MSA_REGION_ID, "Pittsburgh, PA metro", "metro"), (config.US_REGION_ID, "United States", "country")):
            s = zillow_series(wide, rid).dropna()
            flags = "smoothed" if "_sm_" in config.SOURCES[sid]["file"] else ""
            if sid == "zillow_sales":
                flags = "nowcast"
            if sid == "zillow_zhvi_inferred":
                flags = "inferred_source"
            for d, v in s.items():
                rows.append(_obs(f"msa-{rid}" if geo == "metro" else "us", name, geo, ind,
                                 d.replace(day=1), d, float(v), flags=flags, time_resolution="monthly"))
    return rows


REDFIN_MAP = {
    "HOMES SOLD": ("redfin_homes_sold", "sales"),
    "MEDIAN SALE PRICE NSA ($)": ("redfin_median_sale_price", "USD"),
    "MEDIAN DAYS ON MARKET (DAYS)": ("redfin_median_days_on_market", "days"),
    "ACTIVE LISTINGS": ("redfin_active_listings", "listings"),
}


def redfin_observations() -> List[dict]:
    rf = load_redfin_national()
    rows = []
    for col, (ind, unit) in REDFIN_MAP.items():
        for d, v in rf[col].items():
            r = _obs("us", "United States", "country", ind, d.replace(day=1), d, float(v),
                     source_id="redfin_national", time_resolution="monthly")
            r["unit"] = unit
            rows.append(r)
    return rows


def build(neighborhoods: Dict[str, str], land_km2: Dict[str, float]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]:
    permits, pqa = load_permits()
    inv, iqa = load_inventory()
    unknown = sorted(set(permits.neighborhood_id) - set(neighborhoods))
    pqa["permits_in_neighborhoods_without_polygon"] = unknown
    snapshot = iqa["snapshot_last_updated_max"]
    rows = permit_annual_observations(permits, neighborhoods)
    rows += inventory_observations(inv, neighborhoods, land_km2, snapshot)
    rows += metro_observations()
    rows += redfin_observations()
    obs = pd.DataFrame(rows, columns=OBS_COLUMNS)
    dup = obs.duplicated(["area_id", "indicator", "period_start", "period_end"])
    if dup.any():
        raise ValueError(f"duplicate observations: {int(dup.sum())}")
    return obs, permits, inv, {"permits": pqa, "inventory": iqa}
