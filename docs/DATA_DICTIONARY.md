# Sherlock Homes — Data Dictionary (Phase 1)

Inventory of every file placed in `data/raw/` as of 2026-09-26. All counts below were computed from the files themselves; nothing is assumed.

## 0. Headline finding

**No dataset in this drop is finer than the metro (MSA) level, except two boundary files that contain no housing measures.**

| What the project brief expected | Present? |
|---|---|
| Census tracts / tract GEOIDs | **No** |
| ACS (rent, income, households, tenure, vacancy, population) | **No** |
| Pittsburgh PLI / building permits | **No** |
| Allegheny County property sales / assessments | **No** |
| Zillow **rent** (ZORI / ZORDI) | **No** — all Zillow files are for-sale market metrics |
| Vacancy of any kind | **No** |
| Zillow metro-level for-sale metrics | Yes (7 files + 1 forecast) |
| Redfin metrics | Yes, but **national only** (no metro, no Pittsburgh) |
| Allegheny County open spaces (parks, cemeteries, gardens) | Yes (polygons, no housing values) |
| US state boundaries (TIGER 2025) | Yes (state level only) |

Pittsburgh appears in the data as exactly **one geographic unit**: `Pittsburgh, PA` MSA (Zillow RegionID `394982`, SizeRank 27). That MSA covers 7 counties (Allegheny, Armstrong, Beaver, Butler, Fayette, Washington, Westmoreland), so no value here describes the City of Pittsburgh or any neighborhood.

---

## 1. File-by-file inventory

### Shared layout of all Zillow metro files ("wide" format)

| Column | Type | Meaning |
|---|---|---|
| `RegionID` | int | Zillow's internal region ID. Unique per row in every file. **Join key across Zillow files** (verified: identical ID sets where rows overlap). Not a Census CBSA code. |
| `SizeRank` | int | Zillow's size ranking (0 = United States, 1 = New York …). Pittsburgh = 27. |
| `RegionName` | str | e.g. `Pittsburgh, PA`. Human-readable; not a Census name. |
| `RegionType` | str | `country` (1 row) or `msa`. |
| `StateName` | str | 2-letter state of the MSA's principal city. Null for the US row. Multi-state metros carry one state only. |
| `YYYY-MM-DD` | float | One column per month, dated to the **last day** of the month. |

No duplicate rows or duplicate `RegionID`s in any Zillow file.

---

### 1.1 `9a1c60bd-f9f7-4aba-aeb7-af8c3aaa44e5.csv` — **likely Zillow Home Value Index (ZHVI)**

| Property | Value |
|---|---|
| Format | CSV, wide |
| Rows | 895 (1 country + 894 MSAs) |
| Columns | 325 (5 id + 320 months) |
| Coverage | 2000-01-31 → 2026-08-31, monthly |
| Geography | Metro (MSA) + US |
| Missing | 17.2% of cells overall (mostly early years for small metros); Pittsburgh complete (320/320); 892 rows complete for last 5 yrs |
| Values | $48,084 – $1,601,701; Pittsburgh Aug-2026 = $232,122, US = $368,697 |

**Data-quality issue: the filename is a UUID, so the exact product is unverified.** Row set, date range and dollar magnitudes match Zillow's `Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv` (typical home value, mid-tier, smoothed, seasonally adjusted), and it shares exactly the same 895 RegionIDs as the ZHVI forecast file. Sherlock will label it **"Home value index (inferred ZHVI — please confirm source)"** until confirmed.

| Field | Meaning | Units | Geo | Time | Missing concerns | Sherlock use |
|---|---|---|---|---|---|---|
| monthly columns | Typical home value (inferred ZHVI mid-tier, SA) | USD | MSA | Monthly | Early-year gaps for small metros | **HOUSING COST** — YoY, 3-yr, 5-yr change; growth acceleration timing; peer z-score |

---

### 1.2 `Metro_invt_fs_uc_sfrcondo_sm_month.csv` — Zillow for-sale inventory

| Property | Value |
|---|---|
| Rows / cols | 928 / 107 (1 country + 927 MSAs) |
| Coverage | 2018-03-31 → 2026-08-31, monthly (102 months) |
| Missing | 1.3% of cells; Pittsburgh complete |
| Values | 4 – 1,733,393 listings; Pittsburgh Aug-2026 = 8,193 |

