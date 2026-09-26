"""Small, dependency-light statistical helpers with explicit edge-case rules."""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

MAD_SCALE = 1.4826  # makes MAD comparable to a standard deviation for normal data


def safe_pct_change(new: Optional[float], old: Optional[float], min_base: float = 1e-9) -> Optional[float]:
    """Percent change as a fraction. None if either side unknown or base too small."""
    if new is None or old is None:
        return None
    if isinstance(new, float) and math.isnan(new):
        return None
    if isinstance(old, float) and math.isnan(old):
        return None
    if abs(old) < min_base:
        return None
    return new / old - 1.0


def poisson_residual(observed: float, expected: float) -> float:
    """(O − E) / sqrt(E + 1). The +1 keeps the ratio finite when E = 0."""
    return (observed - expected) / math.sqrt(expected + 1.0)


def robust_z(values: Dict[str, float]) -> Dict[str, float]:
    """Robust z-scores: (x − median) / (1.4826 · MAD).

    Falls back to the standard deviation if MAD is 0, and returns 0 for all
    if there is no spread at all. Keys with None/NaN are omitted.
    """
    clean = {k: v for k, v in values.items() if v is not None and not (isinstance(v, float) and math.isnan(v))}
    if len(clean) < 3:
        return {k: 0.0 for k in clean}
    arr = np.array(list(clean.values()), dtype=float)
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med))) * MAD_SCALE
    scale = mad if mad > 1e-12 else float(np.std(arr))
    if scale < 1e-12:
        return {k: 0.0 for k in clean}
    return {k: (v - med) / scale for k, v in clean.items()}


def robust_center_scale(values: Sequence[float]):
    arr = np.array([v for v in values if v is not None and not math.isnan(v)], dtype=float)
    if len(arr) == 0:
        return None, None
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med))) * MAD_SCALE
    scale = mad if mad > 1e-12 else float(np.std(arr))
    return med, scale


def percentile_rank(value: float, population: Iterable[float]) -> Optional[float]:
    """Share (0–100) of the population strictly below value, ties counted half."""
    pop = [p for p in population if p is not None and not math.isnan(p)]
    if not pop:
        return None
    below = sum(1 for p in pop if p < value)
    equal = sum(1 for p in pop if p == value)
    return 100.0 * (below + 0.5 * equal) / len(pop)


def rms(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return math.sqrt(sum(v * v for v in values) / len(values))


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na < 1e-12 or nb < 1e-12:
        return None
    return float(np.dot(va, vb) / (na * nb))
