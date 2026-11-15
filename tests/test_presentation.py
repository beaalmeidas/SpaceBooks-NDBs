"""Real isolated persistence checks for presentation signals on existing customers."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from src.domain.contracts import ServiceError, ValidationError
from src.seed_presentation import DATASET, load_presentation
from tests.test_catalog import example_book
from tests.test_recommendations_integration import RecommendationFixture
from tests.test_sessions import example_customer


@unittest.skipUnless(os.environ.get("SPACEBOOKS_INTEGRATION") == "1", "Requires MongoDB, Redis and Neo4j")
class PresentationTests(RecommendationFixture):
    def setUp(self):
        super().setUp()
        self.db.customers.insert_one(example_customer("client-c", "Carla").to_document())
        self.recommendations._query("UNWIND $ids AS id MERGE (:Cliente {id:id})", write=True,
                                    ids=[self.prefix + c for c in ("client-a", "client-b", "client-c")])
        self.recommendations._query("UNWIND $ids AS id MERGE (:Produto {id:id})", write=True,
                                    ids=[self.prefix + example_book(i).isbn for i in range(4)])
        self.data = {"dataset": DATASET, "customers": [{"id": "client-a"}, {"id": "client-b"},
                     {"id": "client-c", "without_history": True}],
                     "purchases": [{"customer": "client-a", "book": example_book(0).isbn},
                                   {"customer": "client-b", "book": example_book(0).isbn},
                                   {"customer": "client-b", "book": example_book(1).isbn}],
                     "reviews": [{"customer": "client-b", "book": example_book(2).isbn, "rating": 5},
                                 {"customer": "client-a", "book": example_book(3).isbn, "rating": 5}]}
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "presentation.json"

    def load(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        return load_presentation(self.recommendations, self.path)

    def signal_count(self):
        return self.recommendations._query("""
            MATCH (c:Cliente)-[r]->() WHERE c.id STARTS WITH $prefix AND r.demo_dataset=$dataset
            RETURN count(r) AS amount
        """, prefix=self.prefix, dataset=DATASET)[0]["amount"]

    def test_repeat_preserves_real_reviews_customers_commerce_orders_and_recommends(self):
        self.recommendations.submit_review(self.alice, example_book(3).isbn, 2)
        review = self.recommendations.get_review(self.alice, example_book(3).isbn)
        customers = list(self.db.customers.find({}).sort("_id", 1))
        books = list(self.db.books.find({}).sort("_id", 1))
        first = self.load()
        self.assertEqual((first["purchases_created"], first["reviews_created"], first["reviews_preserved"]), (3, 1, 1))
        second = self.load()
        self.assertEqual((second["purchases_created"], second["reviews_created"]), (0, 0))
        self.assertEqual(self.signal_count(), 4)
        self.assertEqual(self.recommendations.get_review(self.alice, example_book(3).isbn), review)
        self.assertEqual(list(self.db.customers.find({}).sort("_id", 1)), customers)
        self.assertEqual(list(self.db.books.find({}).sort("_id", 1)), books)
        self.assertEqual(self.db.orders.count_documents({}), 0)
        suggestions = self.recommendations.recommend(self.alice, limit=2)
        self.assertEqual({s.book.isbn for s in suggestions}, {example_book(1).isbn, example_book(2).isbn})
        self.assertTrue(all(s.reason == "similar_customers" for s in suggestions))
        token = self.sessions.create_demo_session("client-c").token
        self.addCleanup(self.sessions.logout, token)
        suggestions = self.recommendations.recommend(token)
        self.assertTrue(suggestions)
        self.assertTrue(all(s.reason == "preferences" for s in suggestions))

    def test_cold_customer_with_history_aborts_transaction_and_removes_locks(self):
        self.buy("client-c", 0)
        with self.assertRaises(ValidationError):
            self.load()
        self.assertEqual(self.signal_count(), 0)
        rows = self.recommendations._query("""
            MATCH (c:Cliente) WHERE c.id STARTS WITH $prefix AND c._presentation_lock IS NOT NULL
            RETURN count(c) AS amount
        """, prefix=self.prefix)
        self.assertEqual(rows[0]["amount"], 0)

    def test_invalid_rating_or_missing_customer_never_writes(self):
        self.data["reviews"][0]["rating"] = 6
        with self.assertRaises(ValidationError):
            self.load()
        self.data["reviews"][0]["rating"] = 5
        self.data["customers"].append({"id": "not-registered"})
        with self.assertRaises(ValidationError):
            self.load()
        self.assertEqual(self.signal_count(), 0)
        self.assertEqual(self.db.customers.count_documents({}), 3)

    def test_missing_graph_product_aborts_without_partial_signals(self):
        self.recommendations._query("MATCH (p:Produto {id:$id}) DETACH DELETE p", write=True,
                                    id=self.prefix + example_book(2).isbn)
        with self.assertRaises(ServiceError):
            self.load()
        self.assertEqual(self.signal_count(), 0)


if __name__ == "__main__":
    unittest.main()
