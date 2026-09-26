# What Sherlock Homes cannot determine

These limits come from the data that is actually loaded (see `DATA_DICTIONARY.md`). They are shown in every case file.

## Missing concepts (answer: UNKNOWN)

* **Rent at neighborhood or tract level.** Mk2 adds Zillow asking rents at **ZIP level only**, for Aug 2023 → Aug 2026 and 55 ZIPs. These are asking rents for listed homes, not rents paid by current tenants.
* **Neighborhood home prices or sales.** Mk2 has prices and sales at **ZIP level** (Zillow ZHVI and County valid sales). ZIPs do not match neighborhood borders, so neighborhood cases show them as labelled ZIP evidence only.
* **Household income, population, households, tenure, cost burden.** No ACS or Census tables are loaded. Zillow's "income needed" is a modeled affordability threshold, not observed income.
* **Vacancy rate.** The only vacancy proxy is the number of **City-owned** vacant lots, in a single snapshot. Privately owned vacant land and vacant buildings are not included.
* **Housing units added.** Permits have no dwelling-unit field; only 207 of 65,378 descriptions mention a unit count.
* **Completions.** A permit being issued does not mean construction started or finished.

## Causation

No dataset here can establish cause and effect. Sherlock reports **timing** ("X departed from its earlier pattern before Y") and **co-occurrence**. It never reports that one change caused another.

## Geographic limits

* The analysis covers the **City of Pittsburgh only** (90 neighborhoods). Suburban Allegheny County is not covered by the permit data.
* Neighborhood boundaries come from **2010 Census blocks**. The City's current neighborhood boundaries may differ slightly.
* Metro indicators describe a **7-county region** and are always labelled as such. They are never attributed to a neighborhood.
* The city property inventory uses **2010 tract codes**. ACS releases from 2020 onward use 2020 tracts and would need a relationship file.

## Temporal limits

* Permits cover **June 2019 – September 2026**. 2019 and 2026 are partial and excluded from change calculations.
* Only three full years (2020–2022) form the baseline, which **includes pandemic-era activity** in 2020–21.
* The **2024 permit-system change** altered permit types and work-type labels. Sherlock harmonises categories, but counting practices may differ; the citywide rise in renovation permits in 2024–25 may partly reflect this. Because every neighborhood is compared with the **city's** change over the same period, a system-wide artefact affects all areas equally and largely cancels out.
* Zillow recent-month sales are **nowcasts** and may be revised; some Zillow series are smoothed.

## Statistical limits

* Permit counts are small in many neighborhoods. Minimum-count rules mark these as UNKNOWN, but single projects can still dominate (a burst detector flags same-day batches).
* Declared project values are applicant estimates.
* Robust z-scores rank neighborhoods relative to each other; a HIGH level means "different", not "significant" in a formal hypothesis-testing sense.
* Confidence cannot reach HIGH at neighborhood level until an independent second source is added.

## Source identification

* The Zillow home value file arrived with a UUID file name. It was identified as ZHVI (mid-tier, smoothed, seasonally adjusted) from its structure and values, and is labelled "inferred" everywhere.

## Responsible use

Sherlock Homes is decision support. It does not provide legal, financial or zoning advice, and a flagged neighborhood is a lead for human investigation, not a conclusion.


## Mk2 additions

* **County sales:** only transfers coded `VALID SALE` are used, and only from 2020 on, because coding practice changed. The file has no property-type field.
* **ZIP areas** are approximations built from 2010 Census blocks, limited to the Allegheny County part of each ZIP.
* **Zillow ZHVI** is a smoothed, seasonally adjusted index of typical homes. The County median reflects only the homes that sold. The two often differ in size, and Sherlock shows that disagreement.
* **Census ACS** values are not yet loaded. The uploaded Census JSON files are variable dictionaries, not data.

## Dr. John

* Web answers come from general sources (Wikipedia, DuckDuckGo) and can be out of date or not specific to Pittsburgh. They are always tagged [W#] so they can't be mistaken for Sherlock's data.
* Small local AI models make mistakes. The fact check flags unsupported numbers and causal wording, but it can't catch every error in reasoning. Treat answers as a guide to the cited sources.
* Without an AI model, Dr. John lists evidence rather than composing an answer.