| Field | Meaning | Units | Geo | Time | Missing concerns | Use |
|---|---|---|---|---|---|---|
| monthly columns | Count of unique for-sale listings active during month (`sm` = smoothed) | listings | MSA | Monthly, smoothed | Tiny metros have counts < 50 → unstable % changes | **MARKET ACTIVITY / SUPPLY (resale)** — YoY % change |

---

### 1.3 `Metro_market_temp_index_uc_sfrcondo_month.csv` — Zillow Market Heat Index

| Property | Value |
|---|---|
| Rows / cols | 928 / 109 |
| Coverage | 2018-01-31 → 2026-08-31 (104 months) |
| Missing | 2.4%; Pittsburgh complete |
| Values | −120 to 279 (index). 1,001 cells negative across 123 metros (e.g. Cincinnati). Pittsburgh Aug-2026 = 44, US = 51 |

| Field | Meaning | Units | Geo | Time | Missing concerns | Use |
|---|---|---|---|---|---|---|
| monthly columns | Composite seller-vs-buyer market index (higher = hotter for sellers; Zillow describes ~70+ as seller's, ~<30 as buyer's market) | index points | MSA | Monthly | **Composite of other Zillow inputs** → must not be double-counted alongside inventory/days-to-pending in the anomaly score; negative values are unexplained in metadata | **MARKET ACTIVITY** — absolute point change; context indicator |

---

### 1.4 `Metro_mean_doz_pending_uc_sfrcondo_sm_month.csv` — Mean days to pending

| Property | Value |
|---|---|
| Rows / cols | 777 / 107 |
| Coverage | 2018-03-31 → 2026-08-31 |
| Missing | **36.2%** of cells; only 486/777 metros complete for last 5 yrs. Pittsburgh complete |
| Values | 7 – 258 days; Pittsburgh Aug-2026 = 37, US = 53 |

| Field | Meaning | Units | Geo | Time | Missing concerns | Use |
|---|---|---|---|---|---|---|
| monthly columns | Mean days from listing to pending sale (smoothed) | days | MSA | Monthly | Heavy missingness → peer group shrinks to ~578 metros for YoY | **MARKET ACTIVITY** — absolute day change |

---

### 1.5 `Metro_new_con_sales_count_raw_uc_sfrcondo_month.csv` — New-construction sales

| Property | Value |
|---|---|
| Rows / cols | 423 / 108 |
| Coverage | 2018-01-31 → **2026-07-31** (one month shorter than others) |
| Missing | 27.2%; only 284/423 metros complete for last 5 yrs. Pittsburgh complete |
| Values | 5 – 74,488; Pittsburgh Jul-2026 = 76 |
| Pittsburgh annual totals | 2018: 2,787 · 2019: 2,843 · 2020: 2,660 · 2021: 2,466 · 2022: 1,927 · 2023: 1,510 · 2024: 1,340 · 2025: 1,019 · 2026 (Jan–Jul): 605 |

| Field | Meaning | Units | Geo | Time | Missing concerns | Use |
|---|---|---|---|---|---|---|
| monthly columns | Count of **sales of newly constructed homes** (raw, not smoothed / not SA) | sales | MSA | Monthly | Seasonal & noisy → use trailing-12-month sums; small counts; **is sales of new homes, not permits, starts, or completions** | **HOUSING SUPPLY (proxy)** — TTM YoY %, multi-year trend. The only supply-side signal in the drop. |

---

### 1.6 `Metro_new_homeowner_income_needed_downpayment_0.20_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv`

| Property | Value |
|---|---|
| Rows / cols | 390 / 181 |
| Coverage | 2012-01-31 → 2026-08-31 (176 months) |
| Missing | 0.3%; all 390 rows complete for last 5 yrs |
| Values | $10,890 – $2,800,922; Pittsburgh Aug-2026 = $67,279, US = $100,006 |

| Field | Meaning | Units | Geo | Time | Missing concerns | Use |
|---|---|---|---|---|---|---|
| monthly columns | Annual household income needed so that mortgage payment on a typical (mid-tier) home with 20% down stays within an affordability threshold (Zillow methodology; threshold not stated in file) | USD / year | MSA | Monthly, smoothed, SA | Modeled value that combines price **and mortgage rates** — not observed income. Only 390 metros | **ECONOMICS / AFFORDABILITY** — YoY % change; separates rate-driven vs price-driven affordability shifts when compared with 1.1 |

