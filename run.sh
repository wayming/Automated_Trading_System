
#!/bin/bash

# Step 1: 编译 Rust 模块
cargo build
cd indicators && maturin develop && cd -  # 安装 Rust 扩展
cd mock_executor && maturin develop && cd - # 安装 Rust 扩展
cd risk_management && maturin develop && cd - # 安装 Rust 扩展

# Step 2: 运行 Python 回测
cd strategy_engine
python backtest.py
