use dashmap::DashMap;
use tokio::sync::Mutex;
use std::sync::Arc;
use std::collections::HashMap;
use chrono::Local;

use tonic::{transport::Server, Request, Response, Status};
use trading_executor::trade_executor_server::{TradeExecutor, TradeExecutorServer};
use trading_executor::{TradeRequest, TradeResponse};
use stock_hub::stock_quote_client::StockQuoteClient;
use stock_hub::QuoteRequest;

pub mod trading_executor {
    tonic::include_proto!("trading_executor");
}

pub mod stock_hub {
    tonic::include_proto!("stock_hub");
}

#[derive(Debug, Default)]
pub struct TradingEngine {
    cash: Arc<Mutex<f64>>,
    portfolio: Arc<DashMap<String, f64>>,
}

#[tonic::async_trait]
impl TradeExecutor for TradingEngine {
    async fn execute_trade(
        &self,
        request: Request<TradeRequest>,
    ) -> Result<Response<TradeResponse>, Status> {
        let req = request.into_inner();
        let symbol = req.symbol;
        let trade = req.trade.to_lowercase();
        let amount = req.amount;

        // Lock the cash directly inside this function
        let mut cash = self.cash.lock().await;

        // Quote price
        let mut quote_client = StockQuoteClient::connect("http://stock_hub:50052")
            .await
            .map_err(|e| Status::internal(format!("Failed to connect to quote service: {}", e)))?;
        
        let quote_response = quote_client
            .get_quote(Request::new(QuoteRequest {
                symbol: symbol.clone(),
            }))
            .await
            .map_err(|e| Status::internal(format!("Quote error: {}", e)))?
            .into_inner();
        
        let price = quote_response.price;

        match trade.as_str() {
            "buy" => {
                let cost = price * amount;
                if *cash >= cost {
                    *cash -= cost;
                    self.portfolio
                        .entry(symbol.clone())
                        .and_modify(|q| *q += amount)
                        .or_insert(amount);
                    println!("Bought {} shares of {} at price {} at {}",
                        amount, symbol, price, Local::now().format("%Y-%m-%d %H:%M:%S") );
                } else {
                    self.show_portfolio().await;
                    return Err(Status::invalid_argument("Insufficient funds"));
                }
            }
            "sell" => {
                let holding = self.portfolio.get_mut(&symbol);
                match holding {
                    Some(mut h) if *h >= amount => {
                        *h -= amount;
                        *cash += price * amount;
                        println!("Sold {} shares of {}", amount, symbol);
                    }
                    _ => {
                        self.show_portfolio().await;
                        return Err(Status::invalid_argument("Not enough holdings"));
                    }
                }
            }
            _ => return Err(Status::invalid_argument("Trade must be 'buy' or 'sell'")),
        }

        let port_map = self
            .portfolio
            .iter()
            .map(|entry| (entry.key().clone(), *entry.value()))
            .collect::<HashMap<_, _>>();

        println!("Cash balance: {:.2}", cash);
        self.show_portfolio().await;

        Ok(Response::new(TradeResponse {
            message: "Trade executed".to_string(),
            cash_balance: *cash,
            portfolio: port_map,
        }))
    }
}

// ✅ Non-trait methods
impl TradingEngine {
    pub async fn get_portfolio(&self) -> HashMap<String, f64> {
        self.portfolio
            .iter()
            .map(|entry| (entry.key().clone(), *entry.value()))
            .collect()
    }

    pub async fn show_portfolio(&self) {
        println!("Portfolio:");
        for entry in self.portfolio.iter() {
            println!("  {}: {:.2}", entry.key(), entry.value());
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let engine = TradingEngine {
        cash: Arc::new(Mutex::new(10_000_000.0)),
        portfolio: Arc::new(DashMap::new()),
    };
    println!("Server running on [::1]:50051");
    Server::builder()
        .add_service(TradeExecutorServer::new(engine))
        .serve("[::]:50051".parse()?)
        .await?;
    Ok(())
}
