output "raw_bucket_name" {
  description = "Name of the S3 bucket for raw data"
  value       = aws_s3_bucket.raw.id
}

output "curated_bucket_name" {
  description = "Name of the S3 bucket for curated data"
  value       = aws_s3_bucket.curated.id
}

output "aws_region" {
  description = "AWS region used"
  value       = var.aws_region
}

output "glue_database_name" {
  description = "Name of the Glue catalog database"
  value       = aws_glue_catalog_database.main.name
}

output "glue_crawler_name" {
  description = "Name of the Glue crawler"
  value       = aws_glue_crawler.raw_taxi.name
}

output "athena_workgroup_name" {
  description = "Name of the Athena workgroup"
  value       = aws_athena_workgroup.main.name
}

output "athena_results_bucket" {
  description = "S3 bucket where Athena query results are stored"
  value       = aws_s3_bucket.athena_results.id
}