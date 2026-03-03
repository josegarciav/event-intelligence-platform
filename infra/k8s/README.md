# Kubernetes Manifests — Pulsecity

This directory contains all Kubernetes manifests for the Pulsecity platform,
organized with [Kustomize](https://kustomize.io/) overlays for dev and prod.

## Architecture

```
External Traffic
      │
   [Ingress nginx]
      │
      ├──/──────────► [api Deployment x2]  ──► [postgres StatefulSet (dev) / RDS (prod)]
      │                        │
      │                        └─── internal ──► [admin Service]
      │
   [CronJob] ──► scrapping runs every 6h ──► data/batches/ (PVC)
```

## Directory Structure

```
base/        Core manifests — shared across all environments
overlays/
  dev/       Patches: 1 replica, local image tags, postgres StatefulSet enabled
  prod/      Patches: 2+ replicas, ECR image tags, RDS secrets
```

## Local Development with kind

```bash
# 1. Create cluster
kind create cluster --name pulsecity

# 2. Install nginx ingress controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# 3. Apply namespace
kubectl apply -f infra/k8s/namespace.yaml

# 4. Apply dev overlay
kubectl apply -k infra/k8s/overlays/dev/

# 5. Check status
kubectl get all -n pulsecity

# 6. Port-forward API for testing
kubectl port-forward -n pulsecity svc/api 8000:8000
```

## Deploying to EKS

```bash
# Configure kubeconfig
aws eks update-kubeconfig --region us-east-1 --name pulsecity-prod-eks

# Apply secrets first (fill in secrets.yaml.example → secrets.yaml, never commit)
kubectl apply -f infra/k8s/secrets.yaml

# Apply prod overlay
kubectl apply -k infra/k8s/overlays/prod/
```

## kubectl Cheat Sheet

```bash
# Get all resources in namespace
kubectl get all -n pulsecity

# View logs
kubectl logs -n pulsecity deploy/api -f

# Exec into a pod
kubectl exec -it -n pulsecity deploy/api -- /bin/bash

# Scale manually
kubectl scale -n pulsecity deploy/api --replicas=3

# Watch HPA
kubectl get hpa -n pulsecity -w

# Trigger CronJob manually
kubectl create job -n pulsecity --from=cronjob/scrapping scrapping-manual-$(date +%s)

# Describe failing pod
kubectl describe pod -n pulsecity -l app=api
```
