# Sherlock Homes — Methodology

Every number Sherlock shows comes from the deterministic pipeline in `sherlock/`. No language model computes, selects or invents a value. This document describes exactly how each result is produced. Parameters live in `sherlock/config.py`.

## 1. Unit of analysis and geography

**Primary unit: the 90 City of Pittsburgh neighborhoods.** Census tracts were the first choice, but the only dataset with a time dimension below the metro level, PLI permits, carries neighborhood names and no tract codes. Neighborhood boundaries are built by dissolving 2010 Census blocks in `blockcodes2016.zip` on their `geo_name_n` field (`sherlock/geo.py`, pure Python). Blocks from one topology share identical edges, so a neighborhood's interior edges cancel and its outline remains. Rings are simplified with Douglas–Peucker (≈3 m tolerance) and oriented per RFC 7946. `Mount Oliver Borough` is excluded because it is a separate municipality with no City permit data.

Permits are assigned to neighborhoods using the `neighborhood` field in the permit file, not by spatial join. All 90 permit neighborhood names match the block names exactly.

**Separate geographies are never mixed.** Metro values (Zillow, 7-county Pittsburgh MSA) and national values (Zillow US row, Redfin) keep their own `geography` label and are shown as context, never as neighborhood measurements.

## 2. Data normalization

`sherlock/normalize.py` writes `data/processed/observations.csv`, with one row per (area, indicator, period):

| column | meaning |
|---|---|
| `area_id`, `area_name`, `geography` | neighborhood / city / metro / country |
| `indicator` | id from `sherlock/indicators.py` |
| `period_start`, `period_end` | actual coverage; partial years keep their true start/end |
| `time_resolution` | original resolution (annual-from-daily, monthly, smoothed, snapshot …) |
| `value`, `unit`, `n_records` | value and the number of underlying records |
| `source_id`, `source_file` | provenance |
| `flags` | e.g. `partial_year:ends_2026-09-21`, `nowcast`, `smoothed`, `inferred_source`, `snapshot` |

### Permit cleaning (`sherlock/ingest.py`)

1. Keep only **building-type permits** (`BUILDING`, `Building & Development Application`) and **demolition permits**. Trade permits (electrical, mechanical, …) are excluded so that one project is not counted several times.
2. **Harmonise the 2024 system change** with a crosswalk: `NEW CONSTRUCTION`/`NEW`/`New Construction` → *new construction*; `ADDITION / ALTERATION`, `MINOR ALTERATION`, `Existing (alteration/addition)`, … → *alteration*; `COMPLETE DEMOLITION`, `CITY FUNDED DEMOLITION` → *demolition*. Partial demolitions are excluded.
3. Drop `Revoked` permits (300). `Expired` is kept because it only exists in the legacy system and removing it would create an artificial break.
4. Drop exact duplicates (same parcel, date, type, work type, description and value; 166 rows).
5. `total_project_value ≤ 0` is treated as **unknown**, not zero (403 permits).
6. Nothing is interpolated or imputed.

### Indicators

| id | definition | scored? |
|---|---|---|
| `res_new_construction_permits` | residential building permits classed as new construction | yes |
| `demolition_permits` | complete + City-funded demolition permits (residential and commercial) | yes |
| `res_alteration_permits` | residential building permits classed as alteration/addition | yes |
| `res_permit_value` | sum of declared value of residential new-construction + alteration permits | yes |
| `city_owned_vacant_lots` (/km²) | City-owned parcels with class `Vacant Land`, excluding parks/greenways (snapshot) | context only |
| metro indicators | Zillow MSA series (home values, inventory, days to pending, new-home sales, sales, income needed, market heat) | scored only within the metro file |

## 3. Trend calculations

Windows are full calendar years only:

* **Baseline:** 2020–2022  **Recent:** 2023–2025
* 2019 (from June) and 2026 (through September) are partial years. They appear on timelines with an asterisk and are **excluded** from every change calculation.

For each neighborhood *n* and count indicator *i*:

* `B` = baseline count, `R` = recent count
* `CB`, `CR` = the same counts for the whole city
* **Percent change** `R/B − 1` is shown **only if B ≥ 5**. Otherwise it reads "n/a (small base)".
* **Citywide comparison**: `CR/CB − 1`
* **Expected recent count at the city trend**: `E = B × CR/CB`

## 4. Anomaly detection

### 4.1 Count indicators

