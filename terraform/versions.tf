terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  backend "s3" {
    bucket         = "nyc-taxi-pipeline-tfstate-ake-2026-05"
    key            = "main/terraform.tfstate"
    region         = "eu-west-3"
    dynamodb_table = "nyc-taxi-pipeline-tfstate-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Owner       = "achraf-elkhatabi"
    }
  }
}