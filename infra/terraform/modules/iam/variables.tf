variable "project" {
  description = "Project name used as a prefix for all IAM resources"
  type        = string
  default     = "pulsecity"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID (used for IRSA trust policy)"
  type        = string
}

variable "eks_oidc_provider_arn" {
  description = "ARN of the EKS OIDC provider (for IRSA)"
  type        = string
  default     = ""
}

variable "s3_batches_bucket_arn" {
  description = "ARN of the S3 bucket used for ingestion batches"
  type        = string
  default     = "*"
}
