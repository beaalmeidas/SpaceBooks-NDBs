import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from neo4j.exceptions import ServiceUnavailable

from src.domain.contracts import ServiceUnavailableError
from src.domain.models import Order, OrderItem
from src.seed_recommendation_demo import load_demo
from src.services.recommendations import Neo4jRecommendationService, HISTORY, SIMILAR
from tests.test_catalog import example_book
from tests.test_checkout_integration import CheckoutFixture
from tests.test_sessions import example_customer


class RecommendationFixture(CheckoutFixture):
    def setUp(self):
        super().setUp()
        self.db.books.insert_many([example_book(index).to_document() for index in range(3, 9)])
        self.db.books.update_one({"_id": example_book(6).isbn}, {"$set": {"stock": 0}})
        self.recommendations = Neo4jRecommendationService(self.db, self.sessions, self.graph)

    def buy(self, customer, index):
        book = example_book(index)
        self.graph.record(Order(str(uuid4()), customer, (OrderItem(book.isbn, book.title, 1, book.price_cents),),
                                datetime.now(timezone.utc)))

    def rows(self, customer, index):
        records, _, _ = self.graph.driver.execute_query("""
            MATCH (:Cliente {id: $customer})-[r:AVALIOU]->(:Produto {id: $book})
            RETURN r.nota AS rating, r.created_at AS created_at
        """, customer=self.prefix + customer, book=self.prefix + example_book(index).isbn,
            database_=self.graph.database)
        return records


