import asyncio
import json
import sys
import logging
from typing import Dict, Any, AsyncIterator
import psycopg2
from psycopg2.extras import RealDictCursor
from dataclasses import asdict

# MCP SDK 导入（服务器和客户端）
from mcp.server.fastmcp import FastMCP
from mcp.server.session import ServerSession
from mcp.types import Tool, ToolResult

# LangChain 导入（用于 Agent）
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from common.pg_common import PostgresConfig

# MCP 客户端（SDK）
from mcp.client import MCPClient

class PGReader:
    def __init__(self, config: PostgresConfig):
        self.config = config
        self.conn = None
        self.logger = SingletonLoggerSafe.component("PGReader")

    async def connect(self):
        self.conn = await asyncpg.connect(
            host=self.config["host"],
            port=self.config["port"],
            user=self.config["user"],
            password=self.config["password"],
            database=self.config["database"],
        )
        await self.logger.ainfo(
            f"Connected to Postgres at {self.config['host']}:{self.config['port']}/{self.config['database']}"
        )
    
    async def disconnect(self):
        if self.conn:
            await self.conn.close()
        await self.logger.ainfo("Disconnected from Postgres")

class StockMCPServer(FastMCP):
    """基于 MCP SDK 的股票 MCP 服务器"""
    
    def __init__(self, db_connection_string: str):
        super().__init__(name="stock-data-mcp-server", version="1.0.0")
        self.db = StockDatabase(db_connection_string)
        self.add_tool(self.get_stock_data_tool())
        self.add_tool(self.analyze_stock_tool())

    async def lifespan(self, session: ServerSession) -> AsyncIterator[None]:
        """生命周期：启动时连接数据库"""
        await self.db.connect()
        try:
            yield
        finally:
            await self.db.disconnect()

    def get_stock_data_tool(self) -> Tool:
        """定义 get_stock_data 工具"""
        @self.tool(
            name="get_stock_data",
            description="获取股票历史数据",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码"},
                    "days": {"type": "integer", "description": "获取天数", "default": 30}
                },
                "required": ["symbol"]
            }
        )
        def get_stock_data(params: Dict[str, Any]) -> ToolResult:
            symbol = params["symbol"].upper()
            days = params.get("days", 30)
            
            cursor = self.db.connection.cursor()
            cursor.execute("""
                SELECT date, close_price, volume
                FROM stock_prices
                WHERE symbol = %s
                AND date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date DESC
                LIMIT %s
            """, [symbol, days, days])
            
            rows = cursor.fetchall()
            cursor.close()
            
            if not rows:
                result = {"error": f"No data found for {symbol}"}
            else:
                data = [dict(row) for row in rows]
                for row in data:
                    row["date"] = str(row["date"])
                result = {
                    "symbol": symbol,
                    "period_days": days,
                    "data_points": len(data),
                    "data": data
                }
            
            return ToolResult(content=[{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}])

        return get_stock_data

    def analyze_stock_tool(self) -> Tool:
        """定义 analyze_stock 工具"""
        @self.tool(
            name="analyze_stock",
            description="分析股票表现",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码"},
                    "period": {"type": "integer", "description": "分析周期", "default": 30}
                },
                "required": ["symbol"]
            }
        )
        def analyze_stock(params: Dict[str, Any]) -> ToolResult:
            symbol = params["symbol"].upper()
            period = params.get("period", 30)
            
            cursor = self.db.connection.cursor()
            cursor.execute("""
                SELECT 
                    AVG(close_price) as avg_price,
                    MIN(close_price) as min_price,
                    MAX(close_price) as max_price,
                    COUNT(*) as trading_days
                FROM stock_prices
                WHERE symbol = %s
                AND date >= CURRENT_DATE - INTERVAL '%s days'
            """, [symbol, period])
            
            result = cursor.fetchone()
            cursor.close()
            
            if not result or not result["trading_days"]:
                res = {"error": f"No data for analysis: {symbol}"}
            else:
                res = {
                    "symbol": symbol,
                    "analysis_period": period,
                    "statistics": {
                        "avg_price": round(float(result["avg_price"]), 2),
                        "min_price": float(result["min_price"]),
                        "max_price": float(result["max_price"]),
                        "trading_days": result["trading_days"],
                        "price_range_pct": round(
                            (float(result["max_price"]) - float(result["min_price"])) 
                            / float(result["min_price"]) * 100, 2
                        )
                    }
                }
            
            return ToolResult(content=[{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}])

        return analyze_stock