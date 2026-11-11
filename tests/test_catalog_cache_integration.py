import os
import time
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from src.database.config import RedisCacheSettings
from src.domain.contracts import CatalogQuery
from src.services.cached_catalog import CachedCatalogService, search_digest
from src.services.catalog_cache import CatalogInvalidator, RedisCatalogCache
from tests.test_catalog import example_book
from tests.test_catalog_integration import MongoCatalogFixture


class CacheFixture(MongoCatalogFixture):
    def setUp(self):
        super().setUp()
        settings = RedisCacheSettings.from_env()
        if settings.redis_url is None:
            self.fail("Configure Redis for integration tests")
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1,
                                    socket_connect_timeout=1, retry=Retry(NoBackoff(), 0))
        self.addCleanup(self.redis.close)
        self.redis.ping()
        self.prefix = f"test:{uuid4().hex}:"
        self.addCleanup(self.cleanup_cache)
        self.state = self.collection.database[f"cache_state_test_{uuid4().hex}"]
        self.addCleanup(self.state.drop)
        self.cache = RedisCatalogCache(self.redis, namespace=f"{self.prefix}catalog:v1",
                                       product_namespace=f"{self.prefix}product:v1")
        self.spy = MagicMock(wraps=self.service)
        self.cached = CachedCatalogService(self.spy, self.cache, self.state)

    def cleanup_cache(self):
        keys = list(self.redis.scan_iter(match=f"{self.prefix}*"))
        if keys:
            self.redis.delete(*keys)


@unittest.skipUnless(os.environ.get("SPACEBOOKS_INTEGRATION") == "1", "Requires MongoDB and Redis")
class CatalogCacheIntegrationTests(CacheFixture):
    def test_real_hits_all_resources_and_default_ttl(self):
        query = CatalogQuery()
        for _ in range(2):
            self.cached.search(query)
            self.cached.get_book(example_book().isbn)
            self.cached.list_categories()
        self.spy.search.assert_called_once()
        self.spy.get_book.assert_called_once()
        self.spy.list_categories.assert_called_once()
        generation = self.cache.generation()
        key = f"{self.cache.namespace}:{generation}:search:{search_digest(query)}"
        self.assertTrue(0 < self.redis.ttl(key) <= 60)

    def test_real_expiration_reloads_mongodb(self):
        self.cache.ttl_seconds = 1
        query = CatalogQuery()
        self.cached.search(query)
        self.cached.search(query)
        self.spy.search.assert_called_once()
        key = f"{self.cache.namespace}:{self.cache.generation()}:search:{search_digest(query)}"
        self.collection.update_one({"_id": example_book().isbn}, {"$set": {"price_cents": 4321}})
        deadline = time.monotonic() + 4
        while self.redis.exists(key) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(self.redis.exists(key), "Redis key should expire")
        self.assertEqual(self.cached.search(query).items[0].price_cents, 4321)
        self.assertEqual(self.spy.search.call_count, 2)

    def test_real_invalidation_updates_queries_details_and_categories(self):
        query = CatalogQuery(search="Alpha")
        self.assertEqual(self.cached.search(query).total, 2)
        self.cached.get_book(example_book().isbn)
        self.cached.list_categories()
        self.collection.update_one({"_id": example_book().isbn}, {"$set": {
            "title": "Changed book", "price_cents": 4321, "stock": 2, "categories": ["New Category"],
        }})
        self.cached.invalidate_cache()
        self.assertEqual(self.cached.search(query).total, 1)
        book = self.cached.get_book(example_book().isbn)
        self.assertEqual((book.price_cents, book.stock), (4321, 2))
        self.assertIn("New Category", self.cached.list_categories())
        self.assertFalse(self.state.find_one({"_id": "catalog"})["pending"])

    def test_redis_outage_falls_back_and_recovers_pending_invalidation(self):
        query = CatalogQuery()
        self.cached.search(query)
        old_generation = self.cache.generation()
        broken = Redis(host="127.0.0.1", port=1, socket_timeout=0.05, socket_connect_timeout=0.05,
                       decode_responses=True, retry=Retry(NoBackoff(), 0))
        self.addCleanup(broken.close)
        self.cache.redis = broken
        self.collection.update_one({"_id": example_book().isbn}, {"$set": {"stock": 1}})
        self.cached.invalidate_cache()
        self.assertTrue(self.state.find_one({"_id": "catalog"})["pending"])
        self.assertEqual(self.cached.search(query).items[0].stock, 1)
        self.cache.redis = self.redis
        self.assertEqual(self.cached.search(query).items[0].stock, 1)
        self.assertNotEqual(self.cache.generation(), old_generation)
        self.assertFalse(self.state.find_one({"_id": "catalog"})["pending"])

    def test_concurrent_invalidation_intent_is_not_cleared(self):
        invalidator = CatalogInvalidator(self.state, self.cache)
        invalidator.mark()
        rotate = self.cache.rotate
        def concurrent_rotate():
            invalidator.mark()
            return rotate()
        with patch.object(self.cache, "rotate", side_effect=concurrent_rotate):
            self.assertFalse(invalidator.flush())
        self.assertTrue(self.state.find_one({"_id": "catalog"})["pending"])
        self.assertTrue(invalidator.flush())

    def test_disabled_cache_always_reads_mongodb(self):
        uncached = CachedCatalogService(self.spy, None, self.state)
        uncached.search(CatalogQuery())
        uncached.search(CatalogQuery())
        self.assertEqual(self.spy.search.call_count, 2)
