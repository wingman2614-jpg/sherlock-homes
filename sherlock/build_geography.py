"""Step 1 — build analysis geographies from 2010 Census blocks.

Outputs (data/processed/):
  neighborhoods.geojson   90 City of Pittsburgh neighborhoods (dissolved blocks)
  tracts.geojson          2010 census tracts touching the City (city blocks only)
  neighborhood_tract_crosswalk.csv  land-area shares linking neighborhoods and tracts
  geography_qa.json       dissolve diagnostics
"""
from __future__ import annotations

import csv
import json
import time
from collections import defaultdict

from . import config
from .geo import (
    bbox_of, centroid_of, dissolve, mercator_to_lonlat, open_shapefile_zip,
    orient_rfc7946, read_dbf, read_shp_polygons, rings_to_multipolygon,
    simplify_ring, to_geojson_geometry,
)

SIMPLIFY_TOL_M = 4.0   # Web Mercator units (~3 m on the ground at 40.4°N)
EXCLUDED_NEIGHBORHOODS = {"Mount Oliver Borough"}  # separate municipality, not in City data


def slugify(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-").replace("--", "-")


def _project(polys):
    out = []
    for poly in polys:
        rings = []
        for ring in poly:
            ring = simplify_ring(ring, SIMPLIFY_TOL_M)
            rings.append([mercator_to_lonlat(x, y) for x, y in ring])
        out.append(orient_rfc7946(rings))
    return out


def build(verbose: bool = True) -> dict:
    t0 = time.time()
    shp, shx, dbf = open_shapefile_zip(config.RAW / "blockcodes2016.zip", "BlockCodes2016")
    rows = read_dbf(dbf, ["GEOID10", "geo_name_n", "geo_id_tra", "geo_name_1", "ALAND10", "geo_name_z", "geo_id_cou", "INTPTLAT10", "INTPTLON10"])
    city_idx = [i for i, r in enumerate(rows) if r["geo_name_1"] == "Pittsburgh city"]
    nbhd_idx = [i for i, r in enumerate(rows) if r["geo_name_n"] and r["geo_name_n"] not in EXCLUDED_NEIGHBORHOODS]
    county_idx = [i for i, r in enumerate(rows) if r["geo_id_cou"] == "42003" and r["geo_name_z"]]
    need = sorted(set(city_idx) | set(nbhd_idx) | set(county_idx))
    geoms = read_shp_polygons(shp, shx, need)
    if verbose:
        print(f"  read {len(need)} block polygons in {time.time() - t0:.1f}s")

    groups_n = defaultdict(list)
    for i in nbhd_idx:
        groups_n[rows[i]["geo_name_n"]].append(i)
    groups_t = defaultdict(list)
    for i in city_idx:
        groups_t[rows[i]["geo_id_tra"]].append(i)
    groups_z = defaultdict(list)
    for i in county_idx:
        groups_z[rows[i]["geo_name_z"]].append(i)

    qa = {"neighborhoods": {}, "tracts": {}}

    def make_features(groups, kind):
        feats = []
        for key, idxs in sorted(groups.items()):
            rings = dissolve(geoms[i] for i in idxs)
            polys = rings_to_multipolygon(rings, min_area=50.0)  # drop slivers < 50 m²
            polys_ll = _project(polys)
            land_m2 = sum(float(rows[i]["ALAND10"] or 0) for i in idxs)
            cx, cy = centroid_of(polys_ll)
            props = {
                "block_count": len(idxs),
                "land_area_km2": round(land_m2 / 1e6, 4),
                "centroid": [round(cx, 6), round(cy, 6)],
                "bbox": [round(v, 6) for v in bbox_of(polys_ll)],
                "boundary_source": "Dissolved from 2010 Census blocks (BlockCodes2016)",
            }
            if kind == "neighborhood":
                props.update({"id": slugify(key), "name": key, "geography": "neighborhood"})
            elif kind == "zip":
                props.update({"id": f"zip-{key}", "name": f"ZIP {key}", "zip": key, "geography": "zip",
                              "boundary_source": "Approximate ZIP area: 2010 Census blocks grouped by their ZIP code (Allegheny County part only)"})
            else:
                props.update({"id": key, "name": f"Tract {key[5:9]}.{key[9:]}", "geoid": key, "geography": "census_tract_2010"})
            feats.append({"type": "Feature", "properties": props, "geometry": to_geojson_geometry(polys_ll)})
            qa.setdefault({"neighborhood": "neighborhoods", "zip": "zips"}.get(kind, "tracts"), {})[key] = {
                "blocks": len(idxs), "rings": len(rings), "polygons": len(polys),
            }
        return feats

    nfeats = make_features(groups_n, "neighborhood")
    tfeats = make_features(groups_t, "tract")
    zfeats = make_features(groups_z, "zip")

    # land-area crosswalk
    xw = defaultdict(float)
    tract_land = defaultdict(float)
    nb_land = defaultdict(float)
    for i in nbhd_idx:
        land = float(rows[i]["ALAND10"] or 0)
        xw[(rows[i]["geo_name_n"], rows[i]["geo_id_tra"])] += land
        tract_land[rows[i]["geo_id_tra"]] += land
        nb_land[rows[i]["geo_name_n"]] += land

    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    for name, feats in (("neighborhoods", nfeats), ("tracts", tfeats), ("zips", zfeats)):
        with open(config.PROCESSED / f"{name}.geojson", "w") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"))
    with open(config.PROCESSED / "neighborhood_tract_crosswalk.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["neighborhood", "neighborhood_id", "tract_geoid_2010", "land_m2",
                    "share_of_neighborhood_land", "share_of_tract_land_in_city_nbhds"])
        for (nb, tr), land in sorted(xw.items()):
            w.writerow([nb, slugify(nb), tr, round(land, 1),
                        round(land / nb_land[nb], 4) if nb_land[nb] else "",
                        round(land / tract_land[tr], 4) if tract_land[tr] else ""])
    # neighborhood <-> ZIP (land-area shares of blocks)
    nz = defaultdict(float)
    zip_land = defaultdict(float)
    for i in county_idx:
        zip_land[rows[i]["geo_name_z"]] += float(rows[i]["ALAND10"] or 0)
    for i in nbhd_idx:
        nz[(rows[i]["geo_name_n"], rows[i]["geo_name_z"])] += float(rows[i]["ALAND10"] or 0)
    with open(config.PROCESSED / "neighborhood_zip_crosswalk.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["neighborhood", "neighborhood_id", "zip", "land_m2", "share_of_neighborhood_land", "share_of_zip_land"])
        for (nb, z), land in sorted(nz.items()):
            if not z:
                continue
            w.writerow([nb, slugify(nb), z, round(land, 1),
                        round(land / nb_land[nb], 4) if nb_land[nb] else "",
                        round(land / zip_land[z], 4) if zip_land.get(z) else ""])

    # neighborhood <-> 2020 tract, by locating each 2010 block's internal point in a 2020 tract polygon
    t20 = config.RAW / "tracts_2020_allegheny.geojson"
    n_t20 = 0
    if t20.exists():
        from .geo import point_in_ring
        polys20 = []
        for f in json.load(open(t20))["features"]:
            g = f["geometry"]
            parts = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            rings = [[(x, y) for x, y in poly[0]] for poly in parts]
            xs = [x for r in rings for x, _ in r]
            ys = [y for r in rings for _, y in r]
            polys20.append((f["properties"]["geoid"], rings, (min(xs), min(ys), max(xs), max(ys))))
        nt = defaultdict(float)
        for i in nbhd_idx:
            try:
                pt = (float(rows[i]["INTPTLON10"]), float(rows[i]["INTPTLAT10"]))
            except ValueError:
                continue
            for geoid, rings, (x0, y0, x1, y1) in polys20:
                if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1 and any(point_in_ring(pt, r) for r in rings):
                    nt[(rows[i]["geo_name_n"], geoid)] += float(rows[i]["ALAND10"] or 0)
                    break
        with open(config.PROCESSED / "neighborhood_tract2020_crosswalk.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["neighborhood", "neighborhood_id", "tract_geoid_2020", "land_m2", "share_of_neighborhood_land"])
            for (nb, tr), land in sorted(nt.items()):
                w.writerow([nb, slugify(nb), tr, round(land, 1), round(land / nb_land[nb], 4) if nb_land[nb] else ""])
        n_t20 = len({k[1] for k in nt})

    qa["summary"] = {
        "neighborhoods": len(nfeats), "tracts": len(tfeats), "zips": len(zfeats), "tracts_2020_linked": n_t20,
        "multi_part_neighborhoods": sorted(k for k, v in qa["neighborhoods"].items() if v["polygons"] > 1),
        "excluded": sorted(EXCLUDED_NEIGHBORHOODS),
        "seconds": round(time.time() - t0, 1),
    }
    with open(config.PROCESSED / "geography_qa.json", "w") as f:
        json.dump(qa, f, indent=1)
    if verbose:
        print(f"  {len(nfeats)} neighborhoods, {len(tfeats)} tracts, {len(zfeats)} ZIP areas, {n_t20} 2020 tracts linked in {time.time() - t0:.1f}s")
    return qa


if __name__ == "__main__":
    build()
