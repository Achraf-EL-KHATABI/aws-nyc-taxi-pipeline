# ============================================
# QUICKSIGHT — IAM permissions for service role
# ============================================
#
# Note: QuickSight is mostly UI-driven, but a few things benefit from IaC:
# - The IAM service role permissions on data sources (Athena, S3)
# - A dedicated workgroup for QuickSight queries (cost isolation)
# - The data source registration (athena connection)
#
# Dashboards themselves are created via the QuickSight console — this is
# the standard AWS pattern as of 2026.

# Athena workgroup dedicated to QuickSight queries
# Isolates QuickSight cost from analyst ad-hoc queries
resource "aws_athena_workgroup" "quicksight" {
  name = "${var.project_name}-quicksight"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.id}/quicksight/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    bytes_scanned_cutoff_per_query = 1073741824 # 1 GB
  }

  force_destroy = true
}

# Data source: register Athena as a QuickSight data source
# This creates the "connection" — datasets are created on top later (console)
resource "aws_quicksight_data_source" "athena" {
  data_source_id = "${var.project_name}-athena"
  name           = "${var.project_name}-athena"
  type           = "ATHENA"

  parameters {
    athena {
      work_group = aws_athena_workgroup.quicksight.name
    }
  }

  permission {
    actions = [
      "quicksight:DescribeDataSource",
      "quicksight:DescribeDataSourcePermissions",
      "quicksight:PassDataSource",
      "quicksight:UpdateDataSource",
      "quicksight:DeleteDataSource",
      "quicksight:UpdateDataSourcePermissions",
    ]
    principal = "arn:aws:quicksight:${var.aws_region}:${data.aws_caller_identity.current.account_id}:user/default/${var.quicksight_username}"
  }
}

# Get current AWS account ID (used in QuickSight ARNs)
data "aws_caller_identity" "current" {}