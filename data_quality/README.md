# Data Quality Validations

This module enforces **data contracts** on the curated layer using [Great Expectations v1.x](https://greatexpectations.io/).

## Why this matters

Unit tests check the **code**. Data quality validations check the **data flowing through it**.

A pipeline can be 100% bug-free in its Python and still produce garbage if upstream data drifts. This module provides a second line of defense: every batch must satisfy explicit contracts before being declared valid.

## What is checked (16 expectations)

The full list lives in [`expectations.py`](expectations.py). Categories:

| Category | Coverage |
|---|---|
| **Schema** | 5 derived columns must exist after ETL |
| **Completeness** | `vendorid`, `pickup_datetime`, `fare_amount` are non-null |
| **Business rules** | Trip duration < 24h, distance < 200mi, passenger_count ∈ [1, 9], fare ≥ 0 |
| **Categorical consistency** | `pickup_period` ∈ {morning, afternoon, evening, night}; `is_weekend` is boolean |
| **Temporal consistency** | Pickup dates ∈ [2020-01-01, 2030-12-31] |
| **Volume sanity** | Batch row count ∈ [1, 50M] |

## Real-world finding 🔍

Running this suite on actual production data caught **a real upstream issue** in the NYC TLC dataset:

```
FAIL | expect_column_values_to_be_between on tpep_pickup_datetime
       Description: Pickup dates must be in the modern era.
       1/797067 rows failed
```

A tiny fraction (~0.0001%) of records have timestamps from years like 2002 or 2009 mixed into 2024 batches. This is a known but undocumented quirk of the public NYC TLC dataset. The `pickup_year=2002` partition visible in the curated layer is proof:

```
s3://nyc-taxi-pipeline-curated-.../yellow_taxi/pickup_year=2002/pickup_month=12/...
s3://nyc-taxi-pipeline-curated-.../yellow_taxi/pickup_year=2009/pickup_month=1/...
s3://nyc-taxi-pipeline-curated-.../yellow_taxi/pickup_year=2024/pickup_month=1/...
```

Without this validation, those records would have silently corrupted BI dashboards. With it, the pipeline fails fast with a precise count and business description.

## Run locally

```bash
# Validate the curated layer with 10 sampled files (distributed across partitions)
python data_quality/validate_curated.py --layer curated --max-files 10

# Validate the raw layer
python data_quality/validate_curated.py --layer raw --max-files 1
```

Requires environment variables `AWS_REGION`, `RAW_BUCKET`, `CURATED_BUCKET` (see `.env.example`).

## Sampling strategy

To avoid bias toward early alphabetical partitions (which happen to be the outliers like 2002), the validator collects ALL Parquet files under a prefix and samples them evenly. This guarantees representative coverage across the entire dataset.

## Exit codes

- `0` — all expectations pass, data contract upheld
- `1` — at least one expectation failed; downstream consumers should NOT trust this batch

## Next step: integrate into orchestration

The next iteration will add this validation as a **post-ETL step in Step Functions**, between the ETL job and the curated crawler. If validation fails, the pipeline will:
1. Skip the curated crawler (don't catalog tainted data)
2. Send a SNS alert with the specific failed expectations
3. Fail the state machine