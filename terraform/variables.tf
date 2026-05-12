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

variable "github_owner" {
  description = "GitHub username or org owning the repo"
  type        = string
  default     = "Achraf-EL-KHATABI"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "aws-nyc-taxi-pipeline"
}

variable "notification_email" {
  description = "Email address for pipeline notifications"
  type        = string
}