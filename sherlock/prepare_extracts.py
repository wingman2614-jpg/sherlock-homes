"""Step 0 (Mk2): slim down very large source files.

The original downloads are too large to ship (county sales ≈ 108 MB, Zillow ZIP
home values ≈ 124 MB). This step reads them from data/raw/original/ (if present)
and writes compact extracts into data/raw/, which is what the pipeline reads.
Nothing is aggregated or altered here: rows are filtered to the study area and
unused columns dropped. Row counts are recorded in data/raw/extracts_manifest.json.

    python -m sherlock.prepare_extracts
"""
from __future__ import annotations

import json
import re

import pandas as pd

from . import config
from .geo import open_shapefile_zip, read_dbf, read_shp_polygons, simplify_ring, orient_rfc7946, to_geojson_geometry

ORIG = config.RAW / "original"
SALES_COLS = ["PARID", "PROPERTYZIP", "MUNICODE", "MUNIDESC", "SALEDATE", "RECORDDATE", "PRICE",
              "SALECODE", "SALEDESC", "INSTRTYP", "INSTRTYPDESC"]


def sales(manifest: dict) -> None:
    src = ORIG / "sales.csv"
    if not src.exists():
        return
    df = pd.read_csv(src, usecols=SALES_COLS, dtype={"PARID": str, "PROPERTYZIP": str}, low_memory=False)
    out = config.RAW / "allegheny_sales_slim.csv.gz"
    df.to_csv(out, index=False, compression="gzip")
    manifest["allegheny_sales_slim.csv.gz"] = {"from": "sales.csv", "rows_in": int(len(df)), "rows_out": int(len(df)),
                                               "note": "All rows kept; columns reduced to those used."}


def zillow_zip(name: str, out_name: str, manifest: dict) -> None:
    src = ORIG / name
    if not src.exists():
        return
    df = pd.read_csv(src, dtype={"RegionName": str})
    keep = df[(df["StateName"] == "PA") & (df["CountyName"] == "Allegheny County")]
    keep.to_csv(config.RAW / out_name, index=False)
    manifest[out_name] = {"from": name, "rows_in": int(len(df)), "rows_out": int(len(keep)),
                          "note": "Filtered to ZIP codes Zillow assigns to Allegheny County, PA."}


def tracts_2020(manifest: dict) -> None:
    src = ORIG / "tl_2022_42_tract.zip"
    if not src.exists():
        return
    shp, shx, dbf = open_shapefile_zip(src, "tl_2022_42_tract")
    rows = read_dbf(dbf, ["GEOID", "COUNTYFP", "NAMELSAD", "ALAND", "AWATER"])
    idx = [i for i, r in enumerate(rows) if r["COUNTYFP"] == "003"]
    geoms = read_shp_polygons(shp, shx, idx)
    feats = []
    for i in idx:
        polys = []
        # TIGER parts: outer rings are clockwise; holes counter-clockwise (lon/lat)
        from .geo import rings_to_multipolygon
        for poly in rings_to_multipolygon(geoms[i]):
            polys.append(orient_rfc7946([simplify_ring(r, 0.00003) for r in poly]))
        r = rows[i]
        feats.append({"type": "Feature", "properties": {"geoid": r["GEOID"], "name": r["NAMELSAD"],
                                                        "land_m2": float(r["ALAND"] or 0)},
                      "geometry": to_geojson_geometry(polys)})
    with open(config.RAW / "tracts_2020_allegheny.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))
    manifest["tracts_2020_allegheny.geojson"] = {"from": "tl_2022_42_tract.zip", "rows_in": len(rows), "rows_out": len(feats),
                                                 "note": "2020 Census tracts (TIGER 2022) for Allegheny County, lightly simplified."}


def run() -> dict:
    manifest: dict = {}
    mpath = config.RAW / "extracts_manifest.json"
    if mpath.exists():
        manifest = json.load(open(mpath))
    sales(manifest)
    zillow_zip("Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv", "zip_zhvi_allegheny.csv", manifest)
    zillow_zip("Zip_zori_uc_sfrcondomfr_sm_month.csv", "zip_zori_allegheny.csv", manifest)
    tracts_2020(manifest)
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=1)
    for k, v in manifest.items():
        print(f"  {k}: {v['rows_out']:,} rows (from {v['rows_in']:,})")
    return manifest


if __name__ == "__main__":
    run()
