output "eks_cluster_role_arn" {
  description = "ARN of the EKS cluster IAM role"
  value       = aws_iam_role.eks_cluster.arn
}

output "eks_node_role_arn" {
  description = "ARN of the EKS worker node IAM role"
  value       = aws_iam_role.eks_node.arn
}

output "api_service_role_arn" {
  description = "ARN of the API service IRSA role"
  value       = aws_iam_role.api_service.arn
}

output "rds_monitoring_role_arn" {
  description = "ARN of the RDS enhanced monitoring role"
  value       = aws_iam_role.rds_monitoring.arn
}
