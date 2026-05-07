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

## 🗺️ Roadmap

- [x] **Phase 1** — Bootstrap S3 buckets (raw + curated) with Terraform
- [x] **Phase 2** — Ingest NYC Taxi data via Python + boto3
- [ ] **Phase 3** — Glue Crawler + Data Catalog
- [ ] **Phase 4** — Glue ETL job: CSV → partitioned Parquet
- [ ] **Phase 5** — Athena queries + sample analytics
- [ ] **Phase 6** — QuickSight dashboard
- [ ] **Phase 7** — Orchestration with Step Functions
- [ ] **Phase 8** — CI/CD with GitHub Actions
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