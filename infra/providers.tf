 terraform {
   required_version = ">= 1.6.0"

   required_providers {
    aws = {
       source  = "hashicorp/aws"
       version = ">= 5.0.0"
    }
    # Optional: Databricks later
    # databricks = {
    #   source  = "databricks/databricks"
    #   version = "~> 1.40"
    # }
   }
 }

provider "aws" {
  region = var.aws_region
  profile = var.aws_profile # must match your local AWS CLI profile name  
}

# Opitional: Databricks provider (advanced)
# provider "databricks: {
#   host = var.databricks_host   # e.g. https://<workspace>.databricks.com
#   token = var.databricks_token # store in env var or tfvars, not in code
# }
 