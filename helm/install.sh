# 安装 minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# 安装 kubectl
sudo snap install kubectl --classic

# 安装 argocd
sudo snap install argocd --classic

# 启动集群
minikube start --cpus=4 --memory=8192 --driver=docker


# 验证
kubectl get nodes

# 启用插件
minikube addons enable ingress
minikube addons enable metrics-server

# 安装 helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# 验证
helm version

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