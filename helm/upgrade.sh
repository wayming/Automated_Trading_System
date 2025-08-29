# kubectl rollout restart deployment -n default


# kubectl scale deployment --all --replicas=0 -n default

# kubectl delete pods --all

# helm uninstall tsrade .

helm template trade . -f values.yaml > out.yaml

helm upgrade --install trade . \
  --set scrapers.tvscraper.tradeViewUser=${TRADE_VIEW_USER} \
  --set scrapers.tvscraper.tradeViewPass=${TRADE_VIEW_PASS}
