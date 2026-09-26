# Sherlock Homes Mk2: an AI Housing Detective for Pittsburgh

**AI Horizons 2026 · AI for Housing Hackathon · Track 2: Housing Production, Rents & Household Flow Observatory**

> Housing dashboards show you the data. Sherlock Homes shows you where to investigate.

Sherlock scans all 90 City of Pittsburgh neighborhoods. It flags the ones whose housing activity departs from the citywide pattern, then opens a **case file** for each: why it was flagged, the evidence with sources, a timeline, *what changed first*, similar neighborhoods, cross-source conflicts, data confidence, and what the data **cannot** tell us.

The analysis is deterministic (pandas/NumPy). The language layer only explains results and parses questions; it is blocked from adding numbers or claiming causes.

---

## What's new in Mk2

- **ZIP-code market layer (all of Allegheny County).** Each ZIP gets its own case file comparing it with the typical county ZIP on four measures:
  - Zillow home values (ZHVI)
  - Zillow asking rents (ZORI)
  - County valid-sale counts
  - County median sale prices
- **Two independent price sources are cross-checked per ZIP.** Zillow's index is compared with County recorded sale prices, labelled as agree / size differs / direction differs.
- **Neighborhood case files show "The wider market".** This is the ZIP-level evidence for the ZIP codes covering each neighborhood, clearly labelled with how much of the neighborhood each ZIP covers.
- **The map has a Neighborhoods / ZIP codes toggle.**
- **Ask Sherlock now answers rent, home-value, price and sales questions** (at ZIP level). Income and population still return UNKNOWN.
- **2020 Census tracts are linked to neighborhoods.** An optional **Census ACS** loader shows tract-level rent, income, vacancy and renter share once you save the ACS files; see `data/raw/acs/README.md`.

New data used: Allegheny County property sales, Zillow ZIP ZHVI and ZORI, and TIGER 2022 tracts. The Census `variables*.json` / `2024-5yr-api-changes.csv` uploads are variable dictionaries with no estimates, so they are kept for reference in `data/raw/census_metadata/`.

**Large originals.** The raw sales (108 MB) and ZIP home-value (124 MB) files are too big to ship. The zip contains slim extracts (`data/raw/allegheny_sales_slim.csv.gz`, `zip_zhvi_allegheny.csv`, `zip_zori_allegheny.csv`, `tracts_2020_allegheny.geojson`). To rebuild them from your originals, put the original files in `data/raw/original/` and run `python -m sherlock.build`.

## Dr. John: the assistant chatbot

Click **Ask Dr. John** (bottom-right on every page). He answers questions about Pittsburgh housing and about how Sherlock works, and every fact is cited:

- **[D1], [D2]…** come from Sherlock's own data: case files, ZIP and neighborhood signals, dataset definitions and methodology.
- **[W1], [W2]…** come from free web sources that need no API key: Wikipedia, DuckDuckGo Instant Answers and the WPRDC data catalog.

Every answer gets a **fact check**. Any number that doesn't appear in the sources, and any cause-and-effect wording, is flagged in red.

**Which AI writes the answer (none of these needs a paid key):**

1. **Ollama (free, runs on your computer).** Install it from https://ollama.com, then run `ollama pull llama3.2` once. Dr. John detects it automatically while the Ollama app is running.
2. **Anthropic API.** Used only if you set `ANTHROPIC_API_KEY`.
3. **No AI.** Dr. John still works: he lists what he found in the data and on the web, with citations.

Optional settings: `DRJOHN_OLLAMA_MODEL=llama3.2` (pick a model) and `OLLAMA_URL` (default `http://localhost:11434`).

## Quick start (Windows, in Cursor's terminal)

Requirements: **Python 3.10+** and **Node.js 18+**.

```powershell
# 1. Python environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Build the analysis (about 10 seconds). Writes data/processed/ and web/public/data/
#    (Outputs are already included, so this step is optional. To rebuild the neighborhood
#     boundaries too, copy your blockcodes2016.zip into data/raw/ first; without it the
#     existing boundaries are reused.)
python -m sherlock.build

# 3. Run the tests
python -m pytest -q

# 4. Start the API (keep this terminal open)
uvicorn api.main:app --reload --port 8000

# 5. In a second terminal: the web app
cd web
copy .env.local.example .env.local
npm install
npm run dev
```

Open **http://localhost:3000**. API docs are at **http://localhost:8000/docs**.

macOS/Linux: use `source .venv/bin/activate` and `cp` instead of `copy`.

**No API running?** The web app falls back to the exported JSON in `web/public/data/`, so the map and case files still work. Questions and AI rephrasing need the API.

**Optional AI rephrasing:** set `ANTHROPIC_API_KEY` (and optionally `SHERLOCK_LLM_MODEL`) before starting the API. Without it, Sherlock uses its deterministic finding text.

---

## Two views

The header has a **Quick brief / Full dossier** toggle. **Quick brief** (the default) shows each neighborhood's story in plain English with one chart. **Full dossier** shows every statistic, source, method, conflict check and limitation. The choice is remembered in the browser. The app uses a light theme only.

