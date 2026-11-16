"""Redis primitives and durable invalidation shared by readers and writers."""

import json
import logging
import re
from uuid import uuid4

from pymongo.errors import PyMongoError
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from src.database.config import RedisCacheSettings
from src.domain.contracts import CATALOG_CACHE_TTL_SECONDS


logger = logging.getLogger(__name__)


class RedisCatalogCache:
    def __init__(self, redis, *, ttl_seconds=CATALOG_CACHE_TTL_SECONDS,
                 namespace="catalog:v1", product_namespace="product:v1", owns_client=False):
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3600:
            raise ValueError("Cache TTL must be an integer from 1 to 3600 seconds")
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.namespace = namespace
        self.product_namespace = product_namespace
        self.generation_key = f"{namespace}:generation"
        self._owns_client = owns_client

    @classmethod
    def from_env(cls):
        try:
            settings = RedisCacheSettings.from_env()
            if not settings.redis_url:
                return None
            client = Redis.from_url(
                settings.redis_url, decode_responses=True,
                socket_timeout=settings.timeout_seconds, socket_connect_timeout=settings.timeout_seconds,
                retry=Retry(NoBackoff(), 0),
            )
            return cls(client, ttl_seconds=settings.ttl_seconds, owns_client=True)
        except (ValueError, TypeError, OSError, RedisError):
            logger.warning("Cache Redis sem configuração válida; usando MongoDB diretamente.")
            return None

    def close(self):
        if self._owns_client:
            self.redis.close()

    def generation(self):
        try:
            generation = self.redis.get(self.generation_key)
            if generation is None:
                self.redis.set(self.generation_key, uuid4().hex, nx=True)
                generation = self.redis.get(self.generation_key)
            if isinstance(generation, str) and re.fullmatch(r"[a-f0-9]{32}", generation):
                return generation
        except (RedisError, UnicodeError):
            pass
        return None

    def rotate(self):
        try:
            # A fresh UUID on every retry prevents old generations becoming live again.
            return bool(self.redis.set(self.generation_key, uuid4().hex))
        except RedisError:
            return False

    def get_json(self, key):
        try:
            raw = self.redis.get(key)
            return json.loads(raw) if raw is not None else None
        except (RedisError, ValueError, TypeError, UnicodeError):
            return None

    def put_json(self, key, value):
        try:
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            self.redis.set(key, encoded, ex=self.ttl_seconds)
        except (RedisError, ValueError, TypeError, UnicodeError):
            # Caching must never turn a successful MongoDB read into a failure.
            pass


class CatalogInvalidator:
    """Persist intent before mutations; retry safely after Redis/network failures."""

    def __init__(self, state_collection, cache):
        self.state = state_collection
        self.cache = cache

    def mark(self):
        self.state.update_one({"_id": "catalog"}, {"$set": {"revision": uuid4().hex, "pending": True}}, upsert=True)

    def flush(self):
        if self.cache is None:
            return False
        try:
            marker = self.state.find_one({"_id": "catalog", "pending": True})
            if marker is None:
                return True
            if not isinstance(marker.get("revision"), str) or not marker["revision"]:
                return False
            if not self.cache.rotate():
                return False
            result = self.state.update_one(
                {"_id": "catalog", "revision": marker["revision"], "pending": True},
                {"$set": {"pending": False}},
            )
            return result.matched_count == 1
        except PyMongoError:
            return False

    def invalidate(self):
        self.mark()
        return self.flush()
