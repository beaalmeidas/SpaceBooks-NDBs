import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

from pymongo import MongoClient
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import ConnectionError
from redis.retry import Retry

from src.database.config import Settings
from src.domain.contracts import ConflictError, NotFoundError, ServiceUnavailableError, StockUnavailableError
from src.services.cart import RedisCartService
from src.services.catalog import MongoCatalogService
from src.services.catalog_cache import CatalogInvalidator, RedisCatalogCache
from src.services.checkout import MongoCheckoutService
from src.services.purchases_graph import PurchaseGraph
from src.services.sessions import RedisSessionService
from tests.test_catalog import example_book
from tests.test_sessions import example_customer


class CheckoutFixture(unittest.TestCase):
    def setUp(self):
        settings = Settings.from_env()
        self.prefix = f"checkout_test:{uuid4().hex}:"
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10000, socketTimeoutMS=10000)
        self.addCleanup(client.close)
        self.db = client[f"checkout_test_{uuid4().hex}"]
        self.addCleanup(client.drop_database, self.db.name)
        self.db.books.insert_many([example_book(index).to_document() for index in range(3)])
        self.db.customers.insert_many([example_customer().to_document(), example_customer("client-b", "Bruno").to_document()])
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2,
                                    retry=Retry(NoBackoff(), 0))
        self.addCleanup(self.redis.close)
        self.addCleanup(self.cleanup_keys)
        self.sessions = RedisSessionService(self.db.customers, self.redis, namespace=f"{self.prefix}session")
        self.alice = self.sessions.create_demo_session("client-a").token
        self.bruno = self.sessions.create_demo_session("client-b").token
        self.catalog = MongoCatalogService(self.db.books)
        self.carts = RedisCartService(self.redis, self.sessions, self.catalog, namespace=f"{self.prefix}cart")
        self.cache = RedisCatalogCache(self.redis, namespace=f"{self.prefix}catalog:v1",
                                       product_namespace=f"{self.prefix}product:v1")
        self.invalidator = CatalogInvalidator(self.db.catalog_cache_state, self.cache)
        self.graph = PurchaseGraph.from_settings(settings)
        self.graph.id_prefix = self.prefix
        self.addCleanup(self.graph.close)
        self.addCleanup(self.cleanup_graph)
        self.service = MongoCheckoutService(self.db, self.sessions, self.carts, self.redis, self.graph, self.invalidator)
        self.service.ensure_schema()

    def cleanup_keys(self):
        keys = list(self.redis.scan_iter(match=f"{self.prefix}*"))
        if keys:
            self.redis.delete(*keys)

    def cleanup_graph(self):
        self.graph.driver.execute_query("MATCH (n) WHERE n.id STARTS WITH $prefix DETACH DELETE n",
                                        prefix=self.prefix, database_=self.graph.database)

    def review(self, token=None, quantity=2):
        token = token or self.alice
        cart = self.carts.add_item(token, example_book().isbn, quantity)
        request_id = str(uuid4())
        self.service.prepare(token, request_id, cart.revision)
        return request_id, cart.revision

    def purchases(self, request_id):
        records, _, _ = self.graph.driver.execute_query(
            "MATCH (c:Cliente {id: $customer})-[r:COMPROU {pedido_id: $order_id}]->() RETURN r.quantidade AS quantity",
            customer=self.prefix + "client-a", order_id=request_id, database_=self.graph.database)
        return [row["quantity"] for row in records]


