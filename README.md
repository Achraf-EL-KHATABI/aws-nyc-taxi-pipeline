# 🚕 AWS NYC Taxi Data Pipeline
[![Terraform Apply](https://github.com/Achraf-EL-KHATABI/aws-nyc-taxi-pipeline/actions/workflows/terraform-main.yml/badge.svg)](https://github.com/Achraf-EL-KHATABI/aws-nyc-taxi-pipeline/actions/workflows/terraform-main.yml)
[![Python Lint](https://github.com/Achraf-EL-KHATABI/aws-nyc-taxi-pipeline/actions/workflows/python-lint.yml/badge.svg)](https://github.com/Achraf-EL-KHATABI/aws-nyc-taxi-pipeline/actions/workflows/python-lint.yml)

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

## 🗄️ State Management

Terraform state is stored remotely in S3 with DynamoDB locking, enabling safe collaborative & CI/CD workflows. The backend infrastructure lives in a separate root module (`terraform-bootstrap/`) that's deployed once and rarely touched.

```
terraform-bootstrap/   ← runs once: creates state bucket + lock table
terraform/             ← main infrastructure, uses the bootstrap backend
```

- **State bucket**: versioning + encryption + `prevent_destroy` lifecycle
- **Lock table**: DynamoDB PAY_PER_REQUEST with point-in-time recovery
- **Pattern**: bootstrap stack avoids the chicken-and-egg of "the backend storing its own creation"

## 🎼 Orchestration

The full pipeline is orchestrated by an **AWS Step Functions** state machine that chains all the data engineering steps with retries, error handling, and notifications:

```
Start Raw Crawler → Wait for READY → Run Glue ETL Job → Start Curated Crawler → Wait for READY → Notify (SNS)
```

Key features:
- **Polling loops** with `Wait` + `Choice` states for crawler completion
- **Native sync integration** for Glue job (`startJobRun.sync` — no manual polling needed)
- **Retry policies** with exponential backoff on transient errors
- **Catch handlers** routing all failures to a single notification state
- **CloudWatch logging** of execution history
- **EventBridge Scheduler** for daily automated runs (currently disabled — enable in `step_functions.tf`)
- **SNS topic** for success/failure notifications

### Trigger manually

```bash
aws stepfunctions start-execution \
  --state-machine-arn $(aws stepfunctions list-state-machines \
    --query "stateMachines[?name=='nyc-taxi-pipeline-pipeline'].stateMachineArn" \
    --output text) \
  --region eu-west-3 \
  --input '{}'
```

### State machine definition

The full Amazon States Language definition is in [`state_machine/taxi_pipeline.asl.json`](state_machine/taxi_pipeline.asl.json), templated by Terraform with the actual resource names.

## 📊 BI Dashboard (QuickSight)

The curated layer feeds an interactive Amazon QuickSight dashboard for business analytics — the visible end of the pipeline.

![Dashboard Overview](docs/screenshots/dashboard_overview.png)

### Built on the curated layer

The dashboard queries the `yellow_taxi` Glue catalog table directly via Athena, with no data movement — every visual reflects the latest output of the ETL pipeline.

**Key metrics (Jan–Mar 2024, post-quality-filter):**
- **8.48 M** total trips
- **$18.68** average fare
- Hourly demand curve, daily seasonality, weekend vs weekday patterns

### Visualizations

| Visual | Type | Insight |
|---|---|---|
| Total Trips | KPI | Headline volume |
| Average Fare | KPI | Economic signal |
| Trips by Hour of Day | Bar chart | Peak demand profile |
| Daily Trip Volume | Line chart | Weekly seasonality, outliers |
| Pickup Period | Donut | Morning/afternoon/evening/night split |
| Weekend vs Weekday | Bar chart | Fare behavior comparison |

### Architecture choice — Direct Query (no SPICE)

The dataset uses **Direct Query** mode rather than QuickSight's SPICE in-memory cache. Trade-off:
- ✅ Always fresh — reflects every pipeline run immediately
- ✅ No duplicated storage cost
- ❌ Slightly higher per-visual latency (~3-5 s vs <1 s)

For larger workloads or executive dashboards with many concurrent readers, SPICE would be the right call.

### IaC vs UI boundaries

QuickSight is intentionally UI-driven for visualization design — Terraform (`quicksight.tf`) provisions:
- A dedicated Athena workgroup `nyc-taxi-pipeline-quicksight` (cost & monitoring isolation)
- The Athena data source connection with author-level permissions
- A scoped IAM permission set

The dataset, analysis, and dashboard are created via the QuickSight console — this is the documented AWS pattern as of 2026. Setup is reproducible in ~10 minutes following the steps in [docs/quicksight-setup.md](docs/quicksight-setup.md).

### Data quality observation

While building the dashboard, I noticed a few records with pickup dates outside the partition year (e.g. `2009-01-01` in a `year=2024` partition). This is a known upstream quirk of the NYC TLC public dataset — a tiny fraction (~0.001%) of records have malformed timestamps. The dashboard applies a date filter to scope visualizations to 2024 only. This is a good candidate for a future Great Expectations validation step in the ETL job.

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
- [x] **Phase 6** — QuickSight Dashboard
- [x] **Phase 7** — Orchestration with Step Functions
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