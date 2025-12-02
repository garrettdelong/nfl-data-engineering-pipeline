variable "aws_region" {
    type = string
    description = "AWS region where resources will be created"
    default = "us-west-2"
}

variable "aws_profile" {
    type = string
    description = "Name of the AWS CLI profile to use"
    default = "default" 
}

variable "project_name" {
    type = string
    description = "Project name used for tagging and naming"
    default = "nfl-data-pipeline"
}

variable "raw_bucket_name" {
    type = string
    description = "S3 bucket for raw NFL data"
    default = "nfl-pipeline-raw"
}

variable "processed_bucket_name" {
    type = string
    description = "S3 bucket for processed NFL data"
    default = "nfl-pipeline-processed"
}

# For Snowflake external stage intgeration
variable "snowflake_external_role_name" {
    type = string
    description = "IAM role name for Snowflake S3 access"
    default = "snowflake-nfl-external-role"
}
