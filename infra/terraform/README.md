# Terraform — Pulsecity AWS Infrastructure

This directory codifies all AWS resources using Terraform, enabling reproducible,
version-controlled, and auditable infrastructure.

## What Terraform Does

Terraform reads `.tf` files, compares them against the current AWS state, and applies
only the changes needed. Every infra change goes through a PR like application code.

## Module Descriptions

| Module | Purpose |
|--------|---------|
| `modules/iam` | IAM roles for EKS cluster, worker nodes, API service (IRSA), and RDS monitoring |
| `modules/networking` | VPC, 2 public + 2 private subnets, Internet Gateway, NAT Gateway |
| `modules/eks` | EKS cluster + managed node group (t3.medium by default) |
| `modules/rds` | RDS PostgreSQL 16, configurable Multi-AZ, automated backups |
| `modules/ecr` | ECR repositories for api, admin, and scrapping images |

## Environments

- `environments/dev/` — single-AZ, smaller instances, no Multi-AZ RDS
- `environments/prod/` — multi-AZ, larger instances, RDS Multi-AZ enabled

## Workflow

```bash
# 1. Configure backend (copy and fill in backend.tf.example → backend.tf)
cp backend.tf.example environments/dev/backend.tf

# 2. Copy and fill in variables
cp environments/dev/terraform.tfvars.example environments/dev/terraform.tfvars

# 3. Initialize (downloads providers + modules)
cd environments/dev
terraform init

# 4. Preview changes
terraform plan

# 5. Apply
terraform apply

# 6. Destroy (tear down all resources)
terraform destroy
```

## Remote State (backend.tf.example)

State is stored in S3 with DynamoDB locking. Create these manually before first apply:

```bash
aws s3api create-bucket --bucket pulsecity-tfstate --region us-east-1
aws dynamodb create-table \
  --table-name pulsecity-tfstate-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

## Prerequisites

- [Terraform >= 1.6](https://developer.hashicorp.com/terraform/downloads)
- AWS CLI configured (`aws configure`)
- kubectl (for EKS access after apply)
