# Trade Helm Chart

This Helm chart deploys the Trade application services to Kubernetes

## Services Included

- **Scrapers**: News scrapers for investing.com and TradingView
- **analysers**: News analysers for processing scraped data
- **Core Services**: Mock executor, stock hub, AWS gateway, and news store
- **Infrastructure**: RabbitMQ message broker and Weaviate vector database

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PV provisioner support in the underlying infrastructure

## Installation

1. Clone the repository:
```bash
git clone https://github.com/wayming/trade.git
cd trade
```

2. Install the chart:
```bash
helm install trade ./helm
```

3. Or install with custom values:
```bash
helm install trade ./helm -f custom-values.yaml
```

## Configuration

The following table lists the configurable parameters and their default values:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.imageRegistry` | Global Docker image registry | `""` |
| `rabbitmq.enabled` | Enable RabbitMQ | `true` |
| `weaviate.enabled` | Enable Weaviate | `true` |
| `scrapers.ivscraper.enabled` | Enable IV scraper | `true` |
| `scrapers.tvscraper.enabled` | Enable TV scraper | `true` |

## Upgrading

To upgrade the release:
```bash
helm upgrade trade ./helm
```

## Uninstalling

To uninstall the release:
```bash
helm uninstall trade
```

## Architecture

The chart deploys services in the following order:
1. Network policies
2. Persistent volumes
3. RabbitMQ (message broker)
4. Weaviate (vector database)
5. Scrapers (with Xvfb for headless browsing)
6. analysers
7. Core services

## Networking

- RabbitMQ management UI: Port 15672
- Weaviate: Port 8080 (HTTP), 50051 (gRPC)
- Mock Executor: Port 50051
- Stock Hub: Port 50052
- AWS Gateway: Port 50053

## Storage

The chart creates persistent volumes for:
- `/app/output` - Shared output directory
- RabbitMQ data
- Weaviate data

## Health Checks

RabbitMQ includes health checks. Other services depend on RabbitMQ being ready before starting.
