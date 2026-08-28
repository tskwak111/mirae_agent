# External holdings admission

Task 7 admits zero external holdings generations for the sealed 2026-08-24 build.

- KRX: no cutoff-eligible immutable artifact and no explicit submission redisplay permission.
- SEC N-PORT: no approved exact `CIK + SERIES_ID + CLASS_ID` to `PREF02N001` crosswalk and no recorded reuse basis.
- Public-fund reports: no sealed direct artifact with an exact embedded published official identifier and redisplay permission.

No external file was downloaded and no holding row was inferred. Every official domestic
ETF/ETN, overseas ETF/ETN, and public-fund item therefore receives an explicit
`unavailable` coverage row; `silver_product_holding` remains empty. A later generation
may be admitted only with the complete source, cutoff, schema/unit dictionary, exact
owner mapping, reuse/redisplay, count/hash, quarantine, and raw-lineage contract.
