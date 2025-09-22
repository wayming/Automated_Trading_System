import asyncpg
from typing import TypedDict
from news_model.message import ArticlePayload
from common.logger import SingletonLoggerSafe
from dataclasses import asdict

class PostgresConfig(TypedDict):
    host: str
    port: int
    user: str
    password: str
    database: str
    table_name: str

class PostgresWriter:
    def __init__(self, config: PostgresConfig):
        self.config = config
        self.table = config["table_name"]
        self.property_keys = {"article_id", "time", "title", "content", "analysis", "error"}

    async def __aenter__(self):
        try:
            self.conn = await asyncpg.connect(
                host=self.config["host"],
                port=self.config["port"],
                user=self.config["user"],
                password=self.config["password"],
                database=self.config["database"],
            )
            await SingletonLoggerSafe.ainfo(
                f"Connected to Postgres at {self.config['host']}:{self.config['port']}/{self.config['database']}"
            )
        except Exception as e:
            await SingletonLoggerSafe.aerror(f"Failed to connect to Postgres: {e}")
            raise e
        
        await self._ensure_table()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await self.conn.close()
            await SingletonLoggerSafe.ainfo("Disconnected from Postgres")
        except Exception as e:
            await SingletonLoggerSafe.aerror(f"Failed to disconnect from Postgres: {e}")

    async def _ensure_table(self):
        try:
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                article_id TEXT PRIMARY KEY,
                time TIMESTAMPTZ,
                title TEXT,
                content TEXT,
                analysis TEXT,
                error TEXT
            )
            """
            await self.conn.execute(create_table_sql)
            await SingletonLoggerSafe.ainfo(f"Table '{self.table}' exists or created successfully")
        except Exception as e:
            await SingletonLoggerSafe.aerror(f"Failed to create table '{self.table}': {e}")
            raise e

    async def store_article(self, article_text):
        try:
            article = ArticlePayload.from_json(article_text)
            filtered = {k: v for k, v in asdict(article).items() if k in self.property_keys}

            columns = ", ".join(filtered.keys())
            values = ", ".join(f"${i+1}" for i in range(len(filtered)))
            sql = f"INSERT INTO {self.table} ({columns}) VALUES ({values}) ON CONFLICT (article_id) DO UPDATE SET " + \
                  ", ".join(f"{k}=EXCLUDED.{k}" for k in filtered.keys() if k != "article_id")

            await self.conn.execute(sql, *filtered.values())
            await SingletonLoggerSafe.ainfo(f"Article stored successfully: {filtered}")
        except Exception as e:
            await SingletonLoggerSafe.aerror(f"Failed to store article: {e}")
