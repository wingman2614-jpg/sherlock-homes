# Architecture (Mk2)

```
data/raw/  (CSV, GeoJSON, shapefiles as received)
   │
   ▼  sherlock/build_geography.py    2010 blocks → 90 neighborhood + 137 tract polygons (pure Python dissolve)
   ▼  sherlock/ingest.py             clean permits (2024 crosswalk, revoked, duplicates), inventory, Zillow, Redfin
   ▼  sherlock/normalize.py          observations.csv — one row per area × indicator × period, with provenance
   ▼  sherlock/analytics.py          trends → robust z anomaly signals → timelines / onsets → similarity
   │                                 → metro peer comparison → conflicting evidence → confidence
   ▼  sherlock/narrative.py          deterministic finding + limitations (templates over structured evidence)
   ▼  sherlock/build.py              assembles case files → data/processed/*.json (+ web/public/data for offline demo)
   │
   ├─► sherlock/service.py           read-only Store over processed JSON (all API logic, testable without a server)
   │     ├─ sherlock/query.py        NL question → structured query → filter z-scores (optional validated LLM parse)
   │     └─ sherlock/llm.py          optional LLM rephrasing with number/causation guard
   ▼
api/main.py (FastAPI)  ──JSON──►  web/ (Next.js + TypeScript + Tailwind + MapLibre + Recharts)
```

## Design rules

1. **Analysis is deterministic.** The LLM layer only rephrases text or parses questions into a validated schema. It never produces numbers.
2. **Provenance travels with every value.** Every signal carries `source`, `source_id`, `source_file`, `geography`, `period_start`, `period_end` and `time_resolution`.
3. **UNKNOWN is a value.** Insufficient data is labelled explicitly and never zero-filled into scores.
4. **Geographies do not mix.** Neighborhood, city, metro and national evidence stay separate and labelled.

## Processed outputs (`data/processed/`)

| file | contents |
|---|---|
| `neighborhoods.geojson`, `tracts.geojson` | dissolved polygons with id, name, land area, bbox, centroid |
| `neighborhood_tract_crosswalk.csv` | land-area shares between neighborhoods and 2010 tracts (ready for ACS) |
| `observations.csv` | normalized long table with provenance |
| `areas.json` | per-neighborhood map summary (level, score, confidence, top signal, case id) |
| `cases.json` | full case files (evidence, timeline, what changed first, similar, conflicts, confidence, finding, limitations) |
| `metro.json` | Pittsburgh MSA vs peer metros ("The Regional Backdrop") |
| `conflicts.json` | national and city-vs-metro cross-source comparisons |
| `indicators.json`, `sources.json` | registries |
| `summary.json`, `geography_qa.json` | run summary, QA counts, dissolve diagnostics |

## API (FastAPI, `api/main.py`)

| method | path | returns |
|---|---|---|
| GET | `/health` | status + build time |
| GET | `/summary` | home-page summary (areas worth investigating, city trends, top cases) |
| GET | `/areas`, `/areas/{id}` | map summaries |
| GET | `/geo/neighborhoods`, `/geo/tracts` | GeoJSON (neighborhoods merged with levels) |
| GET | `/cases?include_all=` | case cards |
| GET | `/cases/{id}` | full case file (`case-003`, `file-<area>`, an area id, or `case-metro`) |
| GET | `/cases/{id}/evidence` · `/timeline` · `/what-changed-first` · `/similar` · `/conflicts` · `/confidence` · `/limitations` | case parts |
| GET | `/cases/{id}/explain` | finding, rephrased by the LLM if configured (guarded) |
| GET | `/metro`, `/conflicts`, `/indicators`, `/sources` | registries and context |
| POST | `/investigate` `{question}` | structured query + matching neighborhoods |

## Frontend (`web/`)

* `/`: hero, count of areas worth investigating (from data), citywide baseline, top cases
* `/investigate?case=<id>`: MapLibre map (left) + case file (right) + Ask Sherlock search (top)
* If the API is unreachable, the web app falls back to `web/public/data/*.json` (offline demo mode; questions and AI rephrasing are disabled).

## Adding a dataset (e.g. ACS)

1. Put the file in `data/raw/` and register it in `config.SOURCES`.
2. Add a loader in `ingest.py` and emit observations in `normalize.py` with the correct `geography`, which is `census_tract_2010` for ACS 2015–19.
3. Register indicators in `indicators.py` (`scored`, `method`, caveats).
4. Use `neighborhood_tract_crosswalk.csv` to **show** tract values beside a neighborhood, labelled as tract-level. Aggregating medians across tracts is not valid.
5. Add cross-source comparisons in `analytics.py`; confidence will then be able to reach HIGH.


## Mk2 modules

* `sherlock/prepare_extracts.py`: slims large originals in `data/raw/original/` into shippable extracts.
* `sherlock/zipmarket.py`: ZIP signals, timelines, similarity, the ZHVI-vs-sales conflict, confidence, text, and the neighborhood market context.
* `sherlock/acs.py`: optional Census API loader (tract level).
* Outputs: `zip_cases.json`, `zip_areas.json`, `zips.geojson`, `neighborhood_zip_crosswalk.csv`, `neighborhood_tract2020_crosswalk.csv`.
* API: `GET /geo/zips`, `GET /zip-areas`, `GET /cases?geography=zip`. ZIP case ids look like `zcase-001` or `zipfile-15210`.

## Dr. John (chat)

* `sherlock/drjohn.py`, `POST /chat {question, history, case_id, mode, use_web}` → `{answer, provider, sources[], verification}`.
* **Retrieval (deterministic).** Pulls the open case file, any neighborhoods or ZIPs named in the question, Sherlock's structured search results, the overview, dataset and method descriptions, and metro context. With web search on, it also fetches Wikipedia search and summary, DuckDuckGo Instant Answer, and the WPRDC CKAN `package_search`.
* **Generation.** Anthropic, if a key is set; otherwise Ollama on localhost; otherwise a no-model answer that lists the retrieved evidence.
* **Verification.** Numbers not present in the evidence and causal phrases are flagged in the response and shown in the UI.
