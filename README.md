# Trading System

A comprehensive trading system that integrates news analysis, stock data management, and automated trade execution.

## System Components

### News Processing
- **News Scraper**: Scrapes financial news from multiple sources (Investing.com, TradingView, X/Twitter)
  - Location: `news_scraper/`
  - Components:
    - Multiple source-specific scrapers
    - News analysis
    - Trade policy implementation

- **News Store**: Processes and stores news data
  - Location: `news_store/`
  - Features:
    - Message queue consumer
    - News classification
    - Weaviate database integration

### Trading Infrastructure
- **Stock Hub**: Manages stock quotes and market data
  - Location: `stock_hub/`

- **Strategy Engine**: Implements trading strategies
  - Location: `strategy_engine/`
  - Features:
    - Alpaca trading integration
    - Backtesting capabilities
    - Live trading support
    - Task scheduling

- **Mock Executors**: Testing and simulation
  - Location: `mock_executor/` and `mock_executor2/`

### Technical Analysis
- **Indicators**: Technical analysis indicators library
  - Location: `indicators/`

- **Risk Management**: Risk assessment and management
  - Location: `risk_management/`

### Infrastructure
- **AWS Gateway**: Cloud integration
  - Location: `aws_gateway/`
  - Features:
    - API Gateway setup
    - S3 bucket policies
    - Relay server implementation

- **Protocol Buffers**: Service interfaces
  - Location: `proto/`
  - Defined services:
    - Analysis Push Gateway
    - Stock Hub
    - Trade Executor

- **Docker Support**: Containerization
  - Location: `docker/`
  - Available services:
    - Analyser
    - AWS Gateway
    - Mock Executor
    - News Store
    - RabbitMQ
    - Scraper
    - Stock Hub

## Setup and Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. For Rust components:
   ```bash
   cargo build
   ```

3. Docker deployment:
   ```bash
   cd docker
   docker-compose up
   ```

## Development

- Python components use Protocol Buffers for service definitions
- Rust is used for performance-critical components
- Docker containers are available for all major services
- AWS integration for cloud deployment

## Running the System

Use the provided shell script:
```bash
./run.sh
```

For development/debugging:
```bash
docker-compose -f docker/docker-compose-dbg.yml up
```

## Architecture

- Microservices architecture with containerized components
- Message queue (RabbitMQ) for asynchronous processing
- gRPC for service communication
- Weaviate for news data storage
- AWS integration for cloud deployment

## License

[Add your license information here]