---

### 1.7 `Metro_sales_count_now_uc_sfrcondo_month.csv` — Sales count (nowcast)

| Property | Value |
|---|---|
| Rows / cols | 301 / 228 |
| Coverage | 2008-02-29 → 2026-08-31 (223 months) |
| Missing | 0.5%; Pittsburgh complete |
| Values | 20 – 587,925; Pittsburgh Aug-2026 = 2,780 |

| Field | Meaning | Units | Geo | Time | Missing concerns | Use |
|---|---|---|---|---|---|---|
| monthly columns | Estimated number of home sales (`now` = **nowcast**; recent months are model estimates that get revised) | sales | MSA | Monthly, not SA | Only 300 metros; recent months provisional; seasonal → use TTM | **MARKET ACTIVITY** — TTM YoY %, multi-year trend |

---

### 1.8 `Metro_zhvf_growth_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv` — Zillow home value **forecast**

| Property | Value |
|---|---|
| Rows / cols | 895 / 9 (adds `BaseDate` = 2026-08-31) |
| Columns | `2026-09-30`, `2026-11-30`, `2027-08-31` → 1-, 3-, 12-month-ahead forecast growth |
| Missing | 0% |
| Values | −3.9 to +6.8 (%); Pittsburgh: +0.3 / +1.0 / +0.9; US: +0.2 / +0.6 / +1.4 |

| Field | Meaning | Units | Geo | Time | Missing concerns | Use |
|---|---|---|---|---|---|---|
| horizon columns | Zillow's predicted % change in home value index | % | MSA | Forecast from 2026-08 | **This is a model prediction, not an observation** | **OTHER** — display-only "outlook" in Case File, never in anomaly score or timeline |

---

### 1.9 `redfin_housing_market_monthly_all_country_key_metrics_2012_Jan_to_2026_Aug.csv`

| Property | Value |
|---|---|
| Format | CSV, long (one row per month) |
| Rows / cols | 176 / 28 |
| Coverage | 2012-01 → 2026-08 monthly; `LAST UPDATED` 2026-09-03 |
| Geography | **National only** (`REGION TYPE` = Country, `REGION NAME` = National) |
| Missing | `REGION ID` 100% null; `MEDIAN SALE PRICE NSA MOM (%)` 100% null |
| Duplicates | none |
| Verified | Recomputed `HOMES SOLD YOY (%)` from raw counts — matches |

| Field | Meaning | Units | Use |
|---|---|---|---|
| `PERIOD BEGIN`, `PERIOD END` | Month bounds | date | Time key |
| `HOMES SOLD` (+ MOM/YOY %) | Closed sales | count | Cross-check Zillow sales (national) |
| `MEDIAN SALE PRICE NSA ($)` (+ YOY %) | Median closed price, not seasonally adjusted | USD | Cross-check home value index (national) |
| `MEDIAN DAYS ON MARKET (DAYS)` (+ MOM/YOY **in days**) | Median DOM | days | Cross-check Zillow days-to-pending |
| `NEW LISTINGS` (+ %) | New listings in month | count | National context |
| `ACTIVE LISTINGS` (+ %) | Active listings | count | Cross-check Zillow inventory |
| `PENDING SALES` (+ %) | Pending sales | count | National context |
| `MEDIAN NEW LISTING PRICE PER SQ.FT. ($)` (+ %) | Asking $/sqft | USD/sqft | National context |

Sherlock use: **benchmark + conflicting-evidence source at national level only.** It cannot say anything about Pittsburgh.

---

### 1.10 `redfin_property_types_monthly_all_country_key_metrics_2012_Jan_to_2026_Aug.csv`

| Property | Value |
|---|---|
| Rows / cols | 704 / 27 (176 months × 4 property types) |
| `PROPERTY TYPE` | Single Family Residential, Condo/Co-op, Townhouse, Multi-Family (2-4 Units) |
| `IS SEASONALLY ADJUSTED` | True for SFR/Condo/Townhouse (528 rows), **False for Multi-Family (176)** |
| Geography | National only |
| Missing | `REGION ID` 100%; `MEDIAN SALE PRICE NSA MOM (%)` 100%; the other MOM % fields 176 nulls |

