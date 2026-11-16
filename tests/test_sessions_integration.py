import json
import os
import time
import unittest

from src.domain.contracts import SESSION_TTL_SECONDS, SessionExpiredError
from src.services.sessions import RedisSessionService
from tests.test_catalog_cache_integration import CacheFixture
from tests.test_sessions import example_customer


@unittest.skipUnless(os.environ.get("SPACEBOOKS_INTEGRATION") == "1", "Requires MongoDB and Redis")
class SessionIntegrationTests(CacheFixture):
    def setUp(self):
        super().setUp()
        self.customers = self.collection.database[f"customers_{self.prefix.replace(':', '_')}"]
        self.addCleanup(self.customers.drop)
        self.customers.insert_many([example_customer().to_document(),
                                    example_customer("client-b", "Bruno").to_document()])
        self.sessions = RedisSessionService(self.customers, self.redis, namespace=f"{self.prefix}session")

    def test_two_customers_ttl_and_independent_logout(self):
        first = self.sessions.create_demo_session("client-a")
        second = self.sessions.create_demo_session("client-b")
        key = self.sessions._key(first.token)
        self.assertTrue(SESSION_TTL_SECONDS - 5 <= self.redis.ttl(key) <= SESSION_TTL_SECONDS)
        before = self.redis.pttl(key)
        self.assertEqual(self.sessions.resolve(first.token).customer_id, "client-a")
        self.assertLessEqual(self.redis.pttl(key), before)
        self.assertNotIn(first.token, key + self.redis.get(key))
        self.assertEqual(json.loads(self.redis.get(key))["customer_id"], "client-a")
        self.sessions.logout(first.token)
        with self.assertRaises(SessionExpiredError):
            self.sessions.resolve(first.token)
        self.assertEqual(self.sessions.resolve(second.token).customer_id, "client-b")

    def test_redis_really_expires_and_missing_customer_revokes(self):
        first = self.sessions.create_demo_session("client-a")
        key = self.sessions._key(first.token)
        # Shorten only this temporary test key; production lifetime stays fixed at 8h.
        self.redis.pexpire(key, 80)
        deadline = time.monotonic() + 3
        while self.redis.exists(key) and time.monotonic() < deadline:
            time.sleep(0.02)
        with self.assertRaises(SessionExpiredError):
            self.sessions.resolve(first.token)
        second = self.sessions.create_demo_session("client-b")
        self.customers.delete_one({"_id": "client-b"})
        with self.assertRaises(SessionExpiredError):
            self.sessions.resolve(second.token)
        self.assertFalse(self.redis.exists(self.sessions._key(second.token)))

    def test_directory_literal_search_stable_order_and_limit(self):
        documents = [example_customer(f"client-{index:03d}", "Same name").to_document() for index in range(60)]
        self.customers.insert_many(documents)
        results = self.sessions.list_customers("Same name")
        self.assertEqual(len(results), 50)
        self.assertEqual([item.customer_id for item in results], sorted(item.customer_id for item in results))
        self.assertEqual(self.sessions.list_customers(".*"), ())
        self.assertEqual(self.sessions.list_customers("CLIENT-B")[0].name, "Bruno")
