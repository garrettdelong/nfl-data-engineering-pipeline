# Trust policy: who can assume this role (Snowflake side)
data "aws_iam_policy_document" "snowflake_assume_role" {
    statement {
        effect = "Allow"

        principals {
            type = "AWS"
            identifiers = [ 
                var.snowflake_principal_arn
            ]
        }

        actions = ["sts:AssumeRole"]

        condition {
            test = "StringEquals"
            variable = "sts:ExternalId"
            values = [var.snowflake_external_id]
        }
    }
}

resource "aws_iam_role" "snowflake_external_role" {
    name = var.snowflake_external_role_name
    assume_role_policy = data.aws_iam_policy_document.snowflake_assume_role.json

    tags = local.common_tags
}

# Permissions for this role to read from the raw bucket
data "aws_iam_policy_document" "snowflake_s3_access" {
    statement {
        effect = "Allow"
        
        actions = [
            "s3:GetObject",
            "s3:ListBucket"
        ]

        resources = [
            aws_s3_bucket.raw.arn,
            "${aws_s3_bucket.raw.arn}/*"
        ]
    }
}

resource "aws_iam_policy" "snowflake_s3_policy" {
    name = "${var.project_name}-snowflake-s3-access"
    policy = data.aws_iam_policy_document.snowflake_s3_access.json
}

resource "aws_iam_role_policy_attachment" "snowflake_s3_attach" {
    role = aws_iam_role.snowflake_external_role.name
    policy_arn = aws_iam_policy.snowflake_s3_policy.arn
}