**Data-quality issues:** (a) seasonal adjustment flag differs by property type, so types aren't directly comparable month to month; (b) the column is named `MEDIAN SALE PRICE NSA` even for rows flagged as SA; (c) `MEDIAN DAYS ON MARKET MOM/YOY` are **%** here but **days** in 1.9 — same concept, different units.

Sherlock use: national context only ("small multifamily sales trend nationally"). Not in the MVP scoring.

---

### 1.11 `Allegheny_County_Open_Spaces_*.zip` — Shapefile

| Property | Value |
|---|---|
| Records | 1,426 polygons |
| CRS | NAD83 / Pennsylvania South (ftUS), EPSG:2272 → must reproject to EPSG:4326 for web maps |
| Fields | `MUNICIPALI` (146 municipalities; City of Pittsburgh = 371 features), `FULL_ADDRE` (51 blank), `NAME` (3 blank), `TYPE` (12 values; 1 blank) |
| `TYPE` values | Municipal Park 752, Cemetery 308, Community Garden 158, Private Park 65, "CONSERVATIION AREA" (sic) 60, Golf Course 37, … |
| Duplicates | 2 duplicate attribute rows |
| Time | None (metadata stamped 2022-08-08 / exported 2026-07-02) |

Sherlock use: **map context layer only** (basemap overlay). Contains no housing variable and no date, so it cannot participate in trend or anomaly analysis. `MUNICIPALI` is the only sub-county identifier anywhere in the drop.

### 1.12 `tl_2025_us_state.zip` — Census TIGER/Line states

| Property | Value |
|---|---|
| Records | 56 (states + DC + territories) |
| CRS | NAD83 geographic (EPSG:4269) |
| Keys | `GEOID`/`STATEFP` (2-digit FIPS), `STUSPS`, `NAME` — all unique, no missing |

Sherlock use: state outline for the metro-comparison map; joins to Zillow `StateName` via `STUSPS`. **Not** tracts, counties, or CBSAs — Zillow metros have no polygon in this drop.

---

## 2. Variable classification

| Category | Indicators available | Source | Geography |
|---|---|---|---|
| HOUSING COST | Home value index (inferred ZHVI); Redfin median sale price, $/sqft (national) | 1.1, 1.9 | MSA; national |
| HOUSING SUPPLY | New-construction sales (proxy only); for-sale inventory (resale supply) | 1.5, 1.2 | MSA |
| MARKET ACTIVITY | Sales count (nowcast), days to pending, market heat index; Redfin sold/pending/new/active listings, DOM | 1.7, 1.4, 1.3, 1.9 | MSA; national |
| VACANCY | **none** | — | — |
| HOUSEHOLDS | **none** | — | — |
| DEMOGRAPHICS | **none** | — | — |
| ECONOMICS / AFFORDABILITY | Income needed to buy (20% down) — modeled, not observed income | 1.6 | MSA |
| OTHER | Home value forecast (model output); open space polygons; state boundaries | 1.8, 1.11, 1.12 | MSA; parcel-ish polygons; state |
| RENT | **none** | — | — |

## 3. Compatibility

**Geographic.** All Zillow files share `RegionID` → clean joins at MSA level. Redfin has no region ID and is national only → it can join to the Zillow `United States` row by month, nothing else. Open spaces and state boundaries have no key that links to any housing value. There is no tract, ZIP, county, or neighborhood geography anywhere.

**Temporal.** All housing series are monthly and align by calendar month (Zillow = month-end date, Redfin = PERIOD END). Common window for all seven Zillow observational series: **2018-03 → 2026-07**. Home value (2000–) and sales (2008–) allow longer history. Smoothed (`sm`), seasonally adjusted (`sa`), raw, and nowcast series are mixed and must be labeled per indicator.

**Cross-source overlap usable for "Conflicting Evidence"** (national, computed from the files):

| Concept | Zillow (US row) | Redfin (National) | Aug-2021 → Aug-2026 |
|---|---|---|---|
| Sales | sales_count_now | HOMES SOLD | Zillow −38.0% vs Redfin −27.8% |
| Inventory | invt_fs | ACTIVE LISTINGS | +31.2% vs +29.5% (agree) |
| Price | home value index | MEDIAN SALE PRICE | +20.3% vs +18.6% (agree) |
| Speed | mean days to pending | median days on market | 22→53 days vs 31→50 days |

Different definitions (mean-to-pending vs median-to-close; index vs median; nowcast vs recorded) explain these, and Sherlock can cite them from the column names.

---

