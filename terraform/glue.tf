# ============================================
# GLUE DATABASE — namespace for catalog tables
# ============================================
resource "aws_glue_catalog_database" "main" {
  name        = replace("${var.project_name}_${var.environment}", "-", "_")
  description = "Catalog database for NYC Taxi pipeline"
}

# ============================================
# IAM ROLE — for the Glue Crawler
# ============================================
data "aws_iam_policy_document" "glue_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue_crawler" {
  name               = "${var.project_name}-glue-crawler-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
}

# AWS-managed policy granting standard Glue permissions
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Custom policy: only allow read on OUR raw bucket (least privilege)
data "aws_iam_policy_document" "glue_s3_access" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.raw.arn,
      "${aws_s3_bucket.raw.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "glue_s3_access" {
  name   = "${var.project_name}-glue-s3-access"
  role   = aws_iam_role.glue_crawler.id
  policy = data.aws_iam_policy_document.glue_s3_access.json
}

# ============================================
# GLUE CRAWLER — scans S3 and builds catalog tables
# ============================================
resource "aws_glue_crawler" "raw_taxi" {
  name          = "${var.project_name}-raw-crawler"
  database_name = aws_glue_catalog_database.main.name
  role          = aws_iam_role.glue_crawler.arn
  description   = "Crawls raw NYC Taxi data and registers it in the catalog"

  s3_target {
    path = "s3://${aws_s3_bucket.raw.id}/"
  }

  # Treat Hive partitions (taxi_type=, year=, month=) as table partitions
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