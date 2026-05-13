# QuickSight Setup Guide

This guide documents the manual steps to set up the QuickSight dashboard on top of the Terraform-managed infrastructure.

## Prerequisites

- Terraform infrastructure deployed (see main README)
- AWS account with QuickSight Enterprise subscription
- Pipeline executed at least once (curated layer populated)

## Steps

### 1. Subscribe to QuickSight

1. AWS Console → QuickSight → **Sign up for QuickSight**
2. Edition: **Enterprise**
3. Authentication: IAM federated identities & QuickSight-managed users
4. **Region: eu-west-3 (Paris)** — must match the Athena region
5. Account name: `nyc-taxi-pipeline`
6. Authorize **Amazon Athena** and **Amazon S3** access

### 2. Configure S3 permissions

Critical step — QuickSight needs write access to the Athena results bucket.

1. QuickSight UI → top-right user icon → **Manage QuickSight**
2. **Security & permissions** → **Manage**
3. Amazon S3 → **Select S3 buckets**:
   - `nyc-taxi-pipeline-raw-*`
   - `nyc-taxi-pipeline-curated-*`
   - `nyc-taxi-pipeline-athena-results-*` ⚠️ **Check "Write permission for Athena Workgroup"**
   - `nyc-taxi-pipeline-glue-assets-*`
4. **Save**

### 3. Create the dataset

The Terraform-managed data source `nyc-taxi-pipeline-athena` should already exist.

1. **Datasets** → **New dataset** → **Athena**
2. Select `nyc-taxi-pipeline-athena`
3. Database: `nyc_taxi_pipeline_dev`
4. Table: `yellow_taxi` (the curated layer)
5. Query mode: **Direct query**
6. **Save & visualize**

### 4. Add a global date filter

To exclude outlier records (NYC TLC dataset has rare timestamps outside the partition year):

1. Filter panel → **Create one** → `tpep_pickup_datetime`
2. Filter type: **Between**, range: `2024-01-01` to `2024-12-31`
3. **Apply**

### 5. Build visuals

Follow the table in the main README's BI section.

### 6. Publish

**Share** → **Publish dashboard** → name it `NYC Taxi Analytics`.

## Cost notes

- Author license: $9/month (annual) or $24/month (monthly). 30-day free trial available.
- Reader sessions: $0.30/session, capped at $5/month/reader.
- Direct query mode incurs Athena query costs only — no SPICE storage.

## Cleanup

To stop charges:
1. QuickSight → Manage QuickSight → **Account settings** → **Unsubscribe**
2. Wait 30 days for full deletion.

Note: `terraform destroy` does NOT cancel the QuickSight subscription.