# Addendum (second upload, 2026-09-26): Pittsburgh city-level files

These four files add the first **sub-metro** Pittsburgh geography: 90 City of Pittsburgh neighborhoods, 28 ZIPs, 32 wards, 9 council districts, and (inventory only) 131 census-tract GEOIDs. They cover the **City of Pittsburgh only**, not Allegheny County or the metro.

## A1. `pli_permits.csv` (uploaded as `2.csv`) — City of Pittsburgh PLI permits

| Property | Value |
|---|---|
| Rows / cols | 65,378 / 19; `permit_id` unique; no duplicate rows (1,185 share parcel+date+type+description) |
| Coverage | **2019-06-03 → 2026-09-21** (2019 and 2026 are partial years) |
| Geography | Point (`latitude`/`longitude`, 0 nulls, all within city bounds) + `neighborhood` (90), `zip_code` (28), `ward`, `council_district`, `parcel_num` |
| Missing | `owner_name` 57%, `work_description` 35%, `contractor_name` 18%, `work_type` 208 |

| Field | Meaning | Units | Concerns | Sherlock use |
|---|---|---|---|---|
| `issue_date` | Date permit issued | date | Issue ≠ start ≠ completion | Monthly/annual time key |
| `permit_type` | 14 types: ELECTRICAL 20.5k, BUILDING 17.8k, Building & Development Application 9.2k, MECHANICAL 8.2k, Demolition 1.3k, … | category | **System change in 2024:** `BUILDING` (→2024) replaced by `Building & Development Application` (2024→). Must be harmonized or trends show a fake break | Filter to building-type permits for construction signals (avoid counting the electrical/mechanical permits that accompany the same project) |
| `work_type` | 20 values, with **two vocabularies** (e.g. `NEW CONSTRUCTION` vs `New Construction`; `ADDITION / ALTERATION` vs `Existing (alteration/addition)`) | category | Needs a crosswalk | New construction / alteration / demolition classification |
| `commercial_or_residential` | Residential 40.8k / Commercial 24.5k | category | 66 nulls | Residential filter |
| `total_project_value` | Declared project value | USD | 2,271 zeros, 1 negative, max $162M — very skewed | Investment signal: use median & sum, log scale, never mean |
| `status` | Completed 43.9k, Issued 15.4k, Expired 5.1k, Revoked 712, … | category | Expired/revoked permits never built | Exclude revoked; flag expired |
| `work_description` | Free text | text | 35% blank; **no dwelling-unit field** — only 207 descriptions mention unit counts | Display only; cannot measure units added |

**Key counts (building-type permits, residential new construction):** 2019: 14 (partial) · 2020: 83 · 2021: 96 · 2022: 99 · 2023: 83 · 2024: 74 · 2025: 57 · 2026: 58 (Jan–Sep). Only **16 of 90 neighborhoods** had ≥5 such permits in 2021–23 → small-number problem for % change.
**Demolition permits:** 98 / 165 / 163 / 209 / 208 / 123 / 139 / 195 (2019–2026).

Categories: HOUSING SUPPLY (new construction, demolition), MARKET ACTIVITY / REINVESTMENT (alterations, project value).

## A2. `city_property_inventory.csv` (uploaded as `1.csv`) — City-owned property inventory

| Property | Value |
|---|---|
| Rows / cols | 12,477 / 24; `id` unique; `pin` 22 null |
| Owner | 100% `City of Pittsburgh` |
| Geography | Point + `census_tract` (**full 11-digit GEOID**, e.g. 42003562500; 258 null; 131 tracts) + `neighborhood_name` (89) + ward, council district |
| Time | **Snapshot.** `acquisition_date` 1900–2025 with invalid values (2027 ×2, 2090 ×1), 578 null; `last_updated` 2016-11 → 2026-09 |

