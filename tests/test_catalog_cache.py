import unittest
from dataclasses import replace
from unittest.mock import MagicMock

from redis.exceptions import ConnectionError

from src.domain.contracts import CatalogPage, CatalogQuery
from src.services.cached_catalog import CachedCatalogService, search_digest
from src.services.catalog_cache import RedisCatalogCache
from tests.test_catalog import example_book


class MemoryRedis:
    """Controllable clock for unit tests; real expiry is also integration-tested."""
    def __init__(self):
        self.now = 0
        self.values = {}

    def get(self, key):
        entry = self.values.get(key)
        if entry is None:
            return None
        value, expires = entry
        if expires is not None and expires <= self.now:
            del self.values[key]
            return None
        return value

    def set(self, key, value, nx=False, ex=None):
        if nx and self.get(key) is not None:
            return False
        self.values[key] = (value, None if ex is None else self.now + ex)
        return True


class CatalogCacheUnitTests(unittest.TestCase):
    def test_load_invalidates_even_after_partial_failure(self):
        from unittest.mock import patch
        from src.database.clients import DatabaseError
        from src.database.seed import load
        connections = MagicMock()
        with patch("src.database.seed.create_schema"), patch("src.database.seed.CatalogInvalidator") as invalidator, \
                patch("src.database.seed._load_data", side_effect=DatabaseError("partial write")):
            with self.assertRaises(DatabaseError):
                load(connections, MagicMock())
            self.assertEqual(invalidator.return_value.mark.call_count, 2)
            invalidator.return_value.flush.assert_called_once()

    def test_load_renews_intent_after_readers_retry_during_writes(self):
        from unittest.mock import patch
        from src.database.seed import load
        connections = MagicMock()
        with patch("src.database.seed.create_schema"), patch("src.database.seed.CatalogInvalidator") as invalidator, \
                patch("src.database.seed._load_data") as write:
            write.side_effect = lambda *args: invalidator.return_value.flush()
            load(connections, MagicMock())
            self.assertEqual(invalidator.return_value.mark.call_count, 2)
            self.assertEqual(invalidator.return_value.flush.call_count, 2)

    def setUp(self):
        self.redis = MemoryRedis()
        self.cache = RedisCatalogCache(self.redis)
        self.backend = MagicMock()
        self.backend.search.return_value = CatalogPage((example_book(),), 1, 1, 24)
        self.backend.get_book.return_value = example_book()
        self.backend.list_categories.return_value = ("Science",)
        self.state = MagicMock()
        self.state.find_one.return_value = None
        self.service = CachedCatalogService(self.backend, self.cache, self.state)

    def test_hit_miss_expiry_and_no_sliding_ttl(self):
        first = self.service.search(CatalogQuery())
        self.redis.now = 59
        self.assertEqual(self.service.search(CatalogQuery()), first)
        self.backend.search.assert_called_once()
        self.redis.now = 61
        self.service.search(CatalogQuery())
        self.assertEqual(self.backend.search.call_count, 2)

    def test_all_query_dimensions_change_key_but_normalized_search_does_not(self):
        query = CatalogQuery(search="Jane")
        self.assertEqual(search_digest(query), search_digest(replace(query, search=" JANE ")))
        variants = (replace(query, search="John"), replace(query, category="Fiction"), replace(query, page=2),
                    replace(query, page_size=5), replace(query, sort="price_desc"))
        self.assertEqual(len({search_digest(query), *(search_digest(item) for item in variants)}), 6)

    def test_details_and_categories_are_cached(self):
        for _ in range(2):
            self.assertEqual(self.service.get_book(example_book().isbn), example_book())
            self.assertEqual(self.service.list_categories(), ("Science",))
        self.backend.get_book.assert_called_once()
        self.backend.list_categories.assert_called_once()

    def test_explicit_invalidation_drops_all_resource_types(self):
        self.service.search(CatalogQuery())
        self.service.get_book(example_book().isbn)
        self.service.list_categories()
        self.state.find_one.return_value = {"revision": "revision-1", "pending": True}
        self.state.update_one.return_value.matched_count = 1
        self.service.invalidate_cache()
        self.state.find_one.return_value = None
        self.service.search(CatalogQuery())
        self.service.get_book(example_book().isbn)
        self.service.list_categories()
        self.assertEqual(self.backend.search.call_count, 2)
        self.assertEqual(self.backend.get_book.call_count, 2)
        self.assertEqual(self.backend.list_categories.call_count, 2)

    def test_redis_failure_and_disabled_cache_use_mongodb(self):
        broken = MagicMock()
        broken.get.side_effect = ConnectionError("redis://:secret@unavailable")
        self.service.cache = RedisCatalogCache(broken)
        self.assertEqual(self.service.search(CatalogQuery()).items[0], example_book())
        self.service.cache = None
        self.service.search(CatalogQuery())
        self.assertEqual(self.backend.search.call_count, 2)

    def test_corrupt_cached_json_is_a_miss(self):
        generation = self.cache.generation()
        key = f"catalog:v1:{generation}:search:{search_digest(CatalogQuery())}"
        self.redis.set(key, '{"items": "invalid"}')
        self.assertEqual(self.service.search(CatalogQuery()).total, 1)
        self.backend.search.assert_called_once()

    def test_corrupt_cached_book_metadata_is_a_miss(self):
        self.service.get_book(example_book().isbn)
        document = example_book().to_document()
        document["thumbnail"] = {"unexpected": "object"}
        key = f"product:v1:{self.cache.generation()}:{example_book().isbn}"
        self.cache.put_json(key, document)
        self.assertEqual(self.service.get_book(example_book().isbn), example_book())
        self.assertEqual(self.backend.get_book.call_count, 2)

    def test_invalidation_during_read_cannot_republish_old_generation(self):
        old_generation = self.cache.generation()
        self.backend.search.side_effect = lambda query: (self.cache.rotate(), CatalogPage((example_book(),), 1, 1, 24))[1]
        self.service.search(CatalogQuery())
        self.assertNotEqual(self.cache.generation(), old_generation)
        self.backend.search.side_effect = None
        self.service.search(CatalogQuery())
        self.assertEqual(self.backend.search.call_count, 2)

    def test_failed_cache_write_does_not_fail_a_successful_read(self):
        self.redis.set = MagicMock(side_effect=ConnectionError("unavailable"))
        # Keep generation readable, so only storing the loaded result fails.
        self.redis.values["catalog:v1:generation"] = ("a" * 32, None)
        self.assertEqual(self.service.search(CatalogQuery()).total, 1)
