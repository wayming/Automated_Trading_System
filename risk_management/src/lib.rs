use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

#[pyclass]
#[derive(Default)]
pub struct RiskManager {
    max_position_size: f64, // Max position size per stock
    stop_loss_threshold: f64, // Stop-loss threshold
}

#[pymethods]
impl RiskManager {
    #[new]
    fn new(max_position_size: f64, stop_loss_threshold: f64) -> Self {
        RiskManager {
            max_position_size,
            stop_loss_threshold,
        }
    }

    // Check position limit
    fn check_position_limit(&self, py: Python, portfolio: &PyDict, ticker: &str, amount: f64) -> bool {
        // Convert PyDict to HashMap
        let portfolio: HashMap<String, f64> = portfolio
            .into_iter()
            .map(|(key, value)| {
                // Extract key and value without needing `py` argument
                let key: String = key.extract().unwrap(); // Extract the key as a String
                let value: f64 = value.extract().unwrap(); // Extract the value as a f64
                (key, value)
            })
            .collect();

        let total_value: f64 = portfolio.values().sum();
        let stock_value = amount * self.max_position_size;
        if stock_value / total_value > self.max_position_size {
            println!("Position limit exceeded: buying exceeds max position size!");
            return false
        }
        true
    }

    // Check stop-loss logic
    fn check_stop_loss(&self, py: Python, portfolio: &PyDict, ticker: &str, current_price: f64) -> bool {
        // Convert PyDict to HashMap
        let portfolio: HashMap<String, f64> = portfolio
            .into_iter()
            .map(|(key, value)| {
                // Extract key and value without needing `py` argument
                let key: String = key.extract().unwrap(); // Extract the key as a String
                let value: f64 = value.extract().unwrap(); // Extract the value as a f64
                (key, value)
            })
            .collect();

        if let Some(position) = portfolio.get(ticker) {
            if current_price < self.stop_loss_threshold * position {
                println!("Stop-loss triggered for {}: current price is below stop-loss threshold!", ticker);
                return true;
            }
        }
        false
    }
}

#[pymodule]
fn risk_management(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<RiskManager>()?;
    Ok(())
}
