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

  # Uncomment and fill backend.tf after creating S3 bucket + DynamoDB table.
  # Copy backend.tf.example → backend.tf at the repo root.
  # backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      ManagedBy   = "terraform"
      Project     = "pulsecity"
      Environment = "dev"
    }
  }
}

# ── IAM ───────────────────────────────────────────────────────────────────────

module "iam" {
  source = "../../modules/iam"

  project        = "pulsecity"
  environment    = "dev"
  aws_region     = var.aws_region
  aws_account_id = var.aws_account_id

  # OIDC provider is created by the EKS module; reference its output once available.
  # eks_oidc_provider_arn = module.eks.oidc_provider_arn
}

# ── Networking ────────────────────────────────────────────────────────────────

module "networking" {
  source = "../../modules/networking"

  project     = "pulsecity"
  environment = "dev"

  vpc_cidr             = "10.0.0.0/16"
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
  availability_zones   = ["${var.aws_region}a", "${var.aws_region}b"]
}

# ── EKS ───────────────────────────────────────────────────────────────────────

module "eks" {
  source = "../../modules/eks"

  project     = "pulsecity"
  environment = "dev"

  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids
  public_subnet_ids  = module.networking.public_subnet_ids

  eks_cluster_role_arn = module.iam.eks_cluster_role_arn
  eks_node_role_arn    = module.iam.eks_node_role_arn

  # Dev: smaller nodes, fewer replicas
  node_instance_type = "t3.medium"
  node_desired_size  = 2
  node_min_size      = 1
  node_max_size      = 3
}

# ── RDS ───────────────────────────────────────────────────────────────────────

module "rds" {
  source = "../../modules/rds"

  project     = "pulsecity"
  environment = "dev"

  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids

  db_password         = var.db_password
  monitoring_role_arn = module.iam.rds_monitoring_role_arn

  # Dev: single-AZ, small instance
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  multi_az          = false
}

# ── ECR ───────────────────────────────────────────────────────────────────────

module "ecr" {
  source = "../../modules/ecr"

  project     = "pulsecity"
  environment = "dev"
  services    = ["api", "admin", "scrapping"]
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
