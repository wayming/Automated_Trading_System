import asyncpg
from typing import TypedDict
from news_model.message import ArticlePayload
from common.logger import SingletonLoggerSafe
from dataclasses import asdict, fields
from datetime import datetime

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
        self.table_defn = {
            "article_id": {
                "type": "text",
                "primary_key": True
            },
            "time": {
                "type": "timestamp",
            },
            "title": {
                "type": "text",
            },
            "content": {
                "type": "text",
            },
            "analysis": {
                "type": "text",
            },
            "error": {
                "type": "text",
            }
        }
        self.field_names = self.table_defn.keys()
        self.logger = SingletonLoggerSafe.component("PostgresWriter")

    async def __aenter__(self):
        try:
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
        except Exception as e:
            await self.logger.aerror(f"Failed to connect to Postgres: {e}")
            raise e
        
        await self._ensure_table()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await self.conn.close()
            await self.logger.ainfo("Disconnected from Postgres")
        except Exception as e:
            await self.logger.aerror(f"Failed to disconnect from Postgres: {e}")

    async def _ensure_table(self):
        try:
            cols = []
            for field_name, field_defn in self.table_defn.items():
                col = f"{field_name} {field_defn['type']}"
                if field_defn.get("primary_key"):
                    col += " PRIMARY KEY"
                cols.append(col)
            fields_sql = ",".join(cols)
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                {fields_sql}                    
            )
            """
            await self.logger.ainfo(f"Executing SQL: {create_table_sql}")
            await self.conn.execute(create_table_sql)
            await self.logger.ainfo(f"Table '{self.table}' exists or created successfully")
        except Exception as e:
            await self.logger.aerror(f"Failed to create table '{self.table}': {e}")
            raise e

    async def store_article(self, article_text):
        try:
            article = ArticlePayload.from_json(article_text)
            filtered = {k: v for k, v in asdict(article).items() if k in self.field_names}
            for k, v in filtered.items():
                if v is None:
                    continue
                if self.table_defn[k]['type'] == "text":
                    filtered[k] = v.strip()
                elif self.table_defn[k]['type'] == "timestamp":
                    filtered[k] = datetime.fromisoformat(v)
            columns = list(filtered.keys())
            values = list(filtered.values())

            # parameter placeholders: $1, $2, $3 ...
            placeholders = ", ".join(f"${i+1}" for i in range(len(values)))
            set_clause = ", ".join(f"{col}=EXCLUDED.{col}" for col in columns if col != "article_id")

            sql = f"""
                INSERT INTO {self.table} ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (article_id) DO UPDATE SET {set_clause}
            """
            await self.logger.ainfo(f"Executing SQL: {sql}")
            await self.conn.execute(sql, *filtered.values())
            await self.logger.ainfo(f"Article stored successfully: {filtered}")
        except Exception as e:
            await self.logger.aerror(f"Failed to store article: {e}")
