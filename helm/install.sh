# 安装 minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# 安装 kubectl
sudo snap install kubectl --classic

# 安装 argocd client
VERSION=$(curl -L -s https://raw.githubusercontent.com/argoproj/argo-cd/stable/VERSION)
curl -sSL -o argocd-linux-amd64 \
  https://github.com/argoproj/argo-cd/releases/download/v$VERSION/argocd-linux-amd64
sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd
rm argocd-linux-amd64


# 启动集群
minikube start --cpus=4 --memory=8192 --driver=docker


# 验证
kubectl get nodes

# 安装 helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# 验证
helm version

# 添加 Helm repo
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# 安装 ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace


# 安装 metrics-server
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo update
helm install metrics-server metrics-server/metrics-server -n kube-system


# 创建 argocd namespace
kubectl create namespace argocd
# 安装 argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
# 获取初始密码
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

# # 暴露 UI（端口转发）
# kubectl port-forward svc/argocd-server -n argocd 8080:443

# 添加仓库
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add weaviate https://weaviate.github.io/weaviate-helm
helm repo update

# minikube docker shell
# eval $(minikube -p minikube docker-env)