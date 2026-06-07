#!/bin/bash
set -e

echo "================================================"
echo "  Cascade - Automatic Installation"
echo "================================================"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${YELLOW}→${NC} $1"; }

export KUBECONFIG=~/.kube/config

# 1. Install ArgoCD
info "Installing ArgoCD..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml || true

info "Waiting for ArgoCD to be ready..."
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=argocd-server -n argocd --timeout=180s
log "ArgoCD installed"

# 2. Expose ArgoCD on NodePort 30900
info "Exposing ArgoCD..."
kubectl patch svc argocd-server -n argocd --type='json' \
  -p='[{"op": "replace", "path": "/spec/type", "value": "NodePort"}, {"op": "add", "path": "/spec/ports/0/nodePort", "value": 30900}]'
log "ArgoCD available at http://$(hostname -I | awk '{print $1}'):30900"

# 3. Get ArgoCD password
ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
log "ArgoCD password: ${ARGOCD_PASSWORD}"

# 4. Apply App of Apps
info "Applying App of Apps..."
kubectl apply -f https://raw.githubusercontent.com/roberbravo/cascade/master/k3s/argocd/root-app.yaml
log "App of Apps applied - ArgoCD will deploy the full stack"

echo ""
echo "================================================"
echo "  Installation Completed"
echo "================================================"
echo ""
echo "  ArgoCD:           http://$(hostname -I | awk '{print $1}'):30900"
echo "  User:             admin"
echo "  Password:         ${ARGOCD_PASSWORD}"
echo ""
echo "  In 2-3 minutes the following will be available:"
echo "  Pipeline Builder: http://$(hostname -I | awk '{print $1}'):30888"
echo "  Argo Workflows:   http://$(hostname -I | awk '{print $1}'):30800"
echo "  Grafana:          http://$(hostname -I | awk '{print $1}'):30300"
echo "  Grafana login:    admin / cascade123"
echo "================================================"
