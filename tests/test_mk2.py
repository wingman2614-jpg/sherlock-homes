"""Mk2 tests: ZIP market layer, county sales cleaning, ACS loader, crosswalks."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

from sherlock import acs, config, zipmarket  # noqa: E402


class TestSalesCleaning(unittest.TestCase):
    def test_valid_recent_nominal_duplicates(self):
        rows = [
            # PARID, ZIP, MUNICODE, MUNIDESC, SALEDATE, RECORDDATE, PRICE, SALECODE, SALEDESC, INSTRTYP, INSTRTYPDESC
            ["1", "15210", 1, "x", "2021-05-01", "2021-05-10", 150000, "0", "VALID SALE", "DE", "DEED"],
            ["1", "15210", 1, "x", "2021-05-01", "2021-05-10", 150000, "0", "VALID SALE", "DE", "DEED"],  # duplicate
            ["2", "15210", 1, "x", "2019-05-01", "2019-05-10", 150000, "0", "VALID SALE", "DE", "DEED"],  # before 2020
            ["3", "15210", 1, "x", "2022-05-01", "2022-05-10", 1, "0", "VALID SALE", "DE", "DEED"],       # nominal price
            ["4", "15210", 1, "x", "2022-05-01", "2022-05-10", 90000, "3", "LOVE AND AFFECTION SALE", "DE", "DEED"],
            ["5", "1521", 1, "x", "2022-05-01", "2022-05-10", 90000, "0", "VALID SALE", "DE", "DEED"],   # bad ZIP
        ]
        cols = ["PARID", "PROPERTYZIP", "MUNICODE", "MUNIDESC", "SALEDATE", "RECORDDATE", "PRICE", "SALECODE", "SALEDESC", "INSTRTYP", "INSTRTYPDESC"]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.csv.gz")
            pd.DataFrame(rows, columns=cols).to_csv(p, index=False, compression="gzip")
            df, qa = zipmarket.load_sales(p)
        self.assertEqual(len(df), 1)
        self.assertEqual(qa["dropped_duplicates"], 1)
        self.assertEqual(qa["dropped_nominal_price"], 1)
        self.assertEqual(qa["dropped_bad_zip"], 1)
        self.assertEqual(qa["valid_sales"], 5)


class TestAcs(unittest.TestCase):
    def test_parse_sentinels_and_rates(self):
        data = [["NAME", "B25064_001E", "B19013_001E", "B25002_001E", "B25002_003E", "B25003_001E", "B25003_003E", "state", "county", "tract"],
                ["t1", "1100", "-666666666", "100", "10", "90", "45", "42", "003", "010300"]]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "acs_2023.json")
            json.dump(data, open(p, "w"))
            df = acs.parse_api_json(p)
        r = df.iloc[0]
        self.assertEqual(r.geoid, "42003010300")
        self.assertEqual(r.median_gross_rent, 1100)
        self.assertTrue(pd.isna(r.median_household_income))  # Census missing sentinel -> unknown, not a number
        self.assertAlmostEqual(r.vacancy_rate, 0.1)
        self.assertAlmostEqual(r.renter_share, 0.5)

    def test_rejects_non_tract_response(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "acs_2023.json")
            json.dump([["NAME", "B25064_001E", "state"], ["PA", "1000", "42"]], open(p, "w"))
            with self.assertRaises(ValueError):
                acs.parse_api_json(p)


@unittest.skipUnless((PROC / "zip_cases.json").exists(), "run python -m sherlock.build first")
class TestZipOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zc = json.load(open(PROC / "zip_cases.json"))
        cls.nc = json.load(open(PROC / "cases.json"))

    def test_zip_signals_have_provenance_and_zip_geography(self):
        for c in self.zc:
            self.assertEqual(c["geography"], "zip")
            for s in c["evidence"]["signals"]:
                self.assertEqual(s["geography"], "zip")
                for k in ("source", "source_file", "period_start", "period_end", "time_resolution"):
                    self.assertIn(k, s)

    def test_min_sales_rules(self):
        for c in self.zc:
            sig = {s["indicator"]: s for s in c["evidence"]["signals"]}
            sc = sig["zip_sales_count"]
            if sc["baseline_value"] < config.MIN_ZIP_SALES_BASE:
                self.assertEqual(sc["status"], "insufficient_data")
                self.assertIsNone(sc["change_pct"])
            mp = sig["zip_median_price"]
            if mp["status"] == "scored":
                self.assertGreaterEqual(mp["baseline_n"], config.MIN_ZIP_SALES_FOR_MEDIAN)
                self.assertGreaterEqual(mp["recent_n"], config.MIN_ZIP_SALES_FOR_MEDIAN)

    def test_rent_window_is_labelled(self):
        for c in self.zc:
            r = {s["indicator"]: s for s in c["evidence"]["signals"]}["zip_rent"]
            self.assertEqual((r["baseline_period"], r["recent_period"]), ("Aug 2023", "Aug 2026"))

    def test_price_conflict_status_valid(self):
        for c in self.zc:
            for x in c["conflicting_evidence"]["neighborhood"]:
                self.assertIn(x["status"], {"agree", "magnitude", "direction", "unknown"})
                self.assertTrue(x["possible_reasons"])

    def test_zip_case_ids_unique_and_labelled(self):
        ids = [c["id"] for c in self.zc]
        self.assertEqual(len(ids), len(set(ids)))
        for c in self.zc:
            if c["case_number"]:
                self.assertTrue(c["case_label"].startswith("Z-"))

    def test_similar_zip_ids_resolve(self):
        area_ids = {c["area_id"] for c in self.zc}
        for c in self.zc:
            for s in c["similar_cases"]:
                self.assertIn(s["area_id"], area_ids)

    def test_neighborhood_market_context_labelled(self):
        for c in self.nc:
            mk = c["evidence"]["context"]["zip_market"]
            self.assertIn("ZIP-code level", mk["note"])
            for z in mk["zips"]:
                self.assertGreaterEqual(z["share_of_neighborhood_land"], 0.10)
            if mk["plain"]:
                self.assertIn("ZIP", mk["plain"])

    def test_crosswalk_shares_sum_to_one(self):
        xw = pd.read_csv(PROC / "neighborhood_zip_crosswalk.csv")
        sums = xw.groupby("neighborhood").share_of_neighborhood_land.sum()
        self.assertTrue(((sums > 0.95) & (sums < 1.001)).all(), sums[(sums <= 0.95) | (sums >= 1.001)])

    def test_zip_text_non_causal(self):
        for c in self.zc:
            text = (c["finding"]["text"] + " " + c["plain"]["headline"]).lower()
            for bad in ("caused", "led to", "drove", "due to", "because of"):
                self.assertNotIn(bad, text)


if __name__ == "__main__":
    unittest.main()
