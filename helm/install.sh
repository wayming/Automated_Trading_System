# Install minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Install kubectl
sudo snap install kubectl --classic

# Start minikube
minikube start --cpus=4 --memory=8192 --driver=docker


# Verify
kubectl get nodes

# Install helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version

# Add Helm repo
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Install ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace


# Install metrics-server
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo update
helm install metrics-server metrics-server/metrics-server -n kube-system

# Add repository
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add weaviate https://weaviate.github.io/weaviate-helm
helm repo update

# Minikube docker shell
# eval $(minikube -p minikube docker-env)

