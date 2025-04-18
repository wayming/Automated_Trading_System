use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use std::fs::File;
use std::io::Write;
use tokio_postgres::{NoTls, Client};

#[pyfunction]
fn get_sma(tickers: Vec<String>, period: usize) -> PyResult<()> {
    // 创建文件用于写入SMA信号
    let mut file = File::create("signals.csv").unwrap();
    writeln!(file, "ticker,sma").unwrap();

    // 模拟一些硬编码的收盘价数据
    let fake_data = vec![
        100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0, 116.0, 118.0,
    ];

    for ticker in tickers {
        let close_prices = fake_data.clone();

        // 如果数据不够长，跳过
        if close_prices.len() < period {
            writeln!(file, "{},N/A", ticker).unwrap();
            continue;
        }

        let sma = close_prices
            .windows(period)
            .map(|window| window.iter().sum::<f64>() / period as f64)
            .collect::<Vec<_>>();

        writeln!(file, "{},{}", ticker, sma.last().unwrap()).unwrap();
    }

    Ok(())
}

#[pyfunction]
fn generate_signals() -> PyResult<()> {
    // 模拟 20 支推荐股票（现实中可从数据库筛选 + SMA动量打分）
    let tickers = vec!["AAPL", "MSFT", "NVDA", "GOOG", "AMZN"];

    let mut file = File::create("signals.csv").unwrap();
    writeln!(file, "ticker").unwrap();
    for t in tickers {
        writeln!(file, "{}", t).unwrap();
    }

    println!("✅ Rust: signals.csv written.");
    Ok(())
}

#[pymodule]
fn indicators(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_signals, m)?)?;
    m.add_function(wrap_pyfunction!(get_sma, m)?)?;
    Ok(())
}
