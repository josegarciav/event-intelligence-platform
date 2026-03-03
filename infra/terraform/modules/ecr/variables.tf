variable "project" {
  description = "Project name prefix"
  type        = string
  default     = "pulsecity"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "services" {
  description = "List of service names to create ECR repositories for"
  type        = list(string)
  default     = ["api", "admin", "scrapping"]
}

variable "image_tag_mutability" {
  description = "Tag mutability for repositories (MUTABLE or IMMUTABLE)"
  type        = string
  default     = "IMMUTABLE"
}

variable "lifecycle_untagged_days" {
  description = "Days to retain untagged images before expiry"
  type        = number
  default     = 7
}

variable "lifecycle_tagged_count" {
  description = "Number of tagged images to retain per repository"
  type        = number
  default     = 10
}
