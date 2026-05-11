# 🚕 AWS NYC Taxi Data Pipeline

End-to-end data engineering pipeline on AWS, processing the public NYC Taxi dataset using modern best practices: Infrastructure as Code, partitioned data lake, serverless analytics.

> **Status:** 🚧 Work in progress — see [Roadmap](#roadmap) below.

---

## 🏗️ Architecture

```
┌──────────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  NYC Taxi    │────▶│  S3 (raw)   │────▶│  AWS Glue    │────▶│ S3 (curated)│
│  Public Data │     │  CSV files  │     │  PySpark Job │     │   Parquet   │
└──────────────┘     └─────────────┘     └──────────────┘     └─────────────┘
                                                                      │
                                                                      ▼
                                                              ┌─────────────┐
                                                              │   Athena    │
                                                              │  + Glue     │
                                                              │  Catalog    │
                                                              └─────────────┘
                                                                      │
                                                                      ▼
                                                              ┌─────────────┐
                                                              │  QuickSight │
                                                              │  Dashboard  │
                                                              └─────────────┘
```

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Infrastructure as Code** | Terraform |
| **Storage** | Amazon S3 (versioned, encrypted) |
| **Ingestion** | Python (boto3) |
| **Processing** | AWS Glue (PySpark) |
| **Catalog** | AWS Glue Data Catalog |
| **Query Engine** | Amazon Athena |
| **Visualization** | Amazon QuickSight |
| **Region** | eu-west-3 (Paris) |

## 📂 Project Structure

```
aws-nyc-taxi-pipeline/
├── terraform/          # Infrastructure as Code
│   ├── main.tf         # S3 buckets, Glue, IAM
│   ├── variables.tf
│   ├── outputs.tf
│   └── versions.tf
├── scripts/            # Python utilities
│   └── upload_to_s3.py # Data ingestion
├── docs/               # Architecture diagrams
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- AWS account with programmatic access
- Terraform ≥ 1.5
- Python ≥ 3.10
- AWS CLI configured (`aws configure`)

### Deploy the infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars  # then edit values
terraform init
terraform plan
terraform apply
```

### Tear down (avoid AWS charges)

```bash
terraform destroy
```

## 🔐 Security & Best Practices

- ✅ S3 buckets with versioning enabled
- ✅ Server-side encryption (AES-256)
- ✅ Public access fully blocked
- ✅ Resources tagged (Project, Environment, Owner, ManagedBy)
- ✅ No credentials in code (`.tfvars` gitignored)
- ✅ Least-privilege IAM policies (planned)

## 💻 Usage

### Setup

```bash
# Activate virtualenv (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # then edit .env with your bucket names
```

### Ingest NYC Taxi data

```bash
# Single month
python scripts/upload_to_s3.py --year 2024 --months 1

# Multiple months
python scripts/upload_to_s3.py --year 2024 --months 1 2 3

# Different taxi type
python scripts/upload_to_s3.py --taxi-type green --year 2024 --months 1
```

Data lands in S3 with **Hive-style partitioning** for native Glue/Athena partition discovery:

```
s3://<raw-bucket>/
└── taxi_type=yellow/
    └── year=2024/
        └── month=01/
            └── yellow_tripdata_2024-01.parquet
```

### Catalog data with Glue Crawler

```bash
aws glue start-crawler --name nyc-taxi-pipeline-raw-crawler --region eu-west-3
```

Wait until state is `READY`:
```bash
aws glue get-crawler --name nyc-taxi-pipeline-raw-crawler --region eu-west-3 --query "Crawler.State"
```

### Query data with Athena

Sample SQL queries are available in [`sql/`](sql/). Run them via the Athena console (workgroup: `nyc-taxi-pipeline-workgroup`) or with the AWS CLI.

**Example — multi-month aggregation:**
```sql
SELECT year, month, COUNT(*) AS trips, ROUND(SUM(total_amount), 2) AS revenue_usd
FROM nyc_taxi_pipeline_raw_ake_2026_05
WHERE taxi_type = 'yellow'
GROUP BY year, month
ORDER BY year, month;
```

Sample output (Jan-Mar 2024 yellow taxi data):

| year | month | trips | revenue_usd |
|------|-------|-----------|-------------|
| 2024 | 01    | 2,964,624 | 79,456,384  |
| 2024 | 02    | 3,007,526 | 80,073,615  |
| 2024 | 03    | 3,582,628 | 97,162,914  |

### Run the ETL job (raw → curated)

```bash
# Start the PySpark Glue job
aws glue start-job-run \
  --job-name nyc-taxi-pipeline-transform-taxi \
  --region eu-west-3

# Monitor (replace <RUN_ID>)
aws glue get-job-run \
  --job-name nyc-taxi-pipeline-transform-taxi \
  --run-id <RUN_ID> \
  --region eu-west-3 \
  --query "JobRun.JobRunState"

# Once SUCCEEDED, catalog the curated layer
aws glue start-crawler --name nyc-taxi-pipeline-curated-crawler --region eu-west-3
```

The ETL job:
- **Filters** rows with negative durations, zero distances, invalid passenger counts
- **Derives** analytics-ready columns: `trip_duration_minutes`, `pickup_period`, `is_weekend`, `fare_per_mile`, `tip_percentage`, date parts
- **Writes** Snappy-compressed Parquet partitioned by `pickup_year/pickup_month/pickup_day`
- **Bookmarks** are enabled — re-running the job won't re-process the same files

## 🤖 CI/CD

GitHub Actions automate Terraform validation and deployment using **OIDC** (no long-lived AWS credentials stored in GitHub).

| Workflow | Trigger | Action |
|---|---|---|
| `terraform-pr.yml` | Pull request to `main` | `fmt`, `validate`, `plan`, comment diff on PR |
| `terraform-main.yml` | Push to `main` | `apply` (with optional manual approval) |
| `python-lint.yml` | PR with `.py` changes | Run `ruff check` and `ruff format --check` |

### Setup

The IAM role for GitHub Actions is created by Terraform (`github_oidc.tf`). After the first manual apply, set these GitHub repo variables:

- `AWS_ROLE_ARN` — output `github_actions_role_arn` from Terraform
- `AWS_REGION` — `eu-west-3`
- `TF_BUCKET_SUFFIX` — your unique S3 bucket suffix

No secrets, no access keys. Authentication uses GitHub's OIDC tokens, which AWS validates and exchanges for short-lived credentials per workflow run.

## 🗺️ Roadmap

- [x] **Phase 1** — Bootstrap S3 buckets (raw + curated) with Terraform
- [x] **Phase 2** — Ingest NYC Taxi data via Python + boto3
- [x] **Phase 3** — Glue Crawler + Data Catalog
- [x] **Phase 4** — Glue ETL job: raw → partitioned & enriched Parquet
- [x] **Phase 5** — Athena queries + sample analytics
- [ ] **Phase 6** — QuickSight dashboard
- [ ] **Phase 7** — Orchestration with Step Functions
- [x] **Phase 8** — CI/CD with GitHub Actions
- [ ] **Phase 9** — Monitoring with CloudWatch

## 📊 Dataset

[NYC Taxi & Limousine Commission Trip Records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) — public dataset of yellow & green taxi trips in New York City. ~30 GB/year, ideal for testing data engineering patterns at scale.

## 👤 Author

**Achraf El Khatabi**
Cloud / Data Engineer · AWS Certified · 14+ years in BSS Telecom systems
Open to remote opportunities (CET).

[LinkedIn](https://www.linkedin.com/in/achraf-el-khatabi) · [Email](mailto:ac.elkhatabi@gmail.com)

## 📄 License

MIT — see [LICENSE](LICENSE).