## Demo flow (about 3 minutes)

1. **Home page.** "*N* of 90 neighborhoods worth investigating" is computed at build time. Point out the citywide baseline card.
2. **Open case files.** The map shows darker blue for more unusual areas. The legend states that unusual does not mean bad.
3. Click **Allentown** (Case #003, "The Case of the Construction Surge").
4. **Why Sherlock noticed:**
   - New residential construction permits went from 2 (2020–22) to 31 (2023–25), while the city fell 11%.
   - Declared permit value rose 506% vs. the city's +11%.
   - Renovations rose 80% vs. the city's +12%.
5. **Examine evidence.** Each card shows source file, geography, period and method. Note the burst warning: *17 of 31 recent permits were issued on the same day*, so this is likely one multi-lot project.
6. **Timeline.** Click the chip for each indicator.
7. **What changed first?** Permit value fell below its earlier share in 2022; new construction and demolitions rose above theirs in 2024; renovations in 2025. The panel adds *"Order of change does not establish causation."*
8. **Find similar cases.** Hazelwood and others, with the shared features listed.
9. **Conflicting evidence:**
   - City new-construction permits −11% vs. metro new-construction sales −45%. Reasons: different geography, and permits come before sales.
   - Expand the national checks: Zillow vs. Redfin disagree on sales (−38% vs −28% over 5 years) and on speed of sale.
10. **Data confidence: MODERATE.** Reasons: a single source and concentrated activity. **What Sherlock doesn't know:** rent, prices, incomes, completions.
11. **Ask Sherlock:**
    - *"Where are rents rising faster than incomes?"* returns an honest **UNKNOWN**.
    - *"Where are demolitions rising but renovations falling?"* returns ranked neighborhoods with evidence.
12. **ZIP codes (new in Mk2).** Switch the map toggle to **ZIP codes** and open ZIP 15210. Zillow and County prices both rose but by different amounts ("size differs"), and asking rents rose 21% vs. 14% for the typical county ZIP. Back in Allentown, **The wider market** section shows this as ZIP-level evidence covering 74% of the neighborhood.
13. **Regional backdrop.** The Pittsburgh metro is compared with 894 metros; home values grew +11.4% over 5 years vs. a peer median of +23.9%.

---

## Repository layout

```
sherlock/            analysis package (pure Python + pandas/numpy)
  config.py          sources registry, windows, thresholds
  geo.py             shapefile reader, dissolve, simplify (no GDAL)
  build_geography.py neighborhoods/tracts from 2010 Census blocks
  ingest.py          loaders + cleaning (permit crosswalk for the 2024 system change)
  normalize.py       observations table with provenance
  indicators.py      indicator registry (scored / context, caveats)
  stats.py           robust z, Poisson residual, safe % change, cosine
  analytics.py       signals, anomaly, timeline/onsets, similarity, metro, conflicts, confidence
  narrative.py       deterministic finding + limitations
  llm.py             optional guarded LLM rephrasing
  query.py           natural-language question → structured query
  service.py         read-only store used by the API
  build.py           run everything: python -m sherlock.build
api/main.py          FastAPI app
web/                 Next.js 14 + TypeScript + Tailwind + MapLibre + Recharts
tests/               unit + integration tests (pytest or unittest)
docs/                DATA_DICTIONARY, METHODOLOGY, LIMITATIONS, ARCHITECTURE
data/raw/            source files as received (see DATA_DICTIONARY.md)
data/processed/      build outputs (regenerate any time)
```

## Data used

| Dataset | Level | Period | Role |
|---|---|---|---|
| City of Pittsburgh PLI permits | neighborhood (point) | Jun 2019 – Sep 2026 | **scored** signals |
| City-owned property inventory | neighborhood / 2010 tract | snapshot 2026-09 | vacancy proxy (context) |
| 2010 Census blocks (BlockCodes2016) | block → neighborhood/tract | static | boundaries |
| Zillow Research metro series (7 files) | Pittsburgh MSA vs ~900 metros | 2000–2026 | regional backdrop |
| Redfin national | US | 2012–2026 | cross-source checks |
| Allegheny County property sales (valid sales, 2020+) | ZIP code | 2020 – Aug 2026 | **scored** ZIP market signals |
| Zillow ZIP home values (ZHVI) and rents (ZORI) | ZIP code | 2020–2026 (rents Aug 2023 → Aug 2026) | **scored** ZIP market signals |
| 2020 Census tracts (TIGER 2022) | tract | static | links neighborhoods to ACS 2020+ tracts |
| Zoning, open spaces, parks, voting districts, state boundaries | various | snapshots | not used in scoring |

## Honest scope

- Neighborhood confidence tops out at **MODERATE** because one dataset supplies every neighborhood time series.
- Adding **ACS tract data** (rent, income, vacancy, tenure) is the next step. The tract polygons and the neighborhood↔tract crosswalk are already built for it; see `docs/ARCHITECTURE.md`.
- See `docs/LIMITATIONS.md` for everything Sherlock cannot determine.

*Decision support only: not legal, financial or zoning advice.*
