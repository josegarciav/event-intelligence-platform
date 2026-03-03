variable "project" {
  description = "Project name prefix"
  type        = string
  default     = "pulsecity"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for the RDS subnet group"
  type        = list(string)
}

variable "db_name" {
  description = "Initial database name"
  type        = string
  default     = "pulsecity"
}

variable "db_username" {
  description = "Master DB username"
  type        = string
  default     = "pulsecity_admin"
}

variable "db_password" {
  description = "Master DB password (store in tfvars, never commit)"
  type        = string
  sensitive   = true
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  description = "Allocated storage in GiB"
  type        = number
  default     = 20
}

variable "multi_az" {
  description = "Enable Multi-AZ for high availability"
  type        = bool
  default     = false
}

variable "monitoring_role_arn" {
  description = "IAM role ARN for RDS enhanced monitoring"
  type        = string
}

variable "eks_node_sg_id" {
  description = "Security group ID of EKS nodes (allowed DB access)"
  type        = string
  default     = ""
}
