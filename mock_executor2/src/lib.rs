use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

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
            println!("买入 {} 数量 {} @ ${}", ticker, quantity, price); // Now ticker is still available
        } else {
            println!("资金不足，无法买入！");
        }
        Ok(())
    }
    
    // 模拟卖出操作 - Change to &mut self
    fn sell(&mut self, ticker: String, price: f64, quantity: f64) -> PyResult<()> {
        let mut portfolio = self.portfolio.lock().unwrap();
        if let Some(qty) = portfolio.get_mut(&ticker) {
            if *qty >= quantity {
                *qty -= quantity;
                self.cash += price * quantity; // Now allowed because we have &mut self
                println!("卖出 {} 数量 {} @ ${}", ticker, quantity, price);
            } else {
                println!("持仓不足，无法卖出！");
            }
        } else {
            println!("股票 {} 不在持仓中！", ticker);
        }
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
}

#[pymodule]
fn mock_executor(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<MockExecutor>()?;
    Ok(())
}
