terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # backend "s3" {}  # Fill in backend.tf from backend.tf.example
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      ManagedBy   = "terraform"
      Project     = "pulsecity"
      Environment = "prod"
    }
  }
}

# ── IAM ───────────────────────────────────────────────────────────────────────

module "iam" {
  source = "../../modules/iam"

  project        = "pulsecity"
  environment    = "prod"
  aws_region     = var.aws_region
  aws_account_id = var.aws_account_id
}

# ── Networking ────────────────────────────────────────────────────────────────

module "networking" {
  source = "../../modules/networking"

  project     = "pulsecity"
  environment = "prod"

  vpc_cidr             = "10.1.0.0/16"
  public_subnet_cidrs  = ["10.1.1.0/24", "10.1.2.0/24"]
  private_subnet_cidrs = ["10.1.10.0/24", "10.1.11.0/24"]
  availability_zones   = ["${var.aws_region}a", "${var.aws_region}b"]
}

# ── EKS ───────────────────────────────────────────────────────────────────────

module "eks" {
  source = "../../modules/eks"

  project     = "pulsecity"
  environment = "prod"

  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  public_subnet_ids  = module.networking.public_subnet_ids

  eks_cluster_role_arn = module.iam.eks_cluster_role_arn
  eks_node_role_arn    = module.iam.eks_node_role_arn

  # Prod: larger nodes, more replicas
  node_instance_type = "t3.large"
  node_desired_size  = 3
  node_min_size      = 2
  node_max_size      = 10
}

# ── RDS ───────────────────────────────────────────────────────────────────────

module "rds" {
  source = "../../modules/rds"

  project     = "pulsecity"
  environment = "prod"

  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids

  db_password         = var.db_password
  monitoring_role_arn = module.iam.rds_monitoring_role_arn

  # Prod: Multi-AZ, larger instance, more storage
  instance_class    = "db.t3.small"
  allocated_storage = 100
  multi_az          = true
}

# ── ECR ───────────────────────────────────────────────────────────────────────

module "ecr" {
  source = "../../modules/ecr"

  project     = "pulsecity"
  environment = "prod"
  services    = ["api", "admin", "scrapping"]

  # Prod: keep more tagged images
  lifecycle_tagged_count = 20
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  value     = module.rds.db_endpoint
  sensitive = true
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}