1. **Poisson-style residual:** `r = (R − E) / √(E + 1)`. This measures how far the observed count is from what the citywide trend implies, scaled for count noise. The `+1` keeps it finite when `E = 0`.
2. **Minimum data:** the indicator is marked `insufficient_data` (shown as **UNKNOWN** and left out of the score) if `B + R < 5`, or if both `E` and `R` are below 3.
3. **Robust z-score across neighborhoods:** `z = (r − median(r)) / (1.4826 × MAD(r))`, computed over all neighborhoods with sufficient data. If MAD = 0, the standard deviation is used; if there is no spread at all, z = 0. Median and MAD are used instead of mean and SD so that a few extreme neighborhoods do not hide the others.
4. Percentile rank of `r` among compared neighborhoods is also reported.

### 4.2 Permit value

`lr = ln(Vrecent / Vbaseline) − ln(CVrecent / CVbaseline)`: the neighborhood's value growth relative to the city's, on a log scale (symmetric for rises and falls, and robust to inflation because both sides are nominal). It requires at least 5 permits with a declared value in each period. Robust z as above. If one permit is more than 50% of recent value, a note and a confidence factor are added.

### 4.3 Combined anomaly score

`score = √(mean(z²))`, the root-mean-square of the scored indicators' z-scores. It is the typical size of the neighborhood's deviations.

| level | rule |
|---|---|
| HIGH | score ≥ 1.5 **or** any \|z\| ≥ 3 |
| MEDIUM | score ≥ 1.0 **or** any \|z\| ≥ 2 |
| LOW | otherwise |
| INSUFFICIENT DATA | fewer than 2 scored indicators |

HIGH and MEDIUM neighborhoods become numbered **cases**, ordered by level then score. "Why Sherlock noticed" lists every indicator with \|z\| ≥ 1, strongest first. **High means different from the comparison pattern, not good or bad.**

### 4.4 Burst detection

If more than 50% of a neighborhood's recent permits of one type were issued on the same day, a note says it probably reflects one multi-lot project. The pattern also adds a moderate confidence factor ("Concentrated activity").

### 4.5 Metro context

For each Zillow metro series, the Pittsburgh MSA's 1-year and 5-year change is compared with every MSA that has data. Changes are percentages, or trailing-12-month percentages for sales counts; days-to-pending and market heat use absolute differences. The comparison reports a robust z, the percentile, and the same statistics against the 100 largest metros. Percent changes of trailing-12-month sums require a prior total of at least 120. Market heat is shown but not scored, because Zillow builds it from the other inputs. The forecast is never scored.

## 5. Timeline and "What changed first?"

For each indicator and year *y* in 2022–2025, the expected count is the neighborhood's **2020–21 share of city activity × the city's count in year y**.

* Count indicators **depart** in the first year where `(obs − exp)/√(exp + 1)` reaches ±2, with at least 3 permits observed or expected.
* Permit value **departs** in the first year where observed is ≥ 2× or ≤ ½× expected, with at least 3 valued permits.

"What changed first?" orders these first-departure years; ties share a rank. Indicators with no departure are listed as "no clear departure". Every output carries the statement: *order of change does not establish causation.*

## 6. Similar cases

* **Feature vector:** z-scores of the 4 scored indicators plus the robust z of city-owned vacant lots per km² (5 features), clipped to ±4 so one extreme value cannot dominate.
* **Comparison set:** only features both neighborhoods have. At least 3 shared features are required; otherwise no similar cases are listed.
* **Similarity** = cosine similarity, shown as a percent. Negative values are shown as 0%. Ties are broken by Euclidean distance.
* **Explanation:** features where both \|z\| ≥ 0.5 with the same sign are listed as shared ("both above the citywide pattern"). Features whose z differs by ≥ 1.5 are listed as differences.

## 7. Conflicting evidence

`classify_agreement(a, b)` compares two changes (as fractions):

* `agree`: same direction, and the gap is at most max(3 pp, 25% of the larger magnitude)
* `magnitude`: same direction, larger gap
* `direction`: opposite signs, both beyond ±3 pp
* `unknown`: either value is missing

Three comparisons are run:

1. **National:** Zillow's US row vs Redfin national, over 1-year and 5-year windows ending at the last common month, for sales, inventory, prices and speed of sale.
2. **City vs metro supply:** City residential new-construction permits vs Zillow metro new-construction sales, 2020–22 vs 2023–25.
3. **Within neighborhood:** permit counts vs permit value moving in opposite directions (both \|z\| ≥ 1).

