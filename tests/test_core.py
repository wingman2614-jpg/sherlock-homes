"""Unit tests for Sherlock's statistical core and edge cases.

Run with either:  pytest -q      or:  python -m unittest discover tests
"""
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sherlock import analytics as A  # noqa: E402
from sherlock.geo import dissolve, rings_to_multipolygon, signed_area, simplify_ring  # noqa: E402
from sherlock.ingest import classify_permit, load_permits  # noqa: E402
from sherlock.llm import validate  # noqa: E402
from sherlock.stats import cosine_similarity, percentile_rank, poisson_residual, rms, robust_z, safe_pct_change  # noqa: E402


class TestStats(unittest.TestCase):
    def test_zero_denominator_returns_none(self):
        self.assertIsNone(safe_pct_change(10, 0))
        self.assertIsNone(safe_pct_change(0, 0))

    def test_missing_values_return_none(self):
        self.assertIsNone(safe_pct_change(None, 5))
        self.assertIsNone(safe_pct_change(5, None))
        self.assertIsNone(safe_pct_change(float("nan"), 5))

    def test_pct_change(self):
        self.assertAlmostEqual(safe_pct_change(12, 10), 0.2)

    def test_poisson_residual_finite_when_expected_zero(self):
        self.assertEqual(poisson_residual(4, 0), 4.0)
        self.assertEqual(poisson_residual(0, 0), 0.0)

    def test_robust_z_resists_outlier(self):
        vals = {str(i): float(i % 5) for i in range(50)}
        vals["outlier"] = 1000.0
        z = robust_z(vals)
        self.assertGreater(z["outlier"], 100)           # the outlier stands out
        self.assertLess(max(abs(z[k]) for k in vals if k != "outlier"), 2)  # others are not distorted

    def test_robust_z_no_spread(self):
        z = robust_z({"a": 1.0, "b": 1.0, "c": 1.0})
        self.assertEqual(set(z.values()), {0.0})

    def test_robust_z_mad_zero_falls_back_to_std(self):
        z = robust_z({"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0, "e": 10.0})
        self.assertGreater(z["e"], 1.0)

    def test_robust_z_skips_missing(self):
        z = robust_z({"a": 1.0, "b": None, "c": float("nan"), "d": 2.0, "e": 3.0})
        self.assertEqual(set(z), {"a", "d", "e"})

    def test_percentile_and_rms(self):
        self.assertEqual(percentile_rank(5, [1, 2, 3, 4]), 100.0)
        self.assertIsNone(percentile_rank(5, []))
        self.assertAlmostEqual(rms([3, 4]), math.sqrt(12.5))
        self.assertIsNone(rms([]))


class TestAnomaly(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(A.anomaly_level([0.2, -0.3, 0.1])[1], "LOW")
        self.assertEqual(A.anomaly_level([2.1, 0.0])[1], "MEDIUM")
        self.assertEqual(A.anomaly_level([3.2, 0.0])[1], "HIGH")
        self.assertEqual(A.anomaly_level([1.6, -1.6])[1], "HIGH")

    def test_insufficient_history(self):
        score, level = A.anomaly_level([2.5])
        self.assertEqual(level, "INSUFFICIENT DATA")
        self.assertEqual(A.anomaly_level([])[1], "INSUFFICIENT DATA")


class TestAgreement(unittest.TestCase):
    def test_dataset_disagreement(self):
        self.assertEqual(A.classify_agreement(0.14, 0.07), "magnitude")
        self.assertEqual(A.classify_agreement(0.10, -0.08), "direction")
        self.assertEqual(A.classify_agreement(0.10, 0.11), "agree")
        self.assertEqual(A.classify_agreement(None, 0.1), "unknown")
        # tiny values of opposite sign are not a 'direction' conflict
        self.assertEqual(A.classify_agreement(0.01, -0.01), "agree")


class TestSimilarity(unittest.TestCase):
    def test_cosine(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [2, 0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)
        self.assertIsNone(cosine_similarity([0, 0], [1, 1]))

    def test_similarity_requires_three_features_and_explains(self):
        def sig(z):
            return {"status": "scored" if z is not None else "insufficient_data", "z_score": z}
        inds = A.NEIGHBORHOOD_SCORED
        signals = {
            "a": {i: sig(z) for i, z in zip(inds, [2.0, 1.0, 1.0, 1.0])},
            "b": {i: sig(z) for i, z in zip(inds, [1.9, 1.1, 0.9, 1.2])},
            "c": {i: sig(z) for i, z in zip(inds, [-2.0, -1.0, -1.0, -1.0])},
            "d": {i: sig(z) for i, z in zip(inds, [None, None, 1.0, None])},  # too few features
        }
        names = {k: k.upper() for k in signals}
        out = A.similarity(signals, names, vacancy_z={})
        self.assertEqual(out["a"][0]["area_id"], "b")
        self.assertGreater(out["a"][0]["similarity"], 0.95)
        self.assertTrue(out["a"][0]["shared"])            # explanation present
        self.assertEqual(out["d"], [])                     # insufficient features
        self.assertNotIn("d", [x["area_id"] for x in out["a"]])
        c = next(x for x in out["a"] if x["area_id"] == "c")
        self.assertEqual(c["similarity"], 0.0)            # opposite pattern clipped at 0


class TestGeometry(unittest.TestCase):
    def test_dissolve_two_adjacent_squares(self):
        a = [[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]]
        b = [[(1, 0), (1, 1), (2, 1), (2, 0), (1, 0)]]
        rings = dissolve([a, b])
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(abs(signed_area(rings[0])), 2.0)

    def test_hole_detected(self):
        # ring of 8 unit squares around an empty centre
        sq = lambda x, y: [[(x, y), (x, y + 1), (x + 1, y + 1), (x + 1, y), (x, y)]]
        cells = [sq(x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1)]
        polys = rings_to_multipolygon(dissolve(cells))
        self.assertEqual(len(polys), 1)
        self.assertEqual(len(polys[0]), 2)  # outer + hole

    def test_simplify_keeps_closed(self):
        ring = [(0, 0), (0, 0.5), (0, 1), (1, 1), (1, 0), (0, 0)]
        s = simplify_ring(ring, 0.01)
        self.assertEqual(s[0], s[-1])
        self.assertGreaterEqual(len(s), 4)


class TestPermitIngest(unittest.TestCase):
    def test_crosswalk_handles_2024_system_change(self):
        self.assertEqual(classify_permit("BUILDING", "NEW CONSTRUCTION"), "new_construction")
        self.assertEqual(classify_permit("Building & Development Application", "New Construction"), "new_construction")
        self.assertEqual(classify_permit("BUILDING", "MINOR ALTERATION"), "alteration")
        self.assertEqual(classify_permit("Building & Development Application", "Existing (alteration/addition)"), "alteration")
        self.assertEqual(classify_permit("Demolition Permit", "COMPLETE DEMOLITION"), "demolition")
        self.assertIsNone(classify_permit("Demolition Permit", "PARTIAL DEMOLITION"))
        self.assertIsNone(classify_permit("ELECTRICAL", "NEW CONSTRUCTION"))  # trade permits not double counted
        self.assertIsNone(classify_permit("BUILDING", float("nan")))

    def test_duplicates_revoked_and_zero_values(self):
        cols = ["_id", "permit_id", "permit_type", "owner_name", "contractor_name", "work_description", "work_type",
                "commercial_or_residential", "total_project_value", "issue_date", "parcel_num", "address", "latitude",
                "longitude", "council_district", "neighborhood", "ward", "zip_code", "status"]
        base = ["BUILDING", "", "", "NEW HOUSE", "NEW CONSTRUCTION", "Residential", 100000, "2023-05-01", "P1", "x", 40.4, -80.0, 1, "Garfield", 1, 15224, "Issued"]
        rows = [
            [1, "A"] + base,
            [2, "B"] + base,                                   # exact duplicate of A (different id)
            [3, "C"] + base[:-1] + ["Revoked"],                # revoked -> dropped
            [4, "D"] + base[:6] + [0] + base[7:],              # zero value -> unknown
            [5, "E"] + base[:13] + [None] + base[14:],         # missing neighborhood -> dropped
        ]
        rows[3][5] = "DIFFERENT DESCRIPTION"
        rows[4][5] = "ANOTHER DESCRIPTION"
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p.csv")
            pd.DataFrame(rows, columns=cols).to_csv(p, index=False)
            df, qa = load_permits(p)
        self.assertEqual(qa["dropped_exact_duplicates"], 1)
        self.assertEqual(qa["dropped_revoked"], 1)
        self.assertEqual(qa["dropped_missing_neighborhood"], 1)
        self.assertEqual(len(df), 2)
        self.assertTrue(df[df.permit_id == "D"].project_value.isna().all())


class TestLLMGuard(unittest.TestCase):
    CASE = {
        "name": "Testville", "level": "HIGH", "anomaly_score": 2.0,
        "evidence": {"signals": [{
            "indicator": "res_new_construction_permits", "label": "New residential construction permits", "short": "New construction",
            "status": "scored", "baseline_value": 10.0, "recent_value": 20.0, "change_pct": 1.0, "city_change_pct": -0.1,
            "expected_recent": 9.0, "z_score": 2.5, "baseline_period": "2020–2022", "recent_period": "2023–2025",
        }], "context": {}},
        "what_changed_first": {"ordered": []},
    }

    def test_rejects_invented_numbers(self):
        ok, why = validate("Permits rose to 20, and rents rose 14%.", self.CASE)
        self.assertFalse(ok)
        self.assertIn("14", why)

    def test_rejects_causal_language(self):
        ok, _ = validate("New construction caused prices to change.", self.CASE)
        self.assertFalse(ok)
        ok, _ = validate("Permits rose, which led to change.", self.CASE)
        self.assertFalse(ok)

    def test_accepts_grounded_text(self):
        ok, why = validate("Permits went from 10 to 20 between 2020–2022 and 2023–2025, while the city changed -11%... "
                           .replace("-11%", "-10%"), self.CASE)
        self.assertTrue(ok, why)


if __name__ == "__main__":
    unittest.main()
