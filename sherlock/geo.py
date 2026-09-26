"""Dependency-free geometry utilities.

Builds Pittsburgh neighborhood and census-tract polygons by dissolving 2010
Census blocks (BlockCodes2016). Implemented in pure Python so the pipeline
has no GDAL/GeoPandas requirement.

Dissolve method: Census blocks come from a topologically consistent source,
so two neighbouring blocks share identical edges. Within a group
(e.g. one neighborhood) every interior edge appears twice and cancels out;
the edges that remain form the group's outer boundary and holes.
"""
from __future__ import annotations

import io
import math
import struct
import zipfile
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

Point = Tuple[float, float]
Ring = List[Point]

R_EARTH = 6378137.0


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------
def read_dbf(data: bytes, columns: Iterable[str] | None = None) -> List[Dict[str, str]]:
    """Read a dBASE table. Returns list of dicts of stripped strings."""
    wanted = set(columns) if columns else None
    n, header_len, rec_len = struct.unpack("<xxxxIHH20x", data[:32])
    fields = []
    pos = 32
    while data[pos] != 0x0D:
        d = data[pos:pos + 32]
        fields.append((d[:11].split(b"\0")[0].decode("latin1"), d[16]))
        pos += 32
    rows = []
    for i in range(n):
        start = header_len + i * rec_len
        rec = data[start:start + rec_len]
        off = 1
        row = {}
        for name, length in fields:
            if wanted is None or name in wanted:
                row[name] = rec[off:off + length].decode("latin1").strip()
            off += length
        rows.append(row)
    return rows


def read_shp_polygons(shp: bytes, shx: bytes, indices: Iterable[int]) -> Dict[int, List[Ring]]:
    """Read polygon records (shape type 5) for the given 0-based indices."""
    out: Dict[int, List[Ring]] = {}
    for i in indices:
        offset_words, = struct.unpack(">i", shx[100 + 8 * i:104 + 8 * i])
        pos = offset_words * 2 + 8  # skip record header
        shape_type, = struct.unpack("<i", shp[pos:pos + 4])
        if shape_type == 0:
            out[i] = []
            continue
        if shape_type not in (5, 15, 25):
            raise ValueError(f"record {i}: unsupported shape type {shape_type}")
        num_parts, num_points = struct.unpack("<ii", shp[pos + 36:pos + 44])
        parts = list(struct.unpack(f"<{num_parts}i", shp[pos + 44:pos + 44 + 4 * num_parts]))
        pts_start = pos + 44 + 4 * num_parts
        coords = struct.unpack(f"<{2 * num_points}d", shp[pts_start:pts_start + 16 * num_points])
        pts = [(coords[2 * k], coords[2 * k + 1]) for k in range(num_points)]
        parts.append(num_points)
        out[i] = [pts[parts[p]:parts[p + 1]] for p in range(num_parts)]
    return out


def open_shapefile_zip(path, stem: str) -> Tuple[bytes, bytes, bytes]:
    with zipfile.ZipFile(path) as z:
        return z.read(f"{stem}.shp"), z.read(f"{stem}.shx"), z.read(f"{stem}.dbf")


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------
def mercator_to_lonlat(x: float, y: float) -> Point:
    lon = math.degrees(x / R_EARTH)
    lat = math.degrees(2 * math.atan(math.exp(y / R_EARTH)) - math.pi / 2)
    return (lon, lat)


