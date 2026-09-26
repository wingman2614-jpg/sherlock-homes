"""Integration checks on the built outputs (run `python -m sherlock.build` first).

These verify provenance, geographic/temporal labelling and graceful failure.
"""
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

from sherlock.service import NotFound, Store  # noqa: E402

PROVENANCE = {"source", "source_id", "source_file", "geography", "period_start", "period_end", "time_resolution"}


@unittest.skipUnless((PROC / "cases.json").exists(), "run python -m sherlock.build first")
class TestOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store()
        cls.cases = cls.store.cases
        cls.obs = pd.read_csv(PROC / "observations.csv")

    def test_every_signal_keeps_provenance(self):
        for c in self.cases:
            for s in c["evidence"]["signals"]:
                self.assertTrue(PROVENANCE <= set(s), f"{c['name']} {s['indicator']} missing provenance")

    def test_no_duplicate_observations(self):
        self.assertFalse(self.obs.duplicated(["area_id", "indicator", "period_start", "period_end"]).any())

    def test_temporal_resolution_preserved(self):
        res = self.obs.groupby("geography")["time_resolution"].agg(lambda x: set(x))
        self.assertIn("monthly", res["metro"])
        self.assertTrue(any("annual" in r for r in res["neighborhood"]))
        self.assertTrue(any("snapshot" in r for r in res["neighborhood"]))

    def test_partial_years_flagged(self):
        flagged = self.obs[self.obs["flags"].fillna("").astype(str).str.contains("partial_year")]
        self.assertEqual(set(flagged.period_start.str[:4]), {"2019", "2026"})

    def test_geographic_mismatch_is_labelled(self):
        c = self.cases[0]
        metro = c["evidence"]["context"]["metro"]
        self.assertIn("not a neighborhood", metro["note"].lower())
        for m in metro["signals"]:
            self.assertIn("metro", m["geography"].lower())
        for s in c["evidence"]["signals"]:
            self.assertEqual(s["geography"], "neighborhood")

    def test_insufficient_data_is_unknown_not_zero(self):
        insufficient = [s for c in self.cases for s in c["evidence"]["signals"] if s["status"] == "insufficient_data"]
        self.assertTrue(insufficient)
        for s in insufficient:
            self.assertNotIn("z_score", s)

    def test_small_bases_have_no_percent_change(self):
        for c in self.cases:
            for s in c["evidence"]["signals"]:
                if s["indicator"] != "res_permit_value" and s["baseline_value"] < 5:
                    self.assertIsNone(s["change_pct"])

    def test_cases_numbered_and_findings_are_non_causal(self):
        numbered = [c for c in self.cases if c.get("case_number")]
        self.assertEqual([c["case_number"] for c in numbered], list(range(1, len(numbered) + 1)))
        for c in self.cases:
            text = c["finding"]["text"].lower()
            for bad in ("caused", "led to", "drove", "due to", "because of"):
                self.assertNotIn(bad, text)
            self.assertIn("does not establish", text)

    def test_what_changed_first_warns_about_causation(self):
        for c in self.cases:
            self.assertIn("does not establish causation", c["what_changed_first"]["caution"])

    def test_every_case_has_confidence_reasons_and_limitations(self):
        for c in self.cases:
            self.assertIn(c["confidence"]["level"], {"HIGH", "MODERATE", "LOW"})
            self.assertTrue(c["confidence"]["factors"])
            self.assertTrue(c["limitations"])

    def test_geojson_matches_areas(self):
        geo = self.store.neighborhoods_geojson
        self.assertEqual(len(geo["features"]), len(self.store.areas))
        for f in geo["features"]:
            self.assertIn(f["geometry"]["type"], {"Polygon", "MultiPolygon"})

    def test_service_fails_gracefully(self):
        with self.assertRaises(NotFound):
            self.store.get_case("does-not-exist")
        with self.assertRaises(NotFound):
            self.store.case_part("case-metro", "timeline")
        r = self.store.investigate("")
        self.assertEqual(r["results"], [])

    def test_unsupported_questions_return_unknown(self):
        # Mk2: rents are answerable at ZIP level; incomes remain UNKNOWN
        r = self.store.investigate("Where are rents rising faster than incomes?")
        self.assertTrue(any("UNKNOWN" in n and "income" in n for n in r["notes"]))
        for res in r["results"]:
            self.assertTrue(res["area_id"].startswith("zip-"))
        r = self.store.investigate("Where is population growing?")
        self.assertEqual(r["results"], [])
        self.assertTrue(any("UNKNOWN" in n for n in r["notes"]))

    def test_question_results_come_from_z_scores(self):
        r = self.store.investigate("Where are demolitions rising?")
        for res in r["results"]:
            self.assertGreaterEqual(res["z_scores"]["demolition_permits"], 0.5)

    def test_plain_summary_is_present_and_non_causal(self):
        for c in self.cases:
            p = c["plain"]
            self.assertTrue(p["headline"])
            text = " ".join([p["headline"], *p["bullets"], p["timing"] or "", p["confidence"]]).lower()
            for bad in ("caused", "led to", "drove", "due to", "because of", "resulted in"):
                self.assertNotIn(bad, text)
            if c["level"] in ("HIGH", "MEDIUM"):
                self.assertTrue(p["bullets"], c["name"])

    def test_national_conflict_detected(self):
        nat = {c["concept"]: c for c in self.store.conflicts["national"]}
        self.assertIn(nat["Speed of sale"]["status"], {"magnitude", "direction"})


if __name__ == "__main__":
    unittest.main()
