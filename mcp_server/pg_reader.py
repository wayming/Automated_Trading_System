import json
from typing import Dict, Any
from mcp.types import Tool, CallToolResult
from common.pg_common import PostgresConfig
from common.logger import SingletonLoggerSafe
from common.pg_common import asyncpg

class PGReader:
    def __init__(self, config: PostgresConfig):
        self.config = config
        self.logger = SingletonLoggerSafe.component("PGReader")
        self.pool = None
    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=self.config["host"],
            port=self.config["port"],
            user=self.config["user"],
            password=self.config["password"],
            database=self.config["database"],
        )
        await self.logger.ainfo(
            f"Created Postgres connection pool at {self.config['host']}:{self.config['port']}/{self.config['database']}"
        )
    
    async def disconnect(self):
        if self.pool:
            await self.pool.close()
        await self.logger.ainfo("Postgres connection pool closed")

    def get_article_historical_analysis_tool(self) -> Tool:
        """define get_article_historical_analysis tool"""
        @self.tool(
            name="get_article_historical_analysis",
            description="get article historical analysis",
            parameters={
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "article id"}
                },
                "required": ["article_id"]
            }
        )

        async def get_article_historical_analysis(params: Dict[str, Any]) -> ToolResult:
            article_id = params["article_id"]
            
            with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                SELECT article_id, time, title, content, analysis, error
                FROM articles
                WHERE article_id = %s
            """, [article_id])
            
            if not rows:
                result = {"error": f"No data found for {article_id}"}
            elif len(rows) > 1:
                result = {"error": f"Multiple data found for {article_id}"}
            else:
                result = rows[0]
            
            return ToolResult(content=[{"type": "json", "data": json.dumps(result, ensure_ascii=False, indent=2)}])

        return get_article_historical_analysis