# ---------------------------------------------------------------------------
# Ring helpers
# ---------------------------------------------------------------------------
def signed_area(ring: Sequence[Point]) -> float:
    """Shoelace signed area. Positive = counter-clockwise (y up)."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2.0


def point_in_ring(pt: Point, ring: Sequence[Point]) -> bool:
    x, y = pt
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _perp_dist(p: Point, a: Point, b: Point) -> float:
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def simplify_ring(ring: Ring, tol: float) -> Ring:
    """Douglas-Peucker on a closed ring (iterative). Keeps ring closed."""
    if len(ring) <= 5 or tol <= 0:
        return ring
    pts = ring[:-1] if ring[0] == ring[-1] else ring[:]
    # split at the point farthest from the first point to get two open chains
    far = max(range(len(pts)), key=lambda k: (pts[k][0] - pts[0][0]) ** 2 + (pts[k][1] - pts[0][1]) ** 2)
    chains = [pts[:far + 1], pts[far:] + [pts[0]]]
    result: List[Point] = []
    for chain in chains:
        keep = [False] * len(chain)
        keep[0] = keep[-1] = True
        stack = [(0, len(chain) - 1)]
        while stack:
            s, e = stack.pop()
            best, idx = 0.0, -1
            for k in range(s + 1, e):
                d = _perp_dist(chain[k], chain[s], chain[e])
                if d > best:
                    best, idx = d, k
            if idx != -1 and best > tol:
                keep[idx] = True
                stack.append((s, idx))
                stack.append((idx, e))
        kept = [p for p, k in zip(chain, keep) if k]
        result.extend(kept[:-1])
    result.append(result[0])
    return result if len(result) >= 4 else ring


# ---------------------------------------------------------------------------
# Dissolve
# ---------------------------------------------------------------------------
def _key(p: Point, nd: int = 3) -> Tuple[float, float]:
    return (round(p[0], nd), round(p[1], nd))


def dissolve(polygons: Iterable[List[Ring]]) -> List[Ring]:
    """Dissolve many polygons (list of rings each) into boundary rings.

    Returns closed rings in the input coordinate system; orientation of each
    ring follows the input convention (outer vs hole decided later by area
    sign and containment).
    """
    edge_count: Dict[Tuple, int] = defaultdict(int)
    directed: List[Tuple[Tuple, Tuple]] = []
    for rings in polygons:
        for ring in rings:
            for a, b in zip(ring, ring[1:]):
                ka, kb = _key(a), _key(b)
                if ka == kb:
                    continue
                edge_count[(ka, kb) if ka < kb else (kb, ka)] += 1
                directed.append((ka, kb))
    boundary = [(a, b) for a, b in directed if edge_count[(a, b) if a < b else (b, a)] == 1]
    nxt: Dict[Tuple, List[Tuple]] = defaultdict(list)
    for a, b in boundary:
        nxt[a].append(b)
    rings: List[Ring] = []
    used_total = 0
    while nxt:
        start = next(iter(nxt))
        ring = [start]
        cur = start
        guard = 0
        while True:
            outs = nxt.get(cur)
            if not outs:
                break
            nb = outs.pop()
            if not outs:
                del nxt[cur]
            used_total += 1
            ring.append(nb)
            cur = nb
            guard += 1
            if cur == start or guard > 10_000_000:
                break
        if len(ring) >= 4 and ring[0] == ring[-1]:
            rings.append(ring)
    return rings


def rings_to_multipolygon(rings: List[Ring], min_area: float = 0.0) -> List[List[Ring]]:
    """Group boundary rings into polygons using nesting depth.

    Rings are processed largest first. A ring's depth is the number of
    already-placed rings that contain it: even depth -> new outer ring,
    odd depth -> hole of the smallest outer that contains it.
    """
    items = [(abs(signed_area(r)), r) for r in rings]
    items = [t for t in items if t[0] > min_area]
    items.sort(key=lambda t: -t[0])
    placed: List[Tuple[Ring, bool, int]] = []  # (ring, is_outer, polygon index)
    polys: List[List[Ring]] = []
    for _, ring in items:
        a, b = ring[0], ring[1]
        probe = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        containing = [(r, outer, pi) for r, outer, pi in placed if point_in_ring(probe, r)]
        if len(containing) % 2 == 0:
            polys.append([ring])
            placed.append((ring, True, len(polys) - 1))
        else:
            # smallest containing outer = last outer in `containing` (area desc order)
            outer_pi = [pi for r, outer, pi in containing if outer][-1]
            polys[outer_pi].append(ring)
            placed.append((ring, False, outer_pi))
    return polys


def orient_rfc7946(poly: List[Ring]) -> List[Ring]:
    out = []
    for k, ring in enumerate(poly):
        a = signed_area(ring)
        want_ccw = k == 0
        if (a > 0) != want_ccw:
            ring = list(reversed(ring))
        out.append(ring)
    return out


def to_geojson_geometry(polys: List[List[Ring]], ndigits: int = 6) -> dict:
    coords = [[[[round(x, ndigits), round(y, ndigits)] for x, y in ring] for ring in poly] for poly in polys]
    if len(coords) == 1:
        return {"type": "Polygon", "coordinates": coords[0]}
    return {"type": "MultiPolygon", "coordinates": coords}


def bbox_of(polys: List[List[Ring]]) -> List[float]:
    xs = [x for poly in polys for ring in poly for x, _ in ring]
    ys = [y for poly in polys for ring in poly for _, y in ring]
    return [min(xs), min(ys), max(xs), max(ys)]


def centroid_of(polys: List[List[Ring]]) -> Point:
    """Area-weighted centroid of outer rings (label placement only)."""
    cx = cy = total = 0.0
    for poly in polys:
        ring = poly[0]
        a = signed_area(ring)
        if a == 0:
            continue
        sx = sy = 0.0
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            cross = x1 * y2 - x2 * y1
            sx += (x1 + x2) * cross
            sy += (y1 + y2) * cross
        cx += sx / (6 * a) * abs(a)
        cy += sy / (6 * a) * abs(a)
        total += abs(a)
    return (cx / total, cy / total) if total else (float("nan"), float("nan"))
