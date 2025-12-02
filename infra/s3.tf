resource "aws_s3_bucket" "raw" {
    bucket = var.raw_bucket_name

    tags = merge(local.common_tags,  {
        Purpose = "raw"
    })
}

resource "aws_s3_bucket" "processed" {
    bucket = var.processed_bucket_name

    tags = merge(local.common_tags, {
        Purpose = "processed"
    })
}

# Block public access to the buckets
resource "aws_s3_bucket_public_access_block" "raw_block" {
    bucket = aws_s3_bucket.raw.id
    block_public_acls = true
    block_public_policy = true
    ignore_public_acls = true
    restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "processed_block" {
    bucket = aws_s3_bucket.processed.id
    block_public_acls = true
    block_public_policy = true
    ignore_public_acls = true
    restrict_public_buckets = true
}
