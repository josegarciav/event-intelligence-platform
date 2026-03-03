# RDS PostgreSQL 16 with optional Multi-AZ

locals {
  prefix = "${var.project}-${var.environment}"
}

# ── Security Group ────────────────────────────────────────────────────────────

resource "aws_security_group" "rds" {
  name        = "${local.prefix}-rds-sg"
  description = "Allow PostgreSQL access from EKS nodes"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from EKS nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.eks_node_sg_id != "" ? [var.eks_node_sg_id] : []
    cidr_blocks     = var.eks_node_sg_id == "" ? ["10.0.0.0/8"] : []
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${local.prefix}-rds-sg"
    Project     = var.project
    Environment = var.environment
  }
}

# ── Subnet Group ──────────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name       = "${local.prefix}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name        = "${local.prefix}-db-subnet-group"
    Project     = var.project
    Environment = var.environment
  }
}

# ── Parameter Group ───────────────────────────────────────────────────────────

resource "aws_db_parameter_group" "main" {
  name   = "${local.prefix}-pg16"
  family = "postgres16"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000" # log queries > 1s
  }

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# ── RDS Instance ──────────────────────────────────────────────────────────────

resource "aws_db_instance" "main" {
  identifier = "${local.prefix}-postgres"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.allocated_storage * 5 # autoscaling cap
  storage_type          = "gp3"
  storage_encrypted     = true

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.main.name

  backup_retention_period = var.environment == "prod" ? 14 : 3
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  monitoring_interval = 60
  monitoring_role_arn = var.monitoring_role_arn

  deletion_protection = var.environment == "prod"
  skip_final_snapshot = var.environment != "prod"

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}