| Field | Meaning | Concerns | Sherlock use |
|---|---|---|---|
| `class` | Vacant Land 11,344 / Building 859 / Not Classified 274 | — | **VACANCY (proxy):** count of city-owned vacant parcels per neighborhood/tract. **Not** a vacancy rate and not all vacant land (private vacant land is absent) |
| `current_status` | Hold for Study 4,731 · Available for Sale 4,181 · Permanent City Ownership 2,626 · Sale Pending 653 … | Case variants (`Hold for Study` / `Hold For Study`) | Pipeline of land available for reuse |
| `inventory_type` | Public Sale, URA Transfer, Park, Greenway… | Case variants | Exclude parks/greenways from "vacant-land" signal |
| `acquisition_method` | Treasurer Sale 10,238 (tax delinquency) · Purchase 569 · … | 1,436 null | Tax-delinquency history proxy |
| `acquisition_date` | When City acquired | Invalid future dates; 69% acquired before 2010 | Recent-acquisition counts only (2015+), labeled low confidence |
| `zoned_as` | Zoning code | 132 null | Join to zoning legend |
| `parc_sq_ft` | Parcel area | 176 null | Land area of city-held vacant land |

## A3. `zoning.geojson` — City of Pittsburgh zoning polygons

1,069 features (Polygon/MultiPolygon), CRS84 (lon/lat — web-map ready), **1 null geometry**. Fields: `zon_new` (57 codes), `full_zoning_type`, `legendtype` (25), `municode` link, `status` (Approved/Pending). Edit dates 2018. **Snapshot, no history.** Use: map context layer; share of residential vs. commercial zoning per area (requires spatial overlay).

## A4. `zoning_attributes.csv` (uploaded as `3.csv`)

**Exactly 1,000 rows** (OBJECTID 1–1014) vs 1,069 in the GeoJSON → **truncated export** (1,000-row download limit). Same attributes as A3, no geometry. **Redundant — drop in favour of `zoning.geojson`.**

## Addendum compatibility notes

- **Common key between permits and inventory: `neighborhood` / `neighborhood_name`** — identical names (permits add only `Regent Square`). ✅
- Inventory has tract GEOIDs; permits do not, but permit points can be assigned to tracts **only if tract polygons are provided**.
- **No neighborhood or tract polygons are in the upload** → a neighborhood choropleth map cannot yet be drawn.
- Zillow metro data (2018–2026, monthly) overlaps permits (2019-06 → 2026-09) in time but is 7-county metro geography → context layer only, labelled as such.

# Addendum 2 (third upload): Allegheny County park outlines

- `county_park_outlines.geojson` (uploaded as `park_outlines.geojson`): 10 polygons, EPSG:4326 — the Allegheny County–run parks (North Park, South Park, Boyce, Settlers Cabin, Hartwood Acres, Round Hill, Deer Lakes, Harrison Hills, White Oak, Pittsburgh Botanic Garden). Fields: `NAME`, `Address`, `City`, `Zip`, `ImageURL`, `WebURL`, `LastUpdate`.
- `county_parks.csv` (uploaded as `4.csv`): the same 10 parks as attributes only (no geometry).
- **No housing variables, no time series.** All 10 parks lie outside the City of Pittsburgh, so they don't overlap the permit/inventory neighborhoods. Use: optional basemap context only. **These are not neighborhood boundaries.**

# Addendum 3 (fourth upload): geography crosswalks

**Re-uploads (byte-identical to files already in `data/raw/`, verified by MD5):** `pli.csv` (= `pli_permits.csv`), `zoning 1.geojson` (= `zoning.geojson`), `Allegheny_County_Open_Spaces_*.zip`, `tl_2025_us_state.zip`. `zoning.zip` is the same 1,069 zoning polygons as a shapefile → redundant.

## B1. `blockcodes2016.zip` — 2010 Census blocks with multi-geography crosswalk ⭐

| Property | Value |
|---|---|
| Records | 86,990 block polygons, 10 SW-PA counties (Allegheny 30,516; Westmoreland, Washington, Fayette, Butler, Beaver, Armstrong, Lawrence, Indiana, Greene) |
| CRS | WGS84 Web Mercator (EPSG:3857) → reproject to 4326 |
| Vintage | **2010 Census blocks/tracts** (file built 2016/2018) |
| Keys | `GEOID10` (15-digit block, unique), `geo_id_tra` (11-digit tract), `geo_id_blo` (block group), `geo_name_n`/`geo_id_nho` (Pittsburgh neighborhood, 91 names; blank outside the city), `geo_name_z` (ZIP), `geo_name_1` (municipality), school district, PA House/Senate, County Council, `Pgh_Ward`, `Pgh_CityCo` |
| Quality | 9 blocks missing county; 1,951 blocks with zero land area; 60 City blocks without a neighborhood |

