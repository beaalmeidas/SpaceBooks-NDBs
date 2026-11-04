"""Environment configuration; credentials never appear in repr()."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    mongo_uri: str = field(repr=False)
    mongo_database: str
    redis_url: str = field(repr=False)
    neo4j_uri: str = field(repr=False)
    neo4j_username: str
    neo4j_password: str = field(repr=False)
    neo4j_database: str = "neo4j"
    timeout_seconds: float = 10
    query_timeout_seconds: float = 60

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        def required(key):
            value = os.environ.get(key, "")
            if not value or value.startswith("CHANGE_ME_"):
                raise ValueError(f"Configure {key} in .env or the environment")
            return value

        mongo_uri = os.environ.get("MONGO_URI")
        if not mongo_uri:
            user = quote(os.environ.get("MONGO_USERNAME", "spacebooks"), safe="")
            password = quote(required("MONGO_PASSWORD"), safe="")
            mongo_uri = f"mongodb://{user}:{password}@localhost:{os.environ.get('MONGO_PORT', '27017')}/?authSource=admin"
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            password = quote(required("REDIS_PASSWORD"), safe="")
            redis_url = f"redis://:{password}@localhost:{os.environ.get('REDIS_PORT', '6379')}/0"
        timeout = float(os.environ.get("DB_TIMEOUT_SECONDS", "10"))
        if not 0 < timeout <= 120:
            raise ValueError("DB_TIMEOUT_SECONDS must be between 0 and 120")
        query_timeout = float(os.environ.get("DB_QUERY_TIMEOUT_SECONDS", "60"))
        if not 0 < query_timeout <= 120:
            raise ValueError("DB_QUERY_TIMEOUT_SECONDS must be between 0 and 120")
        return cls(
            mongo_uri=mongo_uri, mongo_database=os.environ.get("MONGO_DATABASE", "spacebooks"),
            redis_url=redis_url,
            neo4j_uri=os.environ.get("NEO4J_URI", f"bolt://localhost:{os.environ.get('NEO4J_BOLT_PORT', '7687')}"),
            neo4j_username=os.environ.get("NEO4J_USERNAME", "neo4j"),
            neo4j_password=required("NEO4J_PASSWORD"),
            neo4j_database=os.environ.get("NEO4J_DATABASE", "neo4j"), timeout_seconds=timeout,
            query_timeout_seconds=query_timeout,
        )
