/*
# Trust policy: who can assume this role (Snowflake side)
data "aws_iam_policy_document" "snowflake_assume_role" {
    statement {
        effect = "Allow"

        principals {
            type = "AWS"
            identifiers = [ 
                # Replace this with Snowflake's AWS IAM user/role ARN,
                # which you'll get from Snowflake when you set up the external stage
                "arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME"
            ]
        }

        actions = ["sts:AssumeRole"]
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
*/