@unittest.skipUnless(os.environ.get("SPACEBOOKS_INTEGRATION") == "1", "Requires replica set, Redis and Neo4j")
class CheckoutIntegrationTests(CheckoutFixture):
    def test_single_order_stock_historical_prices_cache_cart_and_ownership(self):
        request_id, revision = self.review()
        generation = self.cache.generation()
        result = self.service.checkout(self.alice, request_id, revision)
        self.assertEqual((result.graph_status, result.cart_status, result.cache_status), ("done",) * 3)
        self.assertEqual(result.order.total_cents, 2468)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 5)
        self.assertEqual(self.db.orders.count_documents({}), 1)
        self.assertEqual(self.carts.get_cart(self.alice).items, ())
        self.assertNotEqual(self.cache.generation(), generation)
        self.assertEqual(self.purchases(request_id), [2])
        self.db.books.update_one({"_id": example_book().isbn}, {"$set": {"price_cents": 9999}})
        repeated = self.service.checkout(self.alice, request_id, revision)
        self.assertEqual(repeated.order.total_cents, 2468)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 5)
        with self.assertRaises(NotFoundError):
            self.service.get_order(self.bruno, request_id)
        with self.assertRaises(NotFoundError):
            self.service.checkout(self.bruno, request_id, revision)

    def test_transaction_rolls_back_all_stock_when_later_item_fails(self):
        self.carts.add_item(self.alice, example_book().isbn, 2)
        cart = self.carts.add_item(self.alice, example_book(1).isbn, 2)
        request_id = str(uuid4())
        self.service.prepare(self.alice, request_id, cart.revision)
        self.db.books.update_one({"_id": example_book(1).isbn}, {"$set": {"stock": 1}})
        with self.assertRaises(StockUnavailableError):
            self.service.checkout(self.alice, request_id, cart.revision)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 7)
        self.assertEqual(self.db.orders.count_documents({}), 0)
        self.assertEqual(len(self.carts.get_cart(self.alice).items), 2)

    def test_price_change_requires_explicit_new_review(self):
        request_id, revision = self.review()
        self.db.books.update_one({"_id": example_book().isbn}, {"$set": {"price_cents": 1500}})
        with self.assertRaises(ConflictError):
            self.service.checkout(self.alice, request_id, revision)
        old = self.service.prepare(self.alice, request_id, revision)
        self.assertEqual(old.total_cents, 2468)
        new_request = str(uuid4())
        new = self.service.prepare(self.alice, new_request, revision)
        self.assertEqual(new.total_cents, 3000)
        result = self.service.checkout(self.alice, new_request, revision)
        self.assertEqual(result.order.total_cents, 3000)

    def test_cart_revision_change_prevents_checkout(self):
        request_id, revision = self.review()
        self.carts.add_item(self.alice, example_book(1).isbn)
        with self.assertRaises(ConflictError):
            self.service.checkout(self.alice, request_id, revision)
        self.assertEqual(self.db.orders.count_documents({}), 0)

    def test_durable_recovery_after_all_three_post_commit_failures(self):
        request_id, revision = self.review()
        with patch.object(self.graph, "record", side_effect=ServiceUnavailableError("offline")), \
                patch.object(self.redis, "eval", side_effect=ConnectionError("offline")), \
                patch.object(self.invalidator, "flush", return_value=False):
            result = self.service.checkout(self.alice, request_id, revision)
        self.assertEqual((result.graph_status, result.cart_status, result.cache_status), ("pending",) * 3)
        self.assertEqual(self.db.orders.count_documents({}), 1)
        self.assertTrue(self.db.catalog_cache_state.find_one({"_id": "catalog"})["pending"])
        # A new worker has only MongoDB markers, not the browser's local state.
        worker = MongoCheckoutService(self.db, self.sessions, self.carts, self.redis, self.graph, self.invalidator)
        self.assertEqual(worker.retry_pending(), 1)
        self.assertEqual(worker.retry_pending(), 0)
        self.assertEqual(self.purchases(request_id), [2])
        self.assertFalse(self.carts.get_cart(self.alice).items)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 5)

    def test_lost_graph_reply_does_not_duplicate_relationship(self):
        request_id, revision = self.review()
        record = self.graph.record

        def lost_reply(order):
            record(order)
            raise ServiceUnavailableError("Lost reply after graph commit")

        with patch.object(self.graph, "record", side_effect=lost_reply):
            result = self.service.checkout(self.alice, request_id, revision)
        self.assertEqual(result.graph_status, "pending")
        self.assertEqual(self.service.retry_pending(), 1)
        self.assertEqual(self.purchases(request_id), [2])

    def test_new_cart_revision_is_preserved_after_purchase(self):
        request_id, revision = self.review()
        record = self.graph.record

        def concurrent_edit(order):
            record(order)
            self.carts.add_item(self.alice, example_book(1).isbn)

        with patch.object(self.graph, "record", side_effect=concurrent_edit):
            result = self.service.checkout(self.alice, request_id, revision)
        self.assertEqual(result.cart_cleanup, "preserved")
        self.assertEqual(result.cart_status, "done")
        self.assertEqual(len(self.carts.get_cart(self.alice).items), 2)

    def test_concurrent_submissions_of_same_attempt_create_one_order(self):
        request_id, revision = self.review()
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda _: self.service.checkout(self.alice, request_id, revision), range(3)))
        self.assertEqual({result.order.order_id for result in results}, {request_id})
        self.assertEqual(self.db.orders.count_documents({}), 1)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 5)
        self.assertEqual(self.purchases(request_id), [2])

    def test_two_customers_cannot_buy_same_last_unit(self):
        self.db.books.update_one({"_id": example_book().isbn}, {"$set": {"stock": 1}})
        first_id, first_revision = self.review(self.alice, quantity=1)
        second_id, second_revision = self.review(self.bruno, quantity=1)
        def buy(args):
            try:
                return self.service.checkout(*args)
            except StockUnavailableError:
                return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(buy, [(self.alice, first_id, first_revision), (self.bruno, second_id, second_revision)]))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(self.db.orders.count_documents({}), 1)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 0)

    def test_another_attempt_cannot_purchase_the_same_cart_revision(self):
        request_id, revision = self.review()
        second_id = str(uuid4())
        self.service.prepare(self.alice, second_id, revision)
        with patch.object(self.redis, "eval", side_effect=ConnectionError("offline")):
            result = self.service.checkout(self.alice, request_id, revision)
        self.assertEqual(result.cart_status, "pending")
        with self.assertRaises(ConflictError):
            self.service.checkout(self.alice, second_id, revision)
        self.assertEqual(self.db.orders.count_documents({}), 1)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 5)
