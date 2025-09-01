kubectl get service trade-app-selenium-hub -n default -o yaml > actual-service.yaml

helm template ../helm --values ../helm/values.yaml | yq e 'select(.kind == "Service" and .metadata.name == "trade-app-selenium-hub")' - > expected-service.yaml

argocd app diff trade-app --local ./helm

argocd app history trade-app

kubectl get pods -n default -l app=trade-app -o jsonpath='{.items[*].spec.containers[*].image}'

argocd app sync trade-app --prune