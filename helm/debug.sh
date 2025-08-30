helm template  trade . -f values.yaml --debug  > rendered.yaml

helm get manifest trade