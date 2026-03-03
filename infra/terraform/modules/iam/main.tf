# IAM roles for Pulsecity platform
# - eks_cluster: EKS control plane
# - eks_node: worker nodes (EC2 + ECR read)
# - api_service: IRSA role for API pods (Secrets Manager + S3)
# - rds_monitoring: RDS enhanced monitoring

locals {
  prefix = "${var.project}-${var.environment}"
}

# ── EKS Cluster Role ─────────────────────────────────────────────────────────

data "aws_iam_policy_document" "eks_cluster_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_cluster" {
  name               = "${local.prefix}-eks-cluster-role"
  assume_role_policy = data.aws_iam_policy_document.eks_cluster_assume.json

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# ── EKS Node Role ─────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "eks_node_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_node" {
  name               = "${local.prefix}-eks-node-role"
  assume_role_policy = data.aws_iam_policy_document.eks_node_assume.json

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "eks_worker_node_policy" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "ecr_read_only" {
  role       = aws_iam_role.eks_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# ── API Service Role (IRSA) ───────────────────────────────────────────────────
# Allows API pods to read Secrets Manager and read/write ingestion batch bucket

data "aws_iam_policy_document" "api_service_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.eks_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(var.eks_oidc_provider_arn, "arn:aws:iam::${var.aws_account_id}:oidc-provider/", "")}:sub"
      values   = ["system:serviceaccount:pulsecity:api"]
    }
  }
}

resource "aws_iam_role" "api_service" {
  name               = "${local.prefix}-api-service-role"
  assume_role_policy = data.aws_iam_policy_document.api_service_assume.json

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "api_service_permissions" {
  statement {
    sid     = "SecretsManagerRead"
    actions = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:${local.prefix}/*"
    ]
  }

  statement {
    sid     = "S3BatchesAccess"
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject"]
    resources = [
      var.s3_batches_bucket_arn,
      "${var.s3_batches_bucket_arn}/*"
    ]
  }
}

resource "aws_iam_role_policy" "api_service" {
  name   = "${local.prefix}-api-service-policy"
  role   = aws_iam_role.api_service.id
  policy = data.aws_iam_policy_document.api_service_permissions.json
}

# ── RDS Monitoring Role ───────────────────────────────────────────────────────

data "aws_iam_policy_document" "rds_monitoring_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["monitoring.rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rds_monitoring" {
  name               = "${local.prefix}-rds-monitoring-role"
  assume_role_policy = data.aws_iam_policy_document.rds_monitoring_assume.json

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
