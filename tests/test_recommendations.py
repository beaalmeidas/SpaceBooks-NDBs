import unittest
from unittest.mock import MagicMock

from neo4j.exceptions import ServiceUnavailable
from pymongo.errors import ConnectionFailure

from src.domain.contracts import NotFoundError, ServiceUnavailableError, SessionExpiredError, ValidationError
from src.services.recommendations import Neo4jRecommendationService
from tests.test_catalog import example_book
from tests.test_sessions import example_customer


class RecommendationUnitTests(unittest.TestCase):
    def setUp(self):
        self.db, self.sessions, self.graph = MagicMock(), MagicMock(), MagicMock()
        self.sessions.resolve.return_value = example_customer()
        self.graph.id_prefix = ""
        self.service = Neo4jRecommendationService(self.db, self.sessions, self.graph)
        self.service.catalog = MagicMock()
        self.service.catalog.get_book.return_value = example_book()

    def test_expired_session_blocks_all_operations_before_access(self):
        self.sessions.resolve.side_effect = SessionExpiredError("expired")
        for action in (lambda: self.service.recommend("token"),
                       lambda: self.service.get_review("token", example_book().isbn),
                       lambda: self.service.submit_review("token", example_book().isbn, 5)):
            with self.assertRaises(SessionExpiredError):
                action()
        self.assertFalse(self.db.mock_calls)
        self.assertFalse(self.graph.mock_calls)
        self.assertFalse(self.service.catalog.mock_calls)

    def test_invalid_ratings_and_limits_never_touch_graph(self):
        for rating in (0, 6, -1, 4.5, True, "5", None):
            with self.assertRaises(ValidationError):
                self.service.submit_review("token", example_book().isbn, rating)
        for limit in (0, 51, True, "10", 1.5):
            with self.assertRaises(ValidationError):
                self.service.recommend("token", limit)
        self.assertFalse(self.graph.mock_calls)
        self.assertFalse(self.db.mock_calls)

    def test_missing_book_cannot_be_rated(self):
        self.service.catalog.get_book.side_effect = NotFoundError("absent")
        with self.assertRaises(NotFoundError):
            self.service.submit_review("token", example_book().isbn, 5)
        self.assertFalse(self.graph.mock_calls)

    def test_graph_failure_is_safe_and_does_not_store_rating_elsewhere(self):
        self.graph.driver.execute_query.side_effect = ServiceUnavailable("private connection details")
        with self.assertRaises(ServiceUnavailableError) as error:
            self.service.submit_review("token", example_book().isbn, 5)
        self.assertNotIn("private", str(error.exception))
        self.assertFalse(self.db.mock_calls)

    def test_mongodb_purchase_history_failure_blocks_recommendations(self):
        self.db.orders.distinct.side_effect = ConnectionFailure("private details")
        with self.assertRaises(ServiceUnavailableError):
            self.service.recommend("token")
        self.assertFalse(self.graph.mock_calls)
