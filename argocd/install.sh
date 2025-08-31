

# Install argocd client
VERSION=$(curl -L -s https://raw.githubusercontent.com/argoproj/argo-cd/stable/VERSION)
curl -sSL -o argocd-linux-amd64 \
  https://github.com/argoproj/argo-cd/releases/download/v$VERSION/argocd-linux-amd64
sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd
rm argocd-linux-amd64

# Create argocd namespace
kubectl create namespace argocd
# Install argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
# Get initial password
pass=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo)
echo $pass

kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "NodePort"}}'
kubectl get svc argocd-server -n argocd
url=$(kubectl get svc argocd-server -n argocd -o jsonpath='{.spec.ports[0].nodePort}' | xargs -I{} echo "$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}'):{}")
echo $url

argocd login $url --username admin --password $pass
# argocd account update-password --account admin --current-password <INITIAL_PASSWORD> --new-password <NEW_SECURE_PASSWORD>


kubectl apply -f argocd-app.yaml
argocd app list
argocd app get trade-app
argocd app logs trade-app

argocd app set trade-app --sync-policy automated
argocd app set trade-app --auto-prune
argocd app set trade-app --self-heal

argocd app sync trade-app



