# Census ACS (optional)

Save Census API responses here as `acs_<YEAR>.json`. Open each link in a browser and save the page:

- **acs_2023.json** (2019–2023, 2020 tracts):
  https://api.census.gov/data/2023/acs/acs5?get=NAME,B25064_001E,B19013_001E,B25002_001E,B25002_003E,B25003_001E,B25003_003E&for=tract:*&in=state:42%20county:003
- **acs_2019.json** (2015–2019, 2010 tracts):
  https://api.census.gov/data/2019/acs/acs5?get=NAME,B25064_001E,B19013_001E,B25002_001E,B25002_003E,B25003_001E,B25003_003E&for=tract:*&in=state:42%20county:003

Then run `python -m sherlock.build`. Case files will show tract-level rent, income, vacancy and renter share.

Note: the `variables*.json` and `2024-5yr-api-changes.csv` files you uploaded are Census *variable dictionaries* (names and labels of every ACS variable). They contain no estimates, so they are kept in `data/raw/census_metadata/` for reference only.
