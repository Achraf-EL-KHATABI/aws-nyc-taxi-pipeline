# ============================================
# S3 BUCKET — Glue scripts and assets
# ============================================
resource "aws_s3_bucket" "glue_assets" {
  bucket        = "${var.project_name}-glue-assets-${var.bucket_suffix}"
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "glue_assets" {
  bucket = aws_s3_bucket.glue_assets.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "glue_assets" {
  bucket = aws_s3_bucket.glue_assets.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Upload the PySpark script to S3 (Terraform-managed = always in sync with code)
resource "aws_s3_object" "etl_script" {
  bucket = aws_s3_bucket.glue_assets.id
  key    = "scripts/transform_taxi_data.py"
  source = "${path.module}/../glue_jobs/transform_taxi_data.py"
  etag   = filemd5("${path.module}/../glue_jobs/transform_taxi_data.py")
}

# ============================================
# IAM ROLE — for the Glue ETL Job
# ============================================
resource "aws_iam_role" "glue_etl_job" {
  name               = "${var.project_name}-glue-etl-job-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
}

resource "aws_iam_role_policy_attachment" "glue_etl_service" {
  role       = aws_iam_role.glue_etl_job.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Custom least-privilege policy: read raw, write curated, read scripts, write logs
data "aws_iam_policy_document" "glue_etl_s3_access" {
  statement {
    sid     = "ReadRawData"
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.raw.arn,
      "${aws_s3_bucket.raw.arn}/*",
    ]
  }

  statement {
    sid = "WriteCuratedData"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.curated.arn,
      "${aws_s3_bucket.curated.arn}/*",
    ]
  }

  statement {
    sid     = "ReadScripts"
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.glue_assets.arn,
      "${aws_s3_bucket.glue_assets.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "glue_etl_s3_access" {
  name   = "${var.project_name}-glue-etl-s3-access"
  role   = aws_iam_role.glue_etl_job.id
  policy = data.aws_iam_policy_document.glue_etl_s3_access.json
}

# ============================================
# GLUE JOB — PySpark ETL: raw → curated
# ============================================
resource "aws_glue_job" "transform_taxi" {
  name              = "${var.project_name}-transform-taxi"
  role_arn          = aws_iam_role.glue_etl_job.arn
  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"
  timeout           = 30 # minutes — generous safety net

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.glue_assets.id}/${aws_s3_object.etl_script.key}"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-job-insights"              = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-metrics"                   = "true"
    "--job-bookmark-option"              = "job-bookmark-enable"
    "--TempDir"                          = "s3://${aws_s3_bucket.glue_assets.id}/tmp/"

    # Custom job arguments (consumed in PySpark via getResolvedOptions)
    "--raw_database"     = aws_glue_catalog_database.main.name
    "--raw_table"        = "nyc_taxi_pipeline_raw_${replace(var.bucket_suffix, "-", "_")}"
    "--curated_bucket"   = aws_s3_bucket.curated.id
    "--curated_path"     = "yellow_taxi"
    "--taxi_type_filter" = "yellow"
  }

  execution_property {
    max_concurrent_runs = 1
  }
}

# ============================================
# GLUE CRAWLER — for the curated layer
# ============================================
resource "aws_glue_crawler" "curated_taxi" {
  name          = "${var.project_name}-curated-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_crawler.arn
  description   = "Crawls curated NYC Taxi data and registers it in the catalog"

  s3_target {
    path = "s3://${aws_s3_bucket.curated.id}/yellow_taxi/"
  }

  configuration = jsonencode({
    Version = 1.0
    Grouping = {
      TableGroupingPolicy = "CombineCompatibleSchemas"
    }
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }
}