kubectl port-forward svc/argocd-server -n default 8080:443
kubectl port-forward svc/trade-selenium-hub -n default 4444:4444
kubectl port-forward svc/trade-rabbitmq -n default 25672:15672



helm template  trade . -f values.yaml --debug  > rendered.yaml

helm get manifest trade

minikube mount /host/path/to/pv:/mount