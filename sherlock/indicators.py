"""Indicator registry: one entry per measure Sherlock knows about.

`scored=True` indicators contribute to the neighborhood anomaly score.
Everything else is shown as evidence or context only.
"""
from __future__ import annotations

INDICATORS = {
    # ---------------- Neighborhood (City of Pittsburgh) ----------------
    "res_new_construction_permits": {
        "label": "New residential construction permits",
        "short": "New construction",
        "category": "HOUSING SUPPLY",
        "unit": "permits",
        "geography": "neighborhood",
        "time_resolution": "annual (from daily issue dates)",
        "source_id": "pli_permits",
        "scored": True,
        "method": "count_vs_city_trend",
        "caveats": [
            "A permit is not a completed home; issuance does not mean construction started or finished.",
            "Permits do not record how many dwelling units they create.",
        ],
    },
    "demolition_permits": {
        "label": "Demolition permits (complete + city-funded)",
        "short": "Demolitions",
        "category": "HOUSING SUPPLY",
        "unit": "permits",
        "geography": "neighborhood",
        "time_resolution": "annual (from daily issue dates)",
        "source_id": "pli_permits",
        "scored": True,
        "method": "count_vs_city_trend",
        "caveats": [
            "Includes commercial and residential structures.",
            "City-funded demolitions are usually condemned buildings; they reflect City action as well as building condition.",
        ],
    },
    "res_alteration_permits": {
        "label": "Residential renovation / alteration permits",
        "short": "Renovations",
        "category": "MARKET ACTIVITY",
        "unit": "permits",
        "geography": "neighborhood",
        "time_resolution": "annual (from daily issue dates)",
        "source_id": "pli_permits",
        "scored": True,
        "method": "count_vs_city_trend",
        "caveats": [
            "The 2024 permit-system change altered work-type labels; categories were harmonised but counting practice may differ between systems.",
        ],
    },
    "res_permit_value": {
        "label": "Declared value of residential building permits",
        "short": "Permit value",
        "category": "MARKET ACTIVITY",
        "unit": "USD (nominal)",
        "geography": "neighborhood",
        "time_resolution": "annual (from daily issue dates)",
        "source_id": "pli_permits",
        "scored": True,
        "method": "log_ratio_vs_city",
        "caveats": [
            "Declared by applicants; not an appraisal. Zero or negative values are treated as unknown.",
            "Nominal dollars (not inflation-adjusted); the city-relative comparison removes citywide inflation.",
            "A single large project can dominate a neighborhood total.",
        ],
    },
    "city_owned_vacant_lots": {
        "label": "City-owned vacant lots (excluding parks & greenways)",
        "short": "City-owned vacant lots",
        "category": "VACANCY (proxy)",
        "unit": "parcels",
        "geography": "neighborhood",
        "time_resolution": "snapshot",
        "source_id": "city_inventory",
        "scored": False,
        "method": "level_context",
        "caveats": [
            "Only City-owned parcels; privately owned vacant land and vacant buildings are not included.",
            "This is a snapshot, so it cannot show change over time.",
            "Not a vacancy rate.",
        ],
    },
    "city_owned_vacant_lots_per_km2": {
        "label": "City-owned vacant lots per km² of land",
        "short": "Vacant lots / km²",
        "category": "VACANCY (proxy)",
        "unit": "parcels per km²",
        "geography": "neighborhood",
        "time_resolution": "snapshot",
        "source_id": "city_inventory",
        "scored": False,
        "method": "level_context",
        "caveats": ["Land area from 2010 Census blocks."],
    },
    # ---------------- Metro (Pittsburgh MSA vs peer metros) ----------------
    "metro_home_value": {
        "label": "Home value index (inferred ZHVI)", "short": "Home values",
        "category": "HOUSING COST", "unit": "USD", "geography": "metro",
        "time_resolution": "monthly", "source_id": "zillow_zhvi_inferred", "scored": True,
        "method": "metro_peer", "transform": "pct", "caveats": ["Source file name is a UUID; identified as ZHVI by structure."],
    },
    "metro_inventory": {
        "label": "For-sale inventory", "short": "Homes for sale",
        "category": "MARKET ACTIVITY", "unit": "listings", "geography": "metro",
        "time_resolution": "monthly (smoothed)", "source_id": "zillow_inventory", "scored": True,
        "method": "metro_peer", "transform": "pct", "caveats": [],
    },
    "metro_days_to_pending": {
        "label": "Mean days to pending", "short": "Days to pending",
        "category": "MARKET ACTIVITY", "unit": "days", "geography": "metro",
        "time_resolution": "monthly (smoothed)", "source_id": "zillow_days_pending", "scored": True,
        "method": "metro_peer", "transform": "diff", "caveats": ["36% of metro-months missing nationally; peer group is smaller."],
    },
    "metro_new_construction_sales": {
        "label": "New-construction home sales (trailing 12 months)", "short": "New-home sales",
        "category": "HOUSING SUPPLY", "unit": "sales", "geography": "metro",
        "time_resolution": "monthly (summed to trailing 12 months)", "source_id": "zillow_newcon_sales", "scored": True,
        "method": "metro_peer", "transform": "pct_ttm", "caveats": ["Sales of new homes, not permits or completions."],
    },
    "metro_sales": {
        "label": "Home sales (trailing 12 months, nowcast)", "short": "Home sales",
        "category": "MARKET ACTIVITY", "unit": "sales", "geography": "metro",
        "time_resolution": "monthly (summed to trailing 12 months)", "source_id": "zillow_sales", "scored": True,
        "method": "metro_peer", "transform": "pct_ttm", "caveats": ["Recent months are model estimates and may be revised."],
    },
    "metro_income_needed": {
        "label": "Income needed to buy a typical home (20% down)", "short": "Income needed",
        "category": "ECONOMICS / AFFORDABILITY", "unit": "USD per year", "geography": "metro",
        "time_resolution": "monthly (smoothed, SA)", "source_id": "zillow_income_needed", "scored": True,
        "method": "metro_peer", "transform": "pct",
        "caveats": ["Modeled from prices and mortgage rates; not observed household income."],
    },
    "metro_market_heat": {
        "label": "Market heat index", "short": "Market heat",
        "category": "MARKET ACTIVITY", "unit": "index points", "geography": "metro",
        "time_resolution": "monthly", "source_id": "zillow_market_heat", "scored": False,
        "method": "metro_peer", "transform": "diff",
        "caveats": ["Composite of other Zillow inputs; shown for context and excluded from the score to avoid double counting."],
    },
}

