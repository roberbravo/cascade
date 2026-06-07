#!/bin/bash

echo "================================================"
echo "  Cascade - Uninstall"
echo "================================================"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${YELLOW}→${NC} $1"; }

export KUBECONFIG=~/.kube/config

# 1. Delete ArgoCD applications
info "Deleting ArgoCD applications..."
kubectl delete application --all -n argocd --ignore-not-found
log "ArgoCD applications deleted"

# 2. Delete namespaces
info "Deleting namespaces..."
kubectl delete namespace argo argocd grafana postgres pipeline-builder --ignore-not-found
log "Namespaces deleted"

# 3. Delete cluster roles
info "Cleaning up cluster roles..."
kubectl delete clusterrole pipeline-builder-role --ignore-not-found
kubectl delete clusterrolebinding pipeline-builder-binding --ignore-not-found
kubectl delete clusterrole argo-workflow-role --ignore-not-found
kubectl delete clusterrolebinding argo-workflow-binding --ignore-not-found
log "Cluster roles deleted"

echo ""
echo "================================================"
echo "  Cascade uninstalled successfully"
echo "================================================"
