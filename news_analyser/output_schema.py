
STOCK_IDENTIFICATION_OUTPUT_SCHEMA = {
    "type": "object",
    "title": "StockIdentification",
    "description": "Schema for identifying a stock symbol",
    "properties": {
        "stock_symbol": {"type": "string", "description": "股票代码"}
    },
    "required": ["stock_symbol"],
    "additionalProperties": False
}

STOCK_PREDICTION_OUTPUT_SCHEMA = {
    "type": "object",
    "title": "StockPrediction",
    "description": "Schema for stock prediction",
    "properties": {
        "stock_code": {"type": "string", "description": "股票代码"},
        "stock_name": {"type": "string", "description": "股票名称"},
        "analysis": {
            "type": "object",
            "properties": {
                "short_term": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "string", "description": "短期评分"},
                        "driver": {"type": "string", "description": "驱动因素"},
                        "risk": {"type": "string", "description": "风险"}
                    },
                    "required": ["score", "driver", "risk"]
                },
                "mid_term": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "string", "description": "中期评分"},
                        "driver": {"type": "string", "description": "驱动因素"},
                        "risk": {"type": "string", "description": "风险"}
                    },
                    "required": ["score", "driver", "risk"]
                },
                "long_term": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "string", "description": "长期评分"},
                        "driver": {"type": "string", "description": "驱动因素"},
                        "risk": {"type": "string", "description": "风险"}
                    },
                    "required": ["score", "driver", "risk"]
                }
            },
            "required": ["short_term", "mid_term", "long_term"]
        },
        "alerts": {
            "type": "array",
            "items": {"type": "string", "description": "风险预警"},
            "description": "风险预警列表"
        },
        "conclusion": {"type": "string", "description": "结论"}
    },
    "required": ["stock_code", "stock_name", "analysis", "alerts", "conclusion"],
    "additionalProperties": False
}