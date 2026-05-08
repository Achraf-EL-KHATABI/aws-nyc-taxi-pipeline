# ============================================
# ATHENA — workgroup for queries + S3 results bucket
# ============================================
resource "aws_s3_bucket" "athena_results" {
  bucket        = "${var.project_name}-athena-results-${var.bucket_suffix}"
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle: auto-delete query results after 30 days to control costs
resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "expire-old-results"
    status = "Enabled"

    filter {}

    expiration {
      days = 30
    }
  }
}

resource "aws_athena_workgroup" "main" {
  name = "${var.project_name}-workgroup"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.id}/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    # Cost guardrail: cap a single query at 1 GB scanned
    bytes_scanned_cutoff_per_query = 1073741824
  }

  force_destroy = true
}