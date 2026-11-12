import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from src.domain.contracts import ServiceUnavailableError, SessionExpiredError, ValidationError
from src.domain.models import Order, OrderItem
from src.services.checkout import MongoCheckoutService, order_from_document, validate_uuid


class CheckoutUnitTests(unittest.TestCase):
    def test_invalid_request_ids_fail_safely(self):
        for value in (None, "", "order-1", {"$ne": None}, uuid4()):
            with self.assertRaises(ValidationError):
                validate_uuid(value)
        validate_uuid(str(uuid4()))

    def test_order_snapshot_validates_total(self):
        order = Order(str(uuid4()), "client-a", (OrderItem("9780000000000", "Book", 2, 1234),),
                      datetime.now(timezone.utc))
        document = order.to_document()
        self.assertEqual(order_from_document(document).total_cents, 2468)
        document["total_cents"] = 1
        with self.assertRaises(ServiceUnavailableError):
            order_from_document(document)

    def test_expired_session_blocks_every_customer_operation_before_database_access(self):
        db, sessions = MagicMock(), MagicMock()
        sessions.resolve.side_effect = SessionExpiredError("expired")
        service = MongoCheckoutService(db, sessions, MagicMock(), MagicMock(), MagicMock(), MagicMock())
        for action in (lambda: service.prepare("token", str(uuid4()), str(uuid4())),
                       lambda: service.checkout("token", str(uuid4()), str(uuid4())),
                       lambda: service.get_order("token", str(uuid4()))):
            with self.assertRaises(SessionExpiredError):
                action()
        self.assertFalse(db.mock_calls)

    def test_recovery_limit_is_validated(self):
        service = MongoCheckoutService(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        for limit in (0, -1, True, 1001, "100"):
            with self.assertRaises(ValidationError):
                service.retry_pending(limit)
