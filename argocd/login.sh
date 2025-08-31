pass=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo)
echo $pass
url=$(kubectl get svc argocd-server -n argocd -o jsonpath='{.spec.ports[0].nodePort}' | xargs -I{} echo "$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}'):{}")
echo $url
argocd login $url --username admin --password $pass --insecure