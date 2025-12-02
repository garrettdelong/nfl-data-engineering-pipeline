output "raw_bucket_name" {
    value = aws_s3_bucket.raw.bucket
    description = "Raw NFL data bucket"
}

output "processed_bucket_name" {
    value = aws_s3_bucket.processed.bucket
    description = "Processed NFL data bucket"
}
/*
output "snowflake_external_role_arn" {
    value = aws_iam_role.snowflake_external_role.arn
    description = "IAM role ARN Snowflake should assume"
}
*/
