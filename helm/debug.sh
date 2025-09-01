kubectl port-forward svc/argocd-server -n default 8080:443
kubectl port-forward svc/trade-selenium-hub -n default 4444:4444
kubectl port-forward svc/trade-rabbitmq -n default 25672:15672



helm template trade . -f values.yaml --debug \
  --set scrapers.tvscraper.tradeViewUser=${TRADE_VIEW_USER} \
  --set scrapers.tvscraper.tradeViewPass=${TRADE_VIEW_PASS} \
  --set global.deepseekApiKey=${DEEPSEEK_API_KEY} > rendered.yaml

helm get manifest trade

# show images
kubectl get pods -n default -o jsonpath="{range .items[*]}{.metadata.name}{':\t'}{range .spec.containers[*]}{.image}{' '}{end}{'\n'}{end}"

minikube mount /host/path/to/pv:/mount