Each comparison lists what the evidence agrees on, what remains uncertain, and **possible** reasons. The reasons are taken only from dataset definitions and coverage, and are labelled as unverified.

## 8. Data confidence

| factor | severity |
|---|---|
| < 30 analysed permits 2020–2025 | major |
| 30–99 analysed permits | moderate |
| < 2 scored indicators | major |
| some indicators unscored | minor |
| single neighborhood-level source (always true today) | moderate |
| one permit > 50% of recent value | moderate |
| same-day batch > 50% of a scored count | moderate |
| related measures point in opposite directions | moderate |
| 2024 permit-system change | minor |
| vacancy proxy is a snapshot | minor |

**LOW** if any major factor or ≥ 3 moderate factors; **MODERATE** if 1–2 moderate factors; **HIGH** only with none. Because every neighborhood currently depends on a single time-series source, no neighborhood can reach HIGH until an independent source (e.g. ACS) is added. This is intended.

## 9. Language layer

* **Finding** (`sherlock/narrative.py`): fixed templates filled from the case file. It always ends by saying what the evidence does not establish.
* **Optional AI rephrasing** (`sherlock/llm.py`, only if `ANTHROPIC_API_KEY` is set): the model receives the case JSON and the deterministic finding. Its output is **rejected** if it contains any number not in the case file, or any causal phrase (caused, led to, drove, due to, because of, resulted in, …). On rejection or error, the deterministic text is shown with the reason.
* **Questions** (`sherlock/query.py`): rule-based parsing into `{conditions: [{indicator, direction}], rank, similar_to, unsupported}`. An LLM may produce the same JSON, which is validated against the indicator list. Answers filter precomputed z-scores (\|z\| ≥ 0.5). Concepts with no data, such as rent, income, prices and vacancy rate, return **UNKNOWN**.


## 10. Mk2: ZIP-code market layer

**Unit and comparison.** There are 109 Allegheny County ZIP areas with market data. Each is compared with the **typical Allegheny County ZIP** (the median of ZIP changes) for Zillow series, and with the **county total/median** for sales.

| indicator | source | change measured | minimum data |
|---|---|---|---|
| `zip_home_value` | Zillow ZHVI | mean of 2023–25 monthly values vs mean of 2020–22 | all 72 months present |
| `zip_rent` | Zillow ZORI | Aug 2026 vs Aug 2023 | both months present |
| `zip_sales_count` | County valid sales | 2023–25 count vs 2020–22 | baseline ≥ 30 sales |
| `zip_median_price` | County valid sales | median 2023–25 vs 2020–22 | ≥ 20 sales in each period |

**Sales cleaning.** Only `SALEDESC == "VALID SALE"`, sale year ≥ 2020, price ≥ $1,000, a valid 5-digit ZIP, and exact duplicates (parcel, date, price) removed.

**Signal.** `lr = ln(recent / baseline) − ln(1 + comparison change)`, then a robust z across ZIPs (median/MAD), as for neighborhoods. The score and levels use the same RMS / max-|z| rules as §4.3.

**Timeline and "what changed first".** Yearly values are compared with the path the ZIP would have followed had it changed like the typical county ZIP since 2020–21 (2023 for rents). A departure is:

- ±5% for home values and rents
- ±10% for median prices, with ≥ 10 sales that year
- a Poisson residual of ±2 for sales counts

**Cross-source check.** Zillow ZHVI change vs County median sale price change, per ZIP, with `classify_agreement` (§7).

**Confidence.**

| factor | severity |
|---|---|
| < 60 valid sales, 2020–25 | major |
| 60–199 valid sales | moderate |
| < 2 measurable indicators | major |
| some indicators missing | minor |
| the two price sources move in opposite directions | moderate |
| the two price sources differ in size | minor |
| approximate ZIP boundary; mixed property types | minor (always) |

Because two independent sources are compared, a ZIP can reach HIGH.

**Neighborhood link.** Every neighborhood lists the ZIPs covering at least 10% of its land, from the block-level land-area crosswalk. These values are displayed as ZIP-level evidence and are **not** used in the neighborhood anomaly score.

**ACS (optional).** When `data/raw/acs/acs_<year>.json` exists, tract estimates are listed per neighborhood for tracts covering at least 10% of its land. Vintages 2019 and earlier use the 2010 crosswalk; 2020 and later use the 2020 crosswalk. Medians are never averaged across tracts, and Census missing-value codes (e.g. −666666666) become UNKNOWN.
