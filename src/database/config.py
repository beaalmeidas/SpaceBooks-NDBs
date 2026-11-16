"""Environment configuration; credentials never appear in repr()."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv


@dataclass(frozen=True)
class RedisCacheSettings:
    redis_url: str | None = field(repr=False)
    ttl_seconds: int = 60
    timeout_seconds: float = 0.25

    @classmethod
    def from_env(cls) -> "RedisCacheSettings":
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        url = os.environ.get("REDIS_URL")
        password = os.environ.get("REDIS_PASSWORD", "")
        if not url and password and not password.startswith("CHANGE_ME_"):
            url = f"redis://:{quote(password, safe='')}@localhost:{os.environ.get('REDIS_PORT', '6379')}/0"
        ttl = int(os.environ.get("CATALOG_CACHE_TTL_SECONDS", "60"))
        timeout = float(os.environ.get("REDIS_CACHE_TIMEOUT_SECONDS", "0.25"))
        if not 1 <= ttl <= 3600 or not 0 < timeout <= 5:
            raise ValueError("Invalid catalog cache TTL or timeout")
        return cls(url, ttl, timeout)


@dataclass(frozen=True)
class RedisSessionSettings:
    redis_url: str = field(repr=False)
    timeout_seconds: float = 1

    @classmethod
    def from_env(cls) -> "RedisSessionSettings":
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        url = os.environ.get("REDIS_URL")
        if not url:
            password = os.environ.get("REDIS_PASSWORD", "")
            if not password or password.startswith("CHANGE_ME_"):
                raise ValueError("Configure Redis for sessions")
            url = f"redis://:{quote(password, safe='')}@localhost:{os.environ.get('REDIS_PORT', '6379')}/0"
        timeout = float(os.environ.get("REDIS_SESSION_TIMEOUT_SECONDS", "1"))
        if not 0 < timeout <= 5:
            raise ValueError("Invalid Redis session timeout")
        return cls(url, timeout)


@dataclass(frozen=True)
class MongoSettings:
    """Mongo-only settings, so the catalog does not require Redis or Neo4j."""

    mongo_uri: str = field(repr=False)
    mongo_database: str
    timeout_seconds: float = 10
    query_timeout_seconds: float = 60

    @classmethod
    def from_env(cls) -> "MongoSettings":
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        uri = os.environ.get("MONGO_URI")
        if not uri:
            password = os.environ.get("MONGO_PASSWORD", "")
            if not password or password.startswith("CHANGE_ME_"):
                raise ValueError("Configure MONGO_PASSWORD")
            user = quote(os.environ.get("MONGO_USERNAME", "spacebooks"), safe="")
            uri = f"mongodb://{user}:{quote(password, safe='')}@localhost:{os.environ.get('MONGO_PORT', '27017')}/?authSource=admin&directConnection=true"
        timeout = float(os.environ.get("DB_TIMEOUT_SECONDS", "10"))
        query_timeout = float(os.environ.get("DB_QUERY_TIMEOUT_SECONDS", "60"))
        if not 0 < timeout <= 120 or not 0 < query_timeout <= 120:
            raise ValueError("Database timeouts must be between 0 and 120 seconds")
        database = os.environ.get("MONGO_DATABASE", "spacebooks")
        if not database.strip():
            raise ValueError("MONGO_DATABASE must not be empty")
        return cls(uri, database, timeout, query_timeout)


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

        mongo = MongoSettings.from_env()
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            password = quote(required("REDIS_PASSWORD"), safe="")
            redis_url = f"redis://:{password}@localhost:{os.environ.get('REDIS_PORT', '6379')}/0"
        return cls(
            mongo_uri=mongo.mongo_uri, mongo_database=mongo.mongo_database,
            redis_url=redis_url,
            neo4j_uri=os.environ.get("NEO4J_URI", f"bolt://127.0.0.1:{os.environ.get('NEO4J_BOLT_PORT', '7687')}"),
            neo4j_username=os.environ.get("NEO4J_USERNAME", "neo4j"),
            neo4j_password=required("NEO4J_PASSWORD"),
            neo4j_database=os.environ.get("NEO4J_DATABASE", "neo4j"), timeout_seconds=mongo.timeout_seconds,
            query_timeout_seconds=mongo.query_timeout_seconds,
        )
