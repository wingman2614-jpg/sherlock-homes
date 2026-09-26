"""Sherlock Homes API.

Run:  uvicorn api.main:app --reload --port 8000     (from the repo root)

All responses are read from data/processed/ (built by `python -m sherlock.build`).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sherlock.service import NotFound, Store  # noqa: E402

app = FastAPI(title="Sherlock Homes Mk2 API", version="2.0.0",
              description="AI housing detective for Pittsburgh. Findings are computed deterministically; "
                          "language models only rephrase or parse, never invent values.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("SHERLOCK_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_methods=["*"], allow_headers=["*"],
)

_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        try:
            _store = Store()
        except FileNotFoundError as e:
            raise HTTPException(503, str(e))
    return _store


def _get(fn, *args):
    try:
        return fn(*args)
    except NotFound as e:
        raise HTTPException(404, f"Not found: {e}")


@app.get("/health")
def health():
    s = store()
    return {"status": "ok", "version": "Mk2", "generated_at": s.summary["generated_at"]}


@app.get("/")
def root():
    return {"name": "Sherlock Homes Mk2 API", "docs": "/docs"}


@app.get("/summary")
def summary():
    return store().home()


@app.get("/areas")
def areas():
    return store().areas


@app.get("/areas/{area_id}")
def area(area_id: str):
    return _get(store().get_area, area_id)


@app.get("/geo/neighborhoods")
def geo_neighborhoods():
    return store().neighborhoods_geojson


@app.get("/geo/zips")
def geo_zips():
    return store().zips_geojson


@app.get("/zip-areas")
def zip_areas():
    return store().zip_areas


@app.get("/geo/tracts")
def geo_tracts():
    return store().tracts_geojson


@app.get("/cases")
def cases(include_all: bool = False, geography: str = "neighborhood"):
    return store().list_cases(include_all, geography)


@app.get("/cases/{case_id}")
def case(case_id: str):
    return _get(store().get_case, case_id)


@app.get("/cases/{case_id}/{part}")
def case_part(case_id: str, part: str):
    if part == "explain":
        return _get(store().explain_case, case_id)
    return _get(store().case_part, case_id, part)


@app.get("/metro")
def metro():
    return store().metro


@app.get("/conflicts")
def conflicts():
    return store().conflicts


@app.get("/indicators")
def indicators():
    return store().indicators


@app.get("/sources")
def sources():
    return store().sources


class Question(BaseModel):
    question: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []
    case_id: str | None = None
    mode: str = "basic"
    use_web: bool = True


@app.post("/chat")
def chat(req: ChatRequest):
    """Dr. John: answers from Sherlock data + free web sources, with citations."""
    return store().chat(req.question, [m.model_dump() if hasattr(m, "model_dump") else dict(m.__dict__) for m in req.history],
                        req.case_id, req.mode, req.use_web)


@app.post("/investigate")
def investigate(q: Question):
    return store().investigate(q.question[:500])
