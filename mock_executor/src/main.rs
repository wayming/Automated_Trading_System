use tonic::{transport::Server, Request, Response, Status};
use trading::trade_executor_server::{TradeExecutor, TradeExecutorServer}; // Correct import
use trading::{TradeRequest, TradeResponse};
use dashmap::DashMap;
use std::sync::{Arc, Mutex};
use std::collections::HashMap;

pub mod trading {
    tonic::include_proto!("trading");
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
        let price = 10.0; // Simulated static price

        let mut cash = self.cash.lock().unwrap();

        match trade.as_str() {
            "buy" => {
                let cost = price * amount;
                if *cash >= cost {
                    *cash -= cost;
                    self.portfolio
                        .entry(symbol.clone())
                        .and_modify(|q| *q += amount)
                        .or_insert(amount);
                    println!("Bought {} shares of {}", amount, symbol);
                } else {
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
                    _ => return Err(Status::invalid_argument("Not enough holdings")),
                }
            }
            _ => return Err(Status::invalid_argument("Trade must be 'buy' or 'sell'")),
        }

        let port_map = self
            .portfolio
            .iter()
            .map(|entry| (entry.key().clone(), *entry.value()))
            .collect::<HashMap<_, _>>();

        Ok(Response::new(TradeResponse {
            message: "Trade executed".to_string(),
            cash_balance: *cash,
            portfolio: port_map,
        }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let engine = TradingEngine::default();
    println!("Server running on [::1]:50051");
    Server::builder()
        .add_service(TradeExecutorServer::new(engine))
        .serve("[::]:50051".parse()?)
        .await?;
    Ok(())
}
