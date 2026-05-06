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