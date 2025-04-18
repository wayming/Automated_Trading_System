
#!/bin/bash

# Step 1: 编译 Rust 模块
cd indicators
maturin develop  # 安装 Rust 扩展
cd -

# Step 2: 运行 Python 回测
cd strategy_engine
python backtest.py
