"""Optional: Census ACS 5-year tract estimates (rent, income, vacancy, renters).

Drop Census API responses into data/raw/acs/ named acs_<YEAR>.json, e.g.

  https://api.census.gov/data/2023/acs/acs5?get=NAME,B25064_001E,B19013_001E,B25002_001E,B25002_003E,B25003_001E,B25003_003E&for=tract:*&in=state:42%20county:003

(open the link in a browser and save the page as data/raw/acs/acs_2023.json; the
same with 2019 in place of 2023 for acs_2019.json).

ACS 2019 and earlier use 2010 tracts; 2020 and later use 2020 tracts, so each
vintage is linked to neighborhoods with its own crosswalk. Values stay at
tract level: medians are never averaged across tracts.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import pandas as pd

from . import config

ACS_DIR = config.RAW / "acs"
VARS = {
    "median_gross_rent": "B25064_001E",
    "median_household_income": "B19013_001E",
    "housing_units": "B25002_001E",
    "vacant_units": "B25002_003E",
    "occupied_units": "B25003_001E",
    "renter_occupied": "B25003_003E",
}
MISSING_SENTINELS = {-666666666, -999999999, -888888888, -222222222, -333333333, -555555555}


def _num(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v in MISSING_SENTINELS or v < 0 else v


def parse_api_json(path) -> pd.DataFrame:
    rows = json.load(open(path))
    header, data = rows[0], rows[1:]
    df = pd.DataFrame(data, columns=header)
    need = {"state", "county", "tract"}
    if not need <= set(df.columns):
        raise ValueError(f"{path}: expected state/county/tract columns (tract-level Census API response)")
    df["geoid"] = df["state"].str.zfill(2) + df["county"].str.zfill(3) + df["tract"].str.zfill(6)
    out = pd.DataFrame({"geoid": df["geoid"]})
    for name, var in VARS.items():
        out[name] = df[var].map(_num) if var in df.columns else None
    out["vacancy_rate"] = out.apply(lambda r: r.vacant_units / r.housing_units if r.housing_units else None, axis=1)
    out["renter_share"] = out.apply(lambda r: r.renter_occupied / r.occupied_units if r.occupied_units else None, axis=1)
    return out


def load_all() -> Dict[int, pd.DataFrame]:
    out = {}
    if not ACS_DIR.exists():
        return out
    for p in sorted(ACS_DIR.glob("acs_*.json")):
        m = re.search(r"acs_(\d{4})", p.name)
        if m:
            out[int(m.group(1))] = parse_api_json(p)
    return out


def neighborhood_acs(vintages: Dict[int, pd.DataFrame]) -> Dict[str, dict]:
    """neighborhood_id -> tract-level ACS evidence (per vintage)."""
    if not vintages:
        return {}
    xw10 = pd.read_csv(config.PROCESSED / "neighborhood_tract_crosswalk.csv", dtype={"tract_geoid_2010": str})
    p20 = config.PROCESSED / "neighborhood_tract2020_crosswalk.csv"
    xw20 = pd.read_csv(p20, dtype={"tract_geoid_2020": str}) if p20.exists() else None
    out: Dict[str, dict] = {}
    for year, df in sorted(vintages.items()):
        use20 = year >= 2020
        xw = xw20 if use20 else xw10
        if xw is None:
            continue
        col = "tract_geoid_2020" if use20 else "tract_geoid_2010"
        vals = df.set_index("geoid")
        city_tracts = set(xw[col])
        city = vals[vals.index.isin(city_tracts)]
        typical = {k: (float(city[k].median()) if city[k].notna().any() else None)
                   for k in ("median_gross_rent", "median_household_income", "vacancy_rate", "renter_share")}
        for nid, grp in xw.groupby("neighborhood_id"):
            tracts = []
            for r in grp.sort_values("share_of_neighborhood_land", ascending=False).itertuples():
                share = float(r.share_of_neighborhood_land)
                g = getattr(r, col)
                if share < 0.10 or g not in vals.index:
                    continue
                v = vals.loc[g]
                tracts.append({"geoid": g, "share_of_neighborhood_land": share,
                               **{k: (None if pd.isna(v[k]) else float(v[k])) for k in typical}})
            entry = out.setdefault(nid, {"vintages": [], "note": (
                "Census ACS 5-year estimates for the census tracts covering this neighborhood (tract level, shown separately; "
                "medians are not averaged). ACS values are survey estimates with margins of error.")})
            entry["vintages"].append({"year": year, "period": f"{year - 4}–{year}", "tract_vintage": 2020 if use20 else 2010,
                                      "tracts": tracts, "typical_city_tract": typical,
                                      "source": f"U.S. Census Bureau, ACS 5-year {year - 4}–{year}"})
    return out
