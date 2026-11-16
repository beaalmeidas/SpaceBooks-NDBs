"""Bounded connections with credential-free application errors."""

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import re
from time import monotonic, sleep
from uuid import uuid4

from neo4j import GraphDatabase, Query
from pymongo import MongoClient
from redis import Redis

from .config import Settings


class DatabaseError(RuntimeError):
    pass


@contextmanager
def operation(service: str, action: str):
    try:
        yield
    except DatabaseError:
        raise
    except Exception as error:
        # Driver messages can contain credentials, URIs and document contents.
        code = getattr(error, "code", "")
        detail = f", {code}" if isinstance(code, str) and re.fullmatch(r"Neo\.[A-Za-z.]+", code) else ""
        raise DatabaseError(f"{service}: {action} failed ({type(error).__name__}{detail}). Check configuration and service health.") from None


@dataclass
class Connections:
    mongo: object
    redis: object
    neo4j: object
    settings: Settings

    @property
    def db(self):
        return self.mongo[self.settings.mongo_database]

    def query(self, cypher: str, **parameters):
        with operation("Neo4j", "query"):
            records, _, _ = self.neo4j.execute_query(
                Query(cypher, timeout=self.settings.query_timeout_seconds),
                parameters_=parameters, database_=self.settings.neo4j_database,
            )
            return records

    def health(self, check_expiry: bool = True) -> dict:
        with operation("MongoDB", "ping"):
            self.mongo.admin.command("ping")
        self.query("RETURN 1 AS ok")
        with operation("Redis", "temporary TTL probe"):
            self.redis.ping()
            key = f"diagnostic:{uuid4().hex}"
            try:
                if not self.redis.set(key, "ok", ex=2, nx=True):
                    raise DatabaseError("Redis: unable to create diagnostic key")
                if self.redis.get(key) != "ok" or not 0 <= self.redis.ttl(key) <= 2:
                    raise DatabaseError("Redis: read/write/TTL check failed")
                if check_expiry:
                    deadline = monotonic() + 4
                    while self.redis.exists(key) and monotonic() < deadline:
                        sleep(0.1)
                    if self.redis.exists(key):
                        raise DatabaseError("Redis: diagnostic key did not expire")
            finally:
                self.redis.delete(key)
        return {"mongodb": "ok", "redis": "ok", "neo4j": "ok", "redis_expiration_checked": check_expiry}


@contextmanager
def connect(settings: Settings):
    with ExitStack() as stack:
        with operation("MongoDB", "connection"):
            mongo = MongoClient(
                settings.mongo_uri, serverSelectionTimeoutMS=int(settings.timeout_seconds * 1000),
                connectTimeoutMS=int(settings.timeout_seconds * 1000),
                socketTimeoutMS=int(settings.timeout_seconds * 1000),
            )
            stack.callback(mongo.close)
        with operation("Redis", "connection"):
            redis = Redis.from_url(settings.redis_url, decode_responses=True,
                                   socket_timeout=settings.timeout_seconds, socket_connect_timeout=settings.timeout_seconds)
            stack.callback(redis.close)
        with operation("Neo4j", "connection"):
            neo4j = GraphDatabase.driver(settings.neo4j_uri,
                                        auth=(settings.neo4j_username, settings.neo4j_password),
                                        connection_timeout=settings.timeout_seconds,
                                        connection_acquisition_timeout=settings.timeout_seconds,
                                        max_transaction_retry_time=settings.query_timeout_seconds)
            stack.callback(neo4j.close)
        yield Connections(mongo, redis, neo4j, settings)