@unittest.skipUnless(os.environ.get("SPACEBOOKS_INTEGRATION") == "1", "Requires MongoDB, Redis and Neo4j")
class RecommendationIntegrationTests(RecommendationFixture):
    def test_cold_customer_gets_available_preferences_and_live_prices(self):
        result = self.recommendations.recommend(self.alice)
        self.assertEqual([item.book.isbn for item in result], [example_book(0).isbn, example_book(3).isbn])
        self.assertTrue(all(item.reason == "preferences" and item.score == 1 for item in result))
        self.db.books.update_one({"_id": example_book(0).isbn}, {"$set": {"price_cents": 9999}})
        self.assertEqual(self.recommendations.recommend(self.alice)[0].book.price_cents, 9999)
        self.db.books.update_one({"_id": example_book(0).isbn}, {"$set": {"stock": 0}})
        self.assertEqual([item.book.isbn for item in self.recommendations.recommend(self.alice)], [example_book(3).isbn])

    def test_collaborative_purchases_positive_ratings_distinct_peers_and_exclusions(self):
        self.db.customers.insert_one(example_customer("client-c", "Carla").to_document())
        carla = self.sessions.create_demo_session("client-c").token
        self.buy("client-a", 0)
        self.buy("client-b", 0)
        self.buy("client-b", 1)
        self.buy("client-b", 1)  # Another order must not count the same peer twice.
        self.recommendations.submit_review(self.bruno, example_book(1).isbn, 5)
        self.recommendations.submit_review(self.bruno, example_book(2).isbn, 2)
        self.recommendations.submit_review(carla, example_book(0).isbn, 4)
        for index in (1, 4, 5, 7):
            self.buy("client-c", index)
        self.db.books.update_one({"_id": example_book(4).isbn}, {"$set": {"stock": 0}})
        self.db.books.delete_one({"_id": example_book(7).isbn})
        self.recommendations.submit_review(self.alice, example_book(5).isbn, 1)
        result = self.recommendations.recommend(self.alice)
        self.assertEqual([(item.book.isbn, item.reason, item.score) for item in result], [
            (example_book(1).isbn, "similar_customers", 2.0),
            (example_book(3).isbn, "preferences", 1.0),
        ])

    def test_rating_only_history_and_changed_rating_change_similarity(self):
        self.recommendations.submit_review(self.alice, example_book(1).isbn, 5)
        self.recommendations.submit_review(self.bruno, example_book(1).isbn, 4)
        self.recommendations.submit_review(self.bruno, example_book(2).isbn, 5)
        result = self.recommendations.recommend(self.alice, limit=1)
        self.assertEqual((result[0].book.isbn, result[0].reason), (example_book(2).isbn, "similar_customers"))
        self.recommendations.submit_review(self.bruno, example_book(1).isbn, 2)
        result = self.recommendations.recommend(self.alice, limit=1)
        self.assertEqual(result[0].reason, "preferences")
        self.assertEqual(len(self.rows("client-b", 1)), 1)

    def test_review_is_updated_with_date_without_changing_imported_average(self):
        isbn = example_book(0).isbn
        before = self.db.books.find_one({"_id": isbn})
        self.assertIsNone(self.recommendations.get_review(self.alice, isbn))
        first = self.recommendations.submit_review(self.alice, isbn, 5)
        second = self.recommendations.submit_review(self.alice, isbn, 2)
        self.assertGreaterEqual(second.created_at, first.created_at)
        persisted = self.recommendations.get_review(self.alice, isbn)
        self.assertEqual(persisted.rating, 2)
        self.assertEqual(persisted.created_at, second.created_at)
        self.assertEqual(len(self.rows("client-a", 0)), 1)
        self.assertIsNone(self.recommendations.get_review(self.bruno, isbn))
        self.assertEqual(self.db.books.find_one({"_id": isbn}), before)

    def test_concurrent_reviews_keep_one_relationship(self):
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda rating: self.recommendations.submit_review(self.alice, example_book().isbn, rating), (3, 4, 5)))
        self.assertEqual(len(results), 3)
        self.assertEqual(len(self.rows("client-a", 0)), 1)
        self.assertIn(self.rows("client-a", 0)[0]["rating"], (3, 4, 5))

    def test_pending_graph_purchase_is_excluded_using_mongodb_order(self):
        # A real confirmed order exists, but its COMPROU projection has not arrived.
        order = Order(str(uuid4()), "client-a", (OrderItem(example_book().isbn, "Purchased", 1, 1234),), datetime.now(timezone.utc))
        self.db.orders.insert_one(order.to_document())
        self.assertEqual([item.book.isbn for item in self.recommendations.recommend(self.alice)], [example_book(3).isbn])

    def test_graph_history_failure_is_closed_and_similarity_failure_uses_known_history(self):
        self.buy("client-a", 0)
        original = self.recommendations._query

        def failure(cypher, **params):
            if cypher == SIMILAR:
                raise ServiceUnavailable("private details")
            return original(cypher, **params)

        with patch.object(self.recommendations, "_query", side_effect=failure):
            result = self.recommendations.recommend(self.alice)
        self.assertEqual([item.book.isbn for item in result], [example_book(3).isbn])
        self.assertEqual(result[0].reason, "preferences")
        with patch.object(self.recommendations, "_query", side_effect=ServiceUnavailable("private details")):
            with self.assertRaises(ServiceUnavailableError) as error:
                self.recommendations.recommend(self.alice)
        self.assertNotIn("private", str(error.exception))

    def test_author_preferences_ties_limits_and_empty_result(self):
        self.db.customers.update_one({"_id": "client-a"}, {"$set": {"favorite_categories": [], "favorite_authors": ["Jane Doe"]}})
        result = self.recommendations.recommend(self.alice, limit=2)
        self.assertEqual([item.book.isbn for item in result], [example_book(0).isbn, example_book(2).isbn])
        self.db.customers.update_one({"_id": "client-a"}, {"$set": {"favorite_authors": []}})
        self.assertEqual(self.recommendations.recommend(self.alice), ())

    def test_identified_demo_data_is_repeatable_without_stock_changes_or_orders(self):
        fixture = {
            "dataset": "recommendations-v1", "customers": [
                {"id": "DEMO_REC_ONE", "name": "DEMO One", "categories": ["Science"], "authors": ["Jane Doe"]},
                {"id": "DEMO_REC_PEER", "name": "DEMO Peer", "categories": ["Science"], "authors": []},
            ], "purchases": [{"customer": "DEMO_REC_ONE", "book": example_book(0).isbn},
                              {"customer": "DEMO_REC_PEER", "book": example_book(0).isbn}],
            "reviews": [{"customer": "DEMO_REC_PEER", "book": example_book(1).isbn, "rating": 5}],
        }
        before = list(self.db.books.find({}).sort("_id", 1))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            self.assertEqual(load_demo(self.recommendations, path), load_demo(self.recommendations, path))
        self.assertEqual(self.db.customers.count_documents({"demo_dataset": "recommendations-v1"}), 2)
        self.assertEqual(len(self.rows("DEMO_REC_PEER", 1)), 1)
        self.assertEqual(self.db.orders.count_documents({}), 0)
        self.assertEqual(list(self.db.books.find({}).sort("_id", 1)), before)
        token = self.sessions.create_demo_session("DEMO_REC_ONE").token
        result = self.recommendations.recommend(token, 1)
        self.assertEqual((result[0].book.isbn, result[0].reason), (example_book(1).isbn, "similar_customers"))
