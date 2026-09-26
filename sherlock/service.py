"""Read-only service layer over data/processed/*.json.

The FastAPI app (api/main.py) is a thin wrapper around this class, so all
behaviour can be tested without a web server.
"""
from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .llm import explain
from .query import investigate


class NotFound(KeyError):
    pass


class Store:
    def __init__(self, processed_dir: Path | None = None):
        self.dir = Path(processed_dir or config.PROCESSED)
        if not (self.dir / "cases.json").exists():
            raise FileNotFoundError(f"{self.dir}/cases.json not found — run `python -m sherlock.build` first.")

    def _load(self, name: str):
        with open(self.dir / name) as f:
            return json.load(f)

    @cached_property
    def summary(self) -> dict:
        return self._load("summary.json")

    @cached_property
    def areas(self) -> List[dict]:
        return self._load("areas.json")

    @cached_property
    def cases(self) -> List[dict]:
        return self._load("cases.json")

    @cached_property
    def zip_cases(self) -> List[dict]:
        p = self.dir / "zip_cases.json"
        return self._load("zip_cases.json") if p.exists() else []

    @cached_property
    def zip_areas(self) -> List[dict]:
        p = self.dir / "zip_areas.json"
        return self._load("zip_areas.json") if p.exists() else []

    @cached_property
    def zips_geojson(self) -> dict:
        p = self.dir / "zips.geojson"
        if not p.exists():
            return {"type": "FeatureCollection", "features": []}
        geo = self._load("zips.geojson")
        by_id = {a["id"]: a for a in self.zip_areas}
        feats = []
        for f in geo["features"]:
            a = by_id.get(f["properties"]["id"])
            if not a:
                continue  # ZIP areas with no market data are not shown
            f["properties"].update({k: a.get(k) for k in ("level", "anomaly_score", "confidence", "case_id", "top_signal_headline", "name")})
            feats.append(f)
        return {"type": "FeatureCollection", "features": feats}

    @cached_property
    def cases_by_id(self) -> Dict[str, dict]:
        d = {c["id"]: c for c in self.cases + self.zip_cases}
        d.update({c["area_id"]: c for c in self.cases + self.zip_cases})  # allow lookup by area id too
        d["case-metro"] = self.metro
        return d

    @cached_property
    def metro(self) -> dict:
        return self._load("metro.json")

    @cached_property
    def neighborhoods_geojson(self) -> dict:
        geo = self._load("neighborhoods.geojson")
        by_id = {a["id"]: a for a in self.areas}
        for f in geo["features"]:
            a = by_id.get(f["properties"]["id"], {})
            f["properties"].update({k: a.get(k) for k in ("level", "anomaly_score", "confidence", "case_id", "top_signal_headline")})
        return geo

    @cached_property
    def tracts_geojson(self) -> dict:
        return self._load("tracts.geojson")

    @cached_property
    def indicators(self) -> dict:
        return self._load("indicators.json")

    @cached_property
    def sources(self) -> dict:
        return self._load("sources.json")

    @cached_property
    def conflicts(self) -> dict:
        return self._load("conflicts.json")

    # ------------------------------------------------------------------
    def home(self) -> dict:
        s = self.summary
        return {
            "areas_worth_investigating": s["cases_worth_investigating"],
            "areas_analysed": s["areas"], "levels": s["levels"], "confidence": s["confidence"],
            "baseline_years": s["baseline_years"], "recent_years": s["recent_years"],
            "permit_last_date": s["permit_last_date"], "generated_at": s["generated_at"],
            "city_trends": s["city_trends"],
            "top_cases": [self.case_card(c) for c in self.cases if c.get("case_number")][:6],
            "zip": s.get("zip"),
            "top_zip_cases": [self.case_card(c) for c in self.zip_cases if c.get("case_number")][:3],
        }

    def case_card(self, c: dict) -> dict:
        return {"id": c["id"], "case_number": c.get("case_number"), "case_label": c.get("case_label"),
                "geography": c.get("geography", "neighborhood"), "area_id": c["area_id"], "name": c["name"],
                "title": c["title"], "level": c["level"], "anomaly_score": c["anomaly_score"],
                "confidence": c["confidence"]["level"], "why_noticed": [w["headline"] for w in c["why_noticed"]][:3]}

    def list_cases(self, include_all: bool = False, geography: str = "neighborhood") -> List[dict]:
        pool = self.zip_cases if geography == "zip" else self.cases
        return [self.case_card(c) for c in pool if include_all or c.get("case_number")]

    def get_case(self, cid: str) -> dict:
        if cid not in self.cases_by_id:
            raise NotFound(cid)
        return self.cases_by_id[cid]

    def get_area(self, aid: str) -> dict:
        for a in self.areas + self.zip_areas:
            if a["id"] == aid:
                return a
        raise NotFound(aid)

    def case_part(self, cid: str, part: str):
        c = self.get_case(cid)
        mapping = {
            "evidence": lambda: c["evidence"],
            "timeline": lambda: {"series": c["timeline"], "what_changed_first": c["what_changed_first"]},
            "what-changed-first": lambda: c["what_changed_first"],
            "similar": lambda: c["similar_cases"],
            "conflicts": lambda: c["conflicting_evidence"],
            "confidence": lambda: c["confidence"],
            "limitations": lambda: c["limitations"],
        }
        if part not in mapping:
            raise NotFound(part)
        if cid == "case-metro":
            metro_parts = {"evidence": {"signals": c["signals"], "forecast": c["forecast"]},
                           "limitations": c["limitations"]}
            if part not in metro_parts:
                raise NotFound(f"{part} is not available for the metro case")
            return metro_parts[part]
        return mapping[part]()

    def explain_case(self, cid: str) -> dict:
        c = self.get_case(cid)
        if cid == "case-metro":
            return {"text": None, "generated_by": "n/a", "llm_status": "metro case has no narrative template"}
        return explain(c)

    def chat(self, question: str, history=None, case_id=None, mode: str = "basic", use_web: bool = True) -> dict:
        from .drjohn import chat
        return chat(question, self, history=history, case_id=case_id, mode=mode, use_web=use_web)

    def investigate(self, question: str) -> dict:
        return investigate(question, self.cases + self.zip_cases, self.indicators)
