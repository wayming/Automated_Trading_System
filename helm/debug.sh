kubectl port-forward svc/argocd-server -n default 8080:443
kubectl port-forward svc/trade-app-selenium-hub -n default 4444:4444
kubectl port-forward svc/trade-app-rabbitmq -n default 25672:15672



helm template trade . -f values.yaml --debug > rendered.yaml

helm get manifest trade

# show images
kubectl get pods -n default -o jsonpath="{range .items[*]}{.metadata.name}{':\t'}{range .spec.containers[*]}{.image}{' '}{end}{'\n'}{end}"

minikube mount /host/path/to/pv:/mount

# create a debug container
kubectl debug -it trade-app-aws-gateway-75ccf79498-w9vvj --image=busybox --target=aws-gateway -- sh