**Why it matters:** dissolving blocks by `geo_name_n` produces **neighborhood polygons**, and by `geo_id_tra` produces **tract polygons**. Verified joins:
- All 90 permit `neighborhood` names match block neighborhoods exactly (blocks add only `Mount Oliver Borough`, a separate municipality).
- All 131 `census_tract` GEOIDs in the city property inventory are 2010 tracts present here.
- Caveat: these are **2010** tract boundaries. ACS releases from 2020 onward use 2020 tracts → a 2010↔2020 tract relationship file (or neighborhood-level aggregation via blocks) is needed before joining ACS 2020+ data.

## B2. `voting_bounds.geojson` — Allegheny County voting districts

1,327 polygons (EPSG:4326), 130 municipalities (Pittsburgh = 402 ward-districts). Fields: `NAME`, `TYPE`, `LABEL`, `WARD_1`, `DISTRICT_1`, `MUNICODE_1`, `MWD_PAD_1` (unique muni-ward-district code). **No housing variables, no time.** Use: optional; could provide ward polygons for the City (permits carry `ward`). Not needed for MVP.


# Addendum 4 (Mk2 upload): market data at ZIP level

| File (as uploaded) | Extract used by Mk2 | Rows | Geography | Period | Role |
|---|---|---|---|---|---|
| `sales.csv` | `allegheny_sales_slim.csv.gz` | 503,747 | parcel → ZIP (123 ZIPs), municipality/ward | 2012-01 → 2026-09 | **scored** (valid sales count, median price) |
| `Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv` | `zip_zhvi_allegheny.csv` | 26,268 → 94 Allegheny ZIPs | ZIP | 2000-01 → 2026-08, monthly | **scored** (home values) |
| `Zip_zori_uc_sfrcondomfr_sm_month.csv` | `zip_zori_allegheny.csv` | 8,459 → 55 Allegheny ZIPs | ZIP | 2015-01 → 2026-08, monthly | **scored** (asking rents) |
| `tl_2022_42_tract.zip` | `tracts_2020_allegheny.geojson` | 3,446 → 394 tracts | 2020 census tract | static | neighborhood ↔ 2020-tract crosswalk (for ACS 2020+) |
| `variables.json`, `variables 1.json`, `variables 2.json` | `census_metadata/` | 1,396 / 19,114 / 28,296 variables | — | ACS 5-year | **metadata only** (Profile, Subject, Detailed tables). No estimates. |
| `2024-5yr-api-changes.csv` | `census_metadata/` | 48,025 | — | 2023→2024 | metadata only (variable name changes) |

## County sales (`sales.csv`) key fields

| Field | Meaning | Notes |
|---|---|---|
| `PARID` | Parcel ID | Same format as permit `parcel_num` / inventory `pin` |
| `PROPERTYZIP` | Property ZIP | 1 missing |
| `MUNIDESC` | Municipality, or City ward (`19th Ward - PITTSBURGH`) | Wards are not neighborhoods |
| `SALEDATE`, `RECORDDATE` | Sale and recording dates | |
| `PRICE` | Sale price (USD) | 25% of all records ≤ $10 (non-market transfers) |
| `SALEDESC` | County validity code | `VALID SALE` 99,176; `LOVE AND AFFECTION` 103,908; `MULTI-PARCEL` 67,051; … |

**Data-quality issues:**

- **The share coded `VALID SALE` jumps from 8% (2019) to 23–32% (2020+).** Coding practice changed, so Mk2 uses 2020 onward only.
- **There is no property-class field,** so medians can include non-residential sales.
- **Recent months have fewer validated sales;** the last valid sale is 2026-08-07, though records run to 2026-09.
- **13 valid-coded sales under $1,000 are dropped.**

## Zillow ZIP series

- **ZHVI** is complete 2020–2025 for most Allegheny ZIPs. It is used as an annual average, 2020–22 vs 2023–25.
- **ZORI** coverage in Allegheny grows from 15 ZIPs (2020) to 31 (Aug 2023) to 55 (2026). Rent change therefore uses **Aug 2023 → Aug 2026** only, and that window is labelled everywhere.

## New derived geography

- **`zips.geojson`:** 114 approximate ZIP areas made by dissolving the 2010 Allegheny County blocks by their ZIP code. It covers the county part only.
- **`neighborhood_zip_crosswalk.csv`, `neighborhood_tract2020_crosswalk.csv`:** land-area shares. 2020 tracts are assigned by locating each 2010 block's internal point.