INDICATORS.update({
    # ---------------- ZIP code market layer (Mk2) ----------------
    "zip_home_value": {
        "label": "Home value index (Zillow ZHVI)", "short": "Home values",
        "category": "HOUSING COST", "unit": "USD", "geography": "zip",
        "time_resolution": "monthly, averaged to calendar year", "source_id": "zillow_zip_zhvi", "scored": True,
        "method": "zip_log_ratio", "caveats": ["Index of typical home values, smoothed and seasonally adjusted."],
    },
    "zip_rent": {
        "label": "Asking rent index (Zillow ZORI)", "short": "Rents",
        "category": "HOUSING COST", "unit": "USD per month", "geography": "zip",
        "time_resolution": "monthly (Aug 2023 → Aug 2026 change)", "source_id": "zillow_zip_zori", "scored": True,
        "method": "zip_log_ratio",
        "caveats": ["Asking rents for listed homes, not what current tenants pay.",
                    "Only ZIPs with enough listings are covered; coverage grew over time, so the change window is Aug 2023 → Aug 2026."],
    },
    "zip_sales_count": {
        "label": "Valid home sales (County records)", "short": "Home sales",
        "category": "MARKET ACTIVITY", "unit": "sales", "geography": "zip",
        "time_resolution": "annual (from daily sale dates)", "source_id": "county_sales", "scored": True,
        "method": "zip_log_ratio",
        "caveats": ["Only transfers the County coded as 'VALID SALE' (arm's-length).",
                    "Includes all property types in the file; the sales file has no property-class field."],
    },
    "zip_median_price": {
        "label": "Median sale price (County records)", "short": "Sale prices",
        "category": "HOUSING COST", "unit": "USD", "geography": "zip",
        "time_resolution": "annual (from daily sale dates)", "source_id": "county_sales", "scored": True,
        "method": "zip_log_ratio",
        "caveats": ["Median of valid sales, so it shifts when the mix of homes selling changes.",
                    "Nominal dollars."],
    },
})

NEIGHBORHOOD_SCORED = [k for k, v in INDICATORS.items() if v["geography"] == "neighborhood" and v["scored"]]
METRO_INDICATORS = [k for k, v in INDICATORS.items() if v["geography"] == "metro"]
ZIP_SCORED = [k for k, v in INDICATORS.items() if v["geography"] == "zip" and v["scored"]]


def meta(indicator_id: str) -> dict:
    return {"id": indicator_id, **INDICATORS[indicator_id]}
