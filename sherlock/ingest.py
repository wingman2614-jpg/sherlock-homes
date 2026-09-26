"""Step 2 — load and clean raw datasets.

Each loader returns a tidy pandas DataFrame plus a QA dict describing every
row that was dropped or re-coded, so nothing disappears silently.
"""
from __future__ import annotations

import re
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from . import config
from .build_geography import slugify

# ---------------------------------------------------------------------------
# PLI permits
# ---------------------------------------------------------------------------
BUILDING_PERMIT_TYPES = {"BUILDING", "Building & Development Application"}

# The City's permit system changed in 2024: `BUILDING` → `Building & Development
# Application`, and work_type vocabulary changed. This crosswalk maps both
# vocabularies onto one harmonised category.
WORK_TYPE_CROSSWALK = {
    "NEW CONSTRUCTION": "new_construction",
    "NEW": "new_construction",
    "ADDITION / ALTERATION": "alteration",
    "MINOR ALTERATION": "alteration",
    "EXISTING (ALTERATION/ADDITION)": "alteration",
    "ALTERATION TO EXISTING": "alteration",
    "NON-SUBSTANTIAL IMPROVEMENT": "alteration",
    "SUBSTANTIAL IMPROVEMENT": "alteration",
    "SUBSTANTIAL DAMAGE REPAIR": "alteration",
}
DEMOLITION_WORK_TYPES = {"COMPLETE DEMOLITION": "complete", "CITY FUNDED DEMOLITION": "city_funded"}


def classify_permit(permit_type: str, work_type: str | float) -> str | None:
    """Return harmonised category or None if the permit is not analysed."""
    wt = str(work_type).strip().upper() if isinstance(work_type, str) else ""
    if permit_type == "Demolition Permit":
        return "demolition" if wt in DEMOLITION_WORK_TYPES else None
    if permit_type in BUILDING_PERMIT_TYPES:
        return WORK_TYPE_CROSSWALK.get(wt)
    return None


def load_permits(path=None) -> Tuple[pd.DataFrame, Dict]:
    path = path or config.RAW / config.SOURCES["pli_permits"]["file"]
    raw = pd.read_csv(path, low_memory=False, dtype={"parcel_num": str, "permit_id": str})
    qa: Dict = {"rows_raw": int(len(raw))}
    df = raw.copy()
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    qa["dropped_bad_date"] = int(df["issue_date"].isna().sum())
    df = df[df["issue_date"].notna()]
    df["category"] = [classify_permit(pt, wt) for pt, wt in zip(df["permit_type"], df["work_type"])]
    df["demolition_kind"] = df["work_type"].str.upper().map(DEMOLITION_WORK_TYPES)
    qa["not_analysed_permit_types"] = int(df["category"].isna().sum())
    df = df[df["category"].notna()].copy()
    revoked = df["status"].eq("Revoked")
    qa["dropped_revoked"] = int(revoked.sum())
    df = df[~revoked]
    key = ["parcel_num", "issue_date", "permit_type", "work_type", "work_description", "total_project_value"]
    dup = df.duplicated(key, keep="first") & df["work_description"].notna()
    qa["dropped_exact_duplicates"] = int(dup.sum())
    df = df[~dup]
    missing_nb = df["neighborhood"].isna()
    qa["dropped_missing_neighborhood"] = int(missing_nb.sum())
    df = df[~missing_nb].copy()
    df["neighborhood_id"] = df["neighborhood"].map(slugify)
    df["year"] = df["issue_date"].dt.year
    df["is_residential"] = df["commercial_or_residential"].eq("Residential")
    v = pd.to_numeric(df["total_project_value"], errors="coerce")
    qa["value_nonpositive_set_unknown"] = int((v <= 0).sum())
    df["project_value"] = v.where(v > 0)  # 0 / negative => unknown, not zero
    df["system"] = np.where(df["permit_type"].eq("Building & Development Application"), "new_2024", "legacy")
    qa["rows_analysed"] = int(len(df))
    qa["categories"] = df["category"].value_counts().to_dict()
    return df, qa


# ---------------------------------------------------------------------------
# City-owned property inventory (snapshot)
# ---------------------------------------------------------------------------
def load_inventory(path=None) -> Tuple[pd.DataFrame, Dict]:
    path = path or config.RAW / config.SOURCES["city_inventory"]["file"]
    df = pd.read_csv(path, low_memory=False)
    qa: Dict = {"rows_raw": int(len(df))}
    for col in ("current_status", "inventory_type"):
        df[col] = df[col].str.strip().str.title()  # 'Hold For Study' == 'Hold for Study'
    acq = pd.to_datetime(df["acquisition_date"], errors="coerce")
    last = pd.to_datetime(df["last_updated"], errors="coerce").max()
    future = acq > last
    qa["acquisition_date_invalid_future"] = int(future.sum())
    df["acquisition_date"] = acq.where(~future)
    df["tract_geoid_2010"] = df["census_tract"].dropna().astype("int64").astype(str).reindex(df.index)
    miss = df["neighborhood_name"].isna()
    qa["missing_neighborhood"] = int(miss.sum())
    df = df[~miss].copy()
    df["neighborhood_id"] = df["neighborhood_name"].map(slugify)
    # Parks, greenways etc. are held as open space, not as vacant land awaiting reuse.
    open_space_types = {"Park", "Legislated Greenway", "Greenway", "Potential Greenway"}
    df["is_vacant_land_for_reuse"] = df["class"].eq("Vacant Land") & ~df["inventory_type"].isin(open_space_types)
    qa["snapshot_last_updated_max"] = str(last.date()) if pd.notna(last) else None
    return df, qa


# ---------------------------------------------------------------------------
# Zillow metro files (wide → long)
# ---------------------------------------------------------------------------
_DATE_COL = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_zillow_wide(source_id: str) -> pd.DataFrame:
    """Return the wide Zillow table (one row per region, one column per month)."""
    path = config.RAW / config.SOURCES[source_id]["file"]
    df = pd.read_csv(path)
    if df["RegionID"].duplicated().any():
        raise ValueError(f"{source_id}: duplicate RegionID")
    return df


def zillow_date_columns(df: pd.DataFrame):
    return [c for c in df.columns if _DATE_COL.match(c)]


def zillow_series(df: pd.DataFrame, region_id: int) -> pd.Series:
    row = df[df["RegionID"] == region_id]
    if row.empty:
        return pd.Series(dtype=float)
    cols = zillow_date_columns(df)
    s = row[cols].iloc[0].astype(float)
    s.index = pd.to_datetime(s.index)
    return s


# ---------------------------------------------------------------------------
# Redfin national
# ---------------------------------------------------------------------------
def load_redfin_national() -> pd.DataFrame:
    path = config.RAW / config.SOURCES["redfin_national"]["file"]
    df = pd.read_csv(path)
    df["period_end"] = pd.to_datetime(df["PERIOD END"])
    df = df.sort_values("period_end").set_index("period_end")
    if df.index.duplicated().any():
        raise ValueError("redfin: duplicate months")
    return df
