terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

provider "aws" {
  region = "eu-west-3"

  default_tags {
    tags = {
      Project   = "nyc-taxi-pipeline"
      Purpose   = "terraform-backend"
      ManagedBy = "Terraform"
      Owner     = "achraf-elkhatabi"
    }
  }
}

# ============================================
# S3 bucket holding the Terraform state file
# ============================================
resource "aws_s3_bucket" "tfstate" {
  bucket = "nyc-taxi-pipeline-tfstate-ake-2026-05"

  # Backend bucket should NEVER be force_destroyed by accident
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ============================================
# DynamoDB table for state locking
# ============================================
resource "aws_dynamodb_table" "tfstate_lock" {
  name         = "nyc-taxi-pipeline-tfstate-lock"
  billing_mode = "PAY_PER_REQUEST"  # essentially free at this scale
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
}