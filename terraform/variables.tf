variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-3"
}

variable "project_name" {
  description = "Project name, used as prefix for resources"
  type        = string
  default     = "nyc-taxi-pipeline"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "bucket_suffix" {
  description = "Unique suffix for S3 bucket names (S3 names are globally unique)"
  type        = string
}