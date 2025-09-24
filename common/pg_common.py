from typing import TypedDict

class PostgresConfig(TypedDict):
    host: str
    port: int
    user: str
    password: str
    database: str
    table_name: str