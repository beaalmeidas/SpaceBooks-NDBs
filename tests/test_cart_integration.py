import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from src.domain.contracts import CART_TTL_SECONDS, NotFoundError, SessionExpiredError, StockUnavailableError
from src.services.cart import RedisCartService
from src.services.catalog import MongoCatalogService
from src.services.sessions import RedisSessionService
from tests.test_catalog import example_book
from tests.test_catalog_cache_integration import CacheFixture
from tests.test_sessions import example_customer


class CartFixture(CacheFixture):
    def setUp(self):
        super().setUp()
        self.customers = self.collection.database[f"customers_{self.prefix.replace(':', '_')}"]
        self.addCleanup(self.customers.drop)
        self.customers.insert_many([example_customer().to_document(),
                                    example_customer("client-b", "Bruno").to_document()])
        self.sessions = RedisSessionService(self.customers, self.redis, namespace=f"{self.prefix}session")
        self.alice = self.sessions.create_demo_session("client-a").token
        self.bruno = self.sessions.create_demo_session("client-b").token
        self.mongo_catalog = MongoCatalogService(self.collection)
        self.carts = RedisCartService(self.redis, self.sessions, self.mongo_catalog, namespace=f"{self.prefix}cart")


@unittest.skipUnless(os.environ.get("SPACEBOOKS_INTEGRATION") == "1", "Requires MongoDB and Redis")
class CartIntegrationTests(CartFixture):
    def test_independent_customers_raw_storage_subtotals_and_current_prices(self):
        first, second = example_book(), example_book(1)
        self.carts.add_item(self.alice, first.isbn, 2)
        alice = self.carts.add_item(self.alice, second.isbn, 3)
        bruno = self.carts.add_item(self.bruno, first.isbn, 1)
        self.assertEqual(alice.total_cents, first.price_cents * 2 + second.price_cents * 3)
        self.assertEqual(bruno.total_cents, first.price_cents)
        self.assertEqual(self.redis.hgetall(self.carts._keys("client-a")[0]), {first.isbn: "2", second.isbn: "3"})
        self.collection.update_one({"_id": first.isbn}, {"$set": {"price_cents": 9999}})
        updated = self.carts.get_cart(self.alice)
        self.assertEqual(updated.total_cents, 9999 * 2 + second.price_cents * 3)
        self.assertEqual(updated.revision, alice.revision)
        self.assertEqual(self.carts.get_cart(self.bruno).total_cents, 9999)
        self.assertEqual(self.collection.find_one({"_id": first.isbn})["stock"], first.stock)

    def test_mutations_revisions_ttl_noops_and_last_removal(self):
        isbn = example_book().isbn
        empty = self.carts.get_cart(self.alice)
        self.assertEqual((empty.items, empty.total_cents, empty.revision), ((), 0, None))
        added = self.carts.add_item(self.alice, isbn)
        keys = self.carts._keys("client-a")
        for key in keys:
            self.assertTrue(CART_TTL_SECONDS - 5 <= self.redis.ttl(key) <= CART_TTL_SECONDS)
        self.assertLessEqual(abs(self.redis.pttl(keys[0]) - self.redis.pttl(keys[1])), 20)
        for key in keys:
            self.redis.expire(key, 300)
        self.carts.get_cart(self.alice)
        unchanged = self.carts.set_quantity(self.alice, isbn, 1)
        self.assertEqual(unchanged.revision, added.revision)
        self.assertLessEqual(self.redis.ttl(keys[0]), 300)
        changed = self.carts.set_quantity(self.alice, isbn, 3)
        self.assertNotEqual(changed.revision, added.revision)
        self.assertGreater(self.redis.ttl(keys[0]), 300)
        unchanged = self.carts.remove_item(self.alice, example_book(1).isbn)
        self.assertEqual(unchanged.revision, changed.revision)
        result = self.carts.remove_item(self.alice, isbn)
        self.assertEqual((result.items, result.revision, result.total_cents), ((), None, 0))
        self.assertEqual(self.redis.exists(*keys), 0)
        self.carts.remove_item(self.alice, isbn)

    def test_stock_and_deleted_book_can_be_removed_by_isbn(self):
        isbn = example_book().isbn
        self.carts.add_item(self.alice, isbn, 2)
        with self.assertRaises(StockUnavailableError):
            self.carts.add_item(self.alice, isbn, 6)
        self.collection.update_one({"_id": isbn}, {"$set": {"stock": 1}})
        self.assertEqual(self.carts.get_cart(self.alice).items[0].quantity, 2)
        with self.assertRaises(StockUnavailableError):
            self.carts.set_quantity(self.alice, isbn, 2)
        self.collection.delete_one({"_id": isbn})
        with self.assertRaises(NotFoundError):
            self.carts.get_cart(self.alice)
        self.assertEqual(self.carts.remove_item(self.alice, isbn).total_cents, 0)

    def test_expiration_creates_new_revision_and_logout_preserves_cart(self):
        isbn = example_book().isbn
        original = self.carts.add_item(self.alice, isbn, 2)
        self.sessions.logout(self.alice)
        with self.assertRaises(SessionExpiredError):
            self.carts.get_cart(self.alice)
        new_token = self.sessions.create_demo_session("client-a").token
        self.assertEqual(self.carts.get_cart(new_token).total_cents, original.total_cents)
        keys = self.carts._keys("client-a")
        with self.redis.pipeline() as pipe:
            for key in keys:
                pipe.pexpire(key, 80)
            pipe.execute()
        deadline = time.monotonic() + 3
        while self.redis.exists(*keys) and time.monotonic() < deadline:
            time.sleep(0.02)
        empty = self.carts.get_cart(new_token)
        self.assertEqual(empty.total_cents, 0)
        self.assertIsNone(empty.revision)
        recreated = self.carts.add_item(new_token, isbn)
        self.assertNotEqual(recreated.revision, original.revision)

    def test_simultaneous_additions_do_not_lose_increments(self):
        isbn = example_book().isbn
        self.collection.replace_one({"_id": isbn}, replace(example_book(), stock=100).to_document())
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.carts.add_item, self.alice, isbn) for _ in range(4)]
            for future in futures:
                future.result()
        self.assertEqual(self.carts.get_cart(self.alice).items[0].quantity, 4)
