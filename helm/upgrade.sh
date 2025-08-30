# kubectl rollout restart deployment -n default
# kubectl rollout restart statefulset -n default


# kubectl scale deployment --all --replicas=0 -n default

# kubectl delete pods --all

# helm uninstall tsrade .

helm template trade . -f values.yaml > out.yaml

kubectl delete deployment,rs,pod -l app.kubernetes.io/instance=trade --ignore-not-found

helm upgrade --install trade . --history-max=1 \
  --set scrapers.tvscraper.tradeViewUser=${TRADE_VIEW_USER} \
  --set scrapers.tvscraper.tradeViewPass=${TRADE_VIEW_PASS} \
  --set global.deepseekApiKey=${DEEPSEEK_API_KEY}