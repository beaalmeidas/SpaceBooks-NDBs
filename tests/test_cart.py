import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from redis.exceptions import ConnectionError, WatchError

from src.domain.contracts import (
    ConflictError, NotFoundError, ServiceUnavailableError, SessionExpiredError,
    StockUnavailableError, ValidationError,
)
from src.services.cart import RedisCartService
from tests.test_catalog import example_book
from tests.test_sessions import example_customer


class CartUnitTests(unittest.TestCase):
    def setUp(self):
        self.redis = MagicMock()
        self.sessions = MagicMock()
        self.sessions.resolve.return_value = example_customer()
        self.catalog = MagicMock()
        self.catalog.get_book.return_value = example_book()
        self.service = RedisCartService(self.redis, self.sessions, self.catalog)
        self.pipe = self.redis.pipeline.return_value.__enter__.return_value

    def stored(self, items, revision=None):
        self.pipe.hgetall.side_effect = lambda key: items if key == "cart:client-a" else {"revision": revision or str(uuid4())}

    def test_session_is_resolved_before_every_operation(self):
        self.sessions.resolve.side_effect = SessionExpiredError("expired")
        for action in (
            lambda: self.service.get_cart("token"),
            lambda: self.service.add_item("token", example_book().isbn),
            lambda: self.service.set_quantity("token", example_book().isbn, 1),
            lambda: self.service.remove_item("token", example_book().isbn),
        ):
            with self.assertRaises(SessionExpiredError):
                action()
        self.redis.pipeline.assert_not_called()
        self.catalog.get_book.assert_not_called()
        self.assertEqual(self.sessions.resolve.call_count, 4)

    def test_invalid_quantities_and_ids_do_not_touch_redis(self):
        for quantity in (0, -1, True, 1.5, "2", None, 2_147_483_648):
            for action in (self.service.add_item, self.service.set_quantity):
                with self.assertRaises(ValidationError):
                    action("token", example_book().isbn, quantity)
        for isbn in (None, "", "123", {"$ne": None}):
            with self.assertRaises(ValidationError):
                self.service.remove_item("token", isbn)
        self.redis.pipeline.assert_not_called()

    def test_missing_book_cannot_be_added(self):
        self.catalog.get_book.side_effect = NotFoundError("absent")
        with self.assertRaises(NotFoundError):
            self.service.add_item("token", example_book().isbn)
        self.redis.pipeline.assert_not_called()

    def test_stock_validates_resulting_quantity_before_writing(self):
        self.stored({example_book().isbn: "6"})
        with self.assertRaises(StockUnavailableError):
            self.service.add_item("token", example_book().isbn, 2)
        self.pipe.multi.assert_not_called()

    def test_setting_absent_item_fails(self):
        self.stored({})
        with self.assertRaises(NotFoundError):
            self.service.set_quantity("token", example_book().isbn, 1)
        self.pipe.multi.assert_not_called()

    def test_read_uses_current_prices_and_never_refreshes_ttl(self):
        self.pipe.hgetall.return_value = self.pipe
        revision = str(uuid4())
        self.pipe.execute.return_value = [{example_book().isbn: "3"}, {"revision": revision}]
        cart = self.service.get_cart("token")
        self.assertEqual(cart.total_cents, 3702)
        self.assertEqual(cart.items[0].subtotal_cents, 3702)
        self.assertEqual(cart.customer_id, "client-a")
        self.assertEqual(cart.revision, revision)
        self.pipe.expire.assert_not_called()
        self.catalog.get_book.assert_called_once_with(example_book().isbn)

    def test_corrupt_quantities_and_missing_revision_fail_safely(self):
        for items, metadata in (
            ({example_book().isbn: "0"}, {}), ({example_book().isbn: "-1"}, {}),
            ({example_book().isbn: "1.5"}, {}), ({example_book().isbn: "01"}, {}),
            ({example_book().isbn: "1"}, {}), ({"bad-isbn": "1"}, {"revision": str(uuid4())}),
        ):
            with self.assertRaises(ServiceUnavailableError):
                self.service._decode(items, metadata)

    def test_redis_failure_does_not_leak_credentials(self):
        self.pipe.hgetall.side_effect = ConnectionError("private-url-password")
        for action in (lambda: self.service.get_cart("token"),
                       lambda: self.service.add_item("token", example_book().isbn)):
            with self.assertRaises(ServiceUnavailableError) as error:
                action()
            self.assertNotIn("private", str(error.exception))

    def test_concurrent_changes_have_bounded_retries(self):
        self.pipe.watch.side_effect = WatchError()
        with self.assertRaises(ConflictError):
            self.service.add_item("token", example_book().isbn)
        self.assertEqual(self.pipe.watch.call_count, 5)

    def test_lost_transaction_reply_is_not_replayed_as_a_watch_conflict(self):
        self.stored({})

        def lost_reply():
            try:
                raise ConnectionError("private connection details")
            except ConnectionError:
                raise WatchError("ConnectionError while watching")

        self.pipe.execute.side_effect = lost_reply
        with self.assertRaises(ServiceUnavailableError) as error:
            self.service.add_item("token", example_book().isbn)
        self.assertNotIn("private", str(error.exception))
        self.pipe.execute.assert_called_once()
