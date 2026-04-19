#!/bin/bash
set -e

echo "================================================"
echo "  Cascade - Automatic Installation"
echo "================================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${YELLOW}→${NC} $1"; }

# 1. Install k3s
info "Installing k3s..."
curl -sfL https://get.k3s.io | sh -
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
export KUBECONFIG=~/.kube/config
log "k3s installed"

# Wait for k3s to be ready
info "Waiting for k3s to be ready..."
sleep 30
kubectl wait --for=condition=Ready nodes --all --timeout=120s
log "k3s ready"

# 2. Install ArgoCD
info "Installing ArgoCD..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

info "Waiting for ArgoCD to be ready..."
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=180s
log "ArgoCD installed"

# 3. Expose ArgoCD on NodePort 30900
info "Exposing ArgoCD..."
kubectl patch svc argocd-server -n argocd --type='json' \
  -p='[{"op": "replace", "path": "/spec/type", "value": "NodePort"}, {"op": "add", "path": "/spec/ports/0/nodePort", "value": 30900}]'
log "ArgoCD available at http://$(hostname -I | awk '{print $1}'):30900"

# 4. Get ArgoCD password
ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)
log "ArgoCD password: ${ARGOCD_PASSWORD}"

# 5. Apply App of Apps
info "Applying App of Apps..."
kubectl apply -f https://raw.githubusercontent.com/roberbravo/cascade/master/k3s/argocd/root-app.yaml
log "App of Apps applied - ArgoCD will deploy the full stack"

echo ""
echo "================================================"
echo "  Installation Completed!!"
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
