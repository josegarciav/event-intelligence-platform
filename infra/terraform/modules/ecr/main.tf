# ECR repositories for all platform services

locals {
  prefix = "${var.project}-${var.environment}"
}

resource "aws_ecr_repository" "services" {
  for_each = toset(var.services)

  name                 = "${local.prefix}-${each.key}"
  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Service     = each.key
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_ecr_lifecycle_policy" "services" {
  for_each   = aws_ecr_repository.services
  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after ${var.lifecycle_untagged_days} days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.lifecycle_untagged_days
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only ${var.lifecycle_tagged_count} tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = var.lifecycle_tagged_count
        }
        action = { type = "expire" }
      }
    ]
  })
}
