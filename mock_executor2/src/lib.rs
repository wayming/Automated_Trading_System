use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use tracing::{info, error};
use tracing_subscriber::fmt::writer::BoxMakeWriter;
use tracing_subscriber::fmt::time::ChronoLocal;
use std::fs::OpenOptions;
use std::path::Path;

fn init_logging() {
    let log_path = Path::new("output/mock_executor.log");
    let file = OpenOptions::new()
        .append(true)
        .create(true)
        .open(log_path)
        .expect("Failed to open log file");

    let file_writer: BoxMakeWriter = Box::new(file);
    tracing_subscriber::fmt()
        .with_writer(file_writer)
        .with_timer(ChronoLocal::rfc3339())
        .with_ansi(false) // No color for file logs
        .init();
}

#[pyclass]
#[derive(Default)]
pub struct MockExecutor {
    portfolio: Arc<Mutex<HashMap<String, f64>>>,  // 股票持仓
    cash: f64, // 初始现金
}

#[pymethods]
impl MockExecutor {
    #[new]
    fn new(initial_cash: f64) -> Self {
        MockExecutor {
            portfolio: Arc::new(Mutex::new(HashMap::new())),
            cash: initial_cash,
        }
    }

    // 模拟买入操作 - Change to &mut self
    fn buy(&mut self, ticker: String, price: f64, quantity: f64) -> PyResult<()> {
        let mut portfolio = self.portfolio.lock().unwrap();
        let cost = price * quantity;
        if self.cash >= cost {
            self.cash -= cost;
            *portfolio.entry(ticker.clone()).or_insert(0.0) += quantity;  // Clone ticker here
            info!("买入 {} 数量 {} @ ${}", ticker, quantity, price); // Now ticker is still available
        } else {
            error!("资金不足，无法买入！");
        }

        self.show_portfolio();
        Ok(())
    }
    
    // 模拟卖出操作 - Change to &mut self
    fn sell(&mut self, ticker: String, price: f64, quantity: f64) -> PyResult<()> {
        let mut portfolio = self.portfolio.lock().unwrap();
        if let Some(qty) = portfolio.get_mut(&ticker) {
            if *qty >= quantity {
                *qty -= quantity;
                self.cash += price * quantity; // Now allowed because we have &mut self
                info!("卖出 {} 数量 {} @ ${}", ticker, quantity, price);
            } else {
                error!("持仓不足，无法卖出！");
            }
        } else {
            error!("股票 {} 不在持仓中！", ticker);
        }

        self.show_portfolio();
        Ok(())
    }

    // 获取当前现金余额
    fn get_cash(&self) -> f64 {
        self.cash
    }

    // 获取持仓情况
    fn get_portfolio(&self) -> HashMap<String, f64> {
        self.portfolio.lock().unwrap().clone()
    }

    // Dump portfolio
    fn show_portfolio(&self) {
        let port_map = self.get_portfolio();
        info!("Cash balance: {:.2}", *cash);
        info!("Portfolio:");
        for (sym, qty) in &port_map {
            info!("  {}: {:.2}", sym, qty);
        }
    }
}

#[pymodule]
fn mock_executor(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<MockExecutor>()?;
    Ok(())
}
