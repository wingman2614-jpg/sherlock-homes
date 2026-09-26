# data/raw

Files the pipeline reads (`sherlock/config.py` → `SOURCES`):

| File | Uploaded as |
|---|---|
| `pli_permits.csv` | `2.csv` / `pli.csv` |
| `city_property_inventory.csv` | `1.csv` |
| `blockcodes2016.zip` | `blockcodes2016.zip` (60 MB, not in the delivery zip; copy it here to rebuild boundaries) |
| `9a1c60bd-f9f7-4aba-aeb7-af8c3aaa44e5.csv` (inferred Zillow ZHVI) | same |
| `Metro_*.csv` (6 Zillow files) | same |
| `redfin_*.csv` (2 files) | same |

Received but not used by the pipeline (context layers, not needed to build; kept out of the delivery zip to save space):
`zoning.geojson`, `zoning.zip`, `3.csv` (truncated zoning table), `Allegheny_County_Open_Spaces_*.zip`,
`tl_2025_us_state.zip`, `park_outlines.geojson`, `4.csv`, `voting_bounds.geojson`.
Drop them back in here if you want to add map overlays later.
