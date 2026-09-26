"""Central configuration: file locations, source metadata, analysis windows.

Every dataset Sherlock reads is registered in SOURCES so that provenance
(source name, file, geography, time resolution, definition) can be attached
to every calculated value.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# --------------------------------------------------------------------------
# Analysis windows (full calendar years only; 2019 and 2026 are partial)
# --------------------------------------------------------------------------
PERMIT_FIRST_FULL_YEAR = 2020
PERMIT_LAST_FULL_YEAR = 2025
BASELINE_YEARS = (2020, 2021, 2022)
RECENT_YEARS = (2023, 2024, 2025)
TIMELINE_YEARS = tuple(range(2020, 2026))

# Minimum counts before a change is scored (protects against tiny denominators)
MIN_EXPECTED_COUNT = 3.0        # expected recent count under city trend
MIN_TOTAL_COUNT = 5             # baseline + recent observed count
MIN_VALUE_PERMITS = 5           # permits with a declared value, per period

# Anomaly level thresholds (see docs/METHODOLOGY.md)
LEVEL_HIGH_RMS = 1.5
LEVEL_HIGH_MAX = 3.0
LEVEL_MED_RMS = 1.0
LEVEL_MED_MAX = 2.0

# --------------------------------------------------------------------------
# Source registry (provenance)
# --------------------------------------------------------------------------
SOURCES = {
    "pli_permits": {
        "name": "City of Pittsburgh PLI permits",
        "file": "pli_permits.csv",
        "publisher": "City of Pittsburgh, Dept. of Permits, Licenses & Inspections (via WPRDC)",
        "geography": "point / City of Pittsburgh neighborhood",
        "time_resolution": "daily issue date (aggregated to calendar year)",
        "coverage": "2019-06-03 to 2026-09-21",
        "definition": "Permits issued. Issuance does not mean construction started or was completed.",
    },
    "city_inventory": {
        "name": "City of Pittsburgh city-owned property inventory",
        "file": "city_property_inventory.csv",
        "publisher": "City of Pittsburgh (via WPRDC)",
        "geography": "parcel point / neighborhood / 2010 census tract",
        "time_resolution": "snapshot (last_updated up to 2026-09-24)",
        "coverage": "snapshot",
        "definition": "Parcels owned by the City. 'Vacant Land' class counts city-owned vacant parcels only; privately owned vacant land is not included.",
    },
    "census_blocks_2010": {
        "name": "2010 Census blocks with Pittsburgh geography codes (BlockCodes2016)",
        "file": "blockcodes2016.zip",
        "publisher": "Census TIGER 2010 blocks with local crosswalk attributes",
        "geography": "census block → neighborhood / tract / ZIP",
        "time_resolution": "static (2010 boundaries)",
        "coverage": "2010 vintage",
        "definition": "Neighborhood and tract polygons are dissolved from these blocks.",
    },
    "zillow_zhvi_inferred": {
        "name": "Zillow home value index (inferred ZHVI mid-tier, SA)",
        "file": "9a1c60bd-f9f7-4aba-aeb7-af8c3aaa44e5.csv",
        "publisher": "Zillow Research",
        "geography": "metro (MSA)",
        "time_resolution": "monthly",
        "coverage": "2000-01 to 2026-08",
        "definition": "File name is a UUID; identified as ZHVI by structure and values. Source not formally confirmed.",
    },
    "zillow_inventory": {
        "name": "Zillow for-sale inventory (smoothed)",
        "file": "Metro_invt_fs_uc_sfrcondo_sm_month.csv",
        "publisher": "Zillow Research", "geography": "metro (MSA)",
        "time_resolution": "monthly (smoothed)", "coverage": "2018-03 to 2026-08",
        "definition": "Unique for-sale listings active during the month.",
    },
    "zillow_days_pending": {
        "name": "Zillow mean days to pending (smoothed)",
        "file": "Metro_mean_doz_pending_uc_sfrcondo_sm_month.csv",
        "publisher": "Zillow Research", "geography": "metro (MSA)",
        "time_resolution": "monthly (smoothed)", "coverage": "2018-03 to 2026-08",
        "definition": "Mean days from listing to pending.",
    },
    "zillow_newcon_sales": {
        "name": "Zillow new-construction sales count (raw)",
        "file": "Metro_new_con_sales_count_raw_uc_sfrcondo_month.csv",
        "publisher": "Zillow Research", "geography": "metro (MSA)",
        "time_resolution": "monthly (raw, not seasonally adjusted)", "coverage": "2018-01 to 2026-07",
        "definition": "Sales of newly constructed homes. Not permits, starts or completions.",
    },
    "zillow_sales": {
        "name": "Zillow sales count (nowcast)",
        "file": "Metro_sales_count_now_uc_sfrcondo_month.csv",
        "publisher": "Zillow Research", "geography": "metro (MSA)",
        "time_resolution": "monthly (nowcast; recent months provisional)", "coverage": "2008-02 to 2026-08",
        "definition": "Estimated number of home sales.",
    },
    "zillow_income_needed": {
        "name": "Zillow income needed to buy (20% down)",
        "file": "Metro_new_homeowner_income_needed_downpayment_0.20_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
        "publisher": "Zillow Research", "geography": "metro (MSA)",
        "time_resolution": "monthly (smoothed, SA)", "coverage": "2012-01 to 2026-08",
        "definition": "Modeled household income needed to afford a typical home with 20% down; reflects prices and mortgage rates, not observed incomes.",
    },
    "zillow_market_heat": {
        "name": "Zillow market heat index",
        "file": "Metro_market_temp_index_uc_sfrcondo_month.csv",
        "publisher": "Zillow Research", "geography": "metro (MSA)",
        "time_resolution": "monthly", "coverage": "2018-01 to 2026-08",
        "definition": "Composite seller/buyer index built from other Zillow inputs. Context only; not scored.",
    },
    "zillow_forecast": {
        "name": "Zillow home value forecast",
        "file": "Metro_zhvf_growth_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
        "publisher": "Zillow Research", "geography": "metro (MSA)",
        "time_resolution": "forecast from 2026-08", "coverage": "1, 3, 12 months ahead",
        "definition": "Model prediction, not an observation. Display only.",
    },
    "redfin_national": {
        "name": "Redfin national housing market metrics",
        "file": "redfin_housing_market_monthly_all_country_key_metrics_2012_Jan_to_2026_Aug.csv",
        "publisher": "Redfin Data Center", "geography": "United States",
        "time_resolution": "monthly", "coverage": "2012-01 to 2026-08",
        "definition": "National totals and medians. No Pittsburgh-specific values.",
    },
    "zoning": {
        "name": "City of Pittsburgh zoning districts",
        "file": "zoning.geojson",
        "publisher": "City of Pittsburgh", "geography": "zoning polygon",
        "time_resolution": "snapshot", "coverage": "snapshot",
        "definition": "Map context only.",
    },
}

# ---------------------------------------------------------------------------
# Mk2 sources (ZIP-level market layer)
# ---------------------------------------------------------------------------
SOURCES.update({
    "county_sales": {
        "name": "Allegheny County property sales (Real Estate Sales)",
        "file": "allegheny_sales_slim.csv.gz",
        "original_file": "sales.csv",
        "publisher": "Allegheny County Office of Property Assessments (via WPRDC)",
        "geography": "parcel → ZIP code",
        "time_resolution": "daily sale date (aggregated to calendar year)",
        "coverage": "2012-01 to 2026-09",
        "definition": "Recorded property transfers. Sherlock uses only sales the County coded 'VALID SALE' (arm's-length), from 2020 on, because the share of sales coded valid jumped from about 8% to 23%+ in 2020.",
    },
    "zillow_zip_zhvi": {
        "name": "Zillow home value index by ZIP (ZHVI, mid-tier, SA)",
        "file": "zip_zhvi_allegheny.csv",
        "original_file": "Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
        "publisher": "Zillow Research", "geography": "ZIP code",
        "time_resolution": "monthly (smoothed, seasonally adjusted; averaged to calendar year)",
        "coverage": "2000-01 to 2026-08",
        "definition": "Typical value of homes in the middle third of the ZIP's market. An index of all homes, not only those that sold.",
    },
    "zillow_zip_zori": {
        "name": "Zillow observed rent index by ZIP (ZORI)",
        "file": "zip_zori_allegheny.csv",
        "original_file": "Zip_zori_uc_sfrcondomfr_sm_month.csv",
        "publisher": "Zillow Research", "geography": "ZIP code",
        "time_resolution": "monthly (smoothed)",
        "coverage": "2015-01 to 2026-08 (Allegheny coverage grows from 15 ZIPs in 2020 to 55 in 2026)",
        "definition": "Typical asking rent for listed rentals (all home types). Asking rents, not rents paid by current tenants.",
    },
    "tracts_2020": {
        "name": "2020 Census tracts (TIGER/Line 2022)",
        "file": "tracts_2020_allegheny.geojson",
        "original_file": "tl_2022_42_tract.zip",
        "publisher": "U.S. Census Bureau", "geography": "census tract (2020)",
        "time_resolution": "static", "coverage": "2020 vintage",
        "definition": "Used to link neighborhoods to the tracts that ACS 2020+ estimates use.",
    },
})

# Mk2 ZIP analysis windows
SALES_FIRST_COMPARABLE_YEAR = 2020     # valid-sale coding changed in 2020
MIN_ZIP_SALES_BASE = 30                # valid sales in baseline for a count change
MIN_ZIP_SALES_FOR_MEDIAN = 20          # valid sales per period for a median price
MIN_SALE_PRICE = 1000                  # drop nominal-price records even if coded valid
RENT_WINDOW = ("2023-08-31", "2026-08-31")  # widest window with broad ZORI coverage

PITTSBURGH_MSA_REGION_ID = 394982
US_REGION_ID = 102001
