import asyncpg
from typing import List, Dict, Any
from common.pg_common import PostgresConfig
from common.logger import SingletonLoggerSafe

class PGReader:
    def __init__(self, config: PostgresConfig):
        self.config = config
        self.logger = SingletonLoggerSafe.component("PGReader")
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=self.config["host"],
            port=self.config["port"],
            user=self.config["user"],
            password=self.config["password"],
            database=self.config["database"],
        )
        await self.logger.ainfo(
            f"Created Postgres connection pool at "
            f"{self.config['host']}:{self.config['port']}/{self.config['database']}"
        )

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
        await self.logger.ainfo("Postgres connection pool closed")

    async def get_article_historical_analysis(self, article_id: str) -> List[Dict[str, Any]]:
        """
        Search article historical analysis by article_id
        """
        try:
            if not self.pool:
                raise RuntimeError("PGReader not connected. Call connect() first.")

            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                """
                SELECT article_id, time, title, content, analysis, error
                FROM articles
                WHERE article_id = $1
                """,
                article_id,
            )

            if not rows:
                await self.logger.ainfo(f"No data found for {article_id}")
                return []
            else:
                return [dict(row) for row in rows]

        except Exception as e:
            await self.logger.aerror(f"Failed to get article historical analysis: {e}")
            raise e
