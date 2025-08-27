helm upgrade --install trade . \
  --set scrapers.tvscraper.tradeViewUser=${TRADE_VIEW_USER} \
  --set scrapers.tvscraper.tradeViewPass=${TRADE_VIEW_PASS}