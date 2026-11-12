import hashlib
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pymongo.errors import ConnectionFailure
from redis.exceptions import ConnectionError

from src.domain.contracts import (
    SESSION_TTL_SECONDS, NotFoundError, ServiceUnavailableError, SessionExpiredError, ValidationError,
)
from src.domain.models import Customer
from src.database.config import RedisSessionSettings
from src.services.sessions import RedisSessionService


def example_customer(customer_id="client-a", name="Alice"):
    return Customer(customer_id, name, f"{customer_id}@example.com", ("Science",), (), date(2025, 1, 1))


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.customers = {item.customer_id: item.to_document() for item in (
            example_customer(), example_customer("client-b", "Bruno"),
        )}
        self.collection = MagicMock()
        self.collection.find_one.side_effect = lambda query, *a, **kw: self.customers.get(query["_id"])
        self.data = {}
        self.redis = MagicMock()
        self.redis.set.side_effect = self.set_value
        self.redis.get.side_effect = self.data.get
        self.redis.delete.side_effect = lambda key: self.data.pop(key, None) is not None
        self.service = RedisSessionService(self.collection, self.redis, clock=lambda: self.now)

    def set_value(self, key, value, *, nx, ex):
        self.assertTrue(nx)
        self.assertEqual(ex, SESSION_TTL_SECONDS)
        if key in self.data:
            return False
        self.data[key] = value
        return True

    def test_two_sessions_are_independent_and_hide_raw_tokens(self):
        alice = self.service.create_demo_session("client-a")
        bruno = self.service.create_demo_session("client-b")
        self.assertNotEqual(alice.token, bruno.token)
        self.assertEqual(len(alice.token), 43)
        self.assertEqual(alice.expires_at - alice.created_at, timedelta(hours=8))
        self.assertEqual(alice.created_at.utcoffset(), timedelta(0))
        self.assertNotIn(alice.token, repr(alice))
        key = "session:" + hashlib.sha256(alice.token.encode()).hexdigest()
        self.assertIn(key, self.data)
        self.assertNotIn(alice.token, str(self.data))
        self.assertEqual(set(json.loads(self.data[key])), {"customer_id", "created_at", "expires_at"})
        self.assertEqual(self.service.resolve(alice.token).customer_id, "client-a")
        self.assertEqual(self.service.resolve(bruno.token).customer_id, "client-b")
        self.service.logout(alice.token)
        self.service.logout(alice.token)
        with self.assertRaises(SessionExpiredError):
            self.service.resolve(alice.token)
        self.assertEqual(self.service.resolve(bruno.token).customer_id, "client-b")

    def test_same_customer_can_have_multiple_sessions(self):
        first = self.service.create_demo_session("client-a")
        second = self.service.create_demo_session("client-a")
        self.service.logout(first.token)
        self.assertEqual(self.service.resolve(second.token).customer_id, "client-a")

    def test_missing_or_invalid_customer_never_creates_a_session(self):
        with self.assertRaises(NotFoundError):
            self.service.create_demo_session("absent")
        for customer_id in (None, {"$ne": None}, "", "a" * 201):
            with self.assertRaises(ValidationError):
                self.service.create_demo_session(customer_id)
        self.redis.set.assert_not_called()

    def test_expiry_is_fixed_and_reads_do_not_renew(self):
        session = self.service.create_demo_session("client-a")
        self.now += timedelta(hours=7)
        self.service.resolve(session.token)
        self.redis.set.assert_called_once()
        self.redis.expire.assert_not_called()
        self.now += timedelta(hours=1)
        with self.assertRaises(SessionExpiredError):
            self.service.resolve(session.token)
        self.assertFalse(self.data)

    def test_invalid_missing_and_malformed_sessions_are_rejected(self):
        for token in (None, "", "client-a", {"customer_id": "client-a"}):
            with self.assertRaises(SessionExpiredError):
                self.service.resolve(token)
        for payload in (None, "not json", "[]", "{}", '{"created_at":0}'):
            session = self.service.create_demo_session("client-a")
            key = self.service._key(session.token)
            if payload is None:
                self.data.pop(key)
            else:
                self.data[key] = payload
            with self.assertRaises(SessionExpiredError):
                self.service.resolve(session.token)

    def test_invalid_dates_and_customer_ids_are_rejected(self):
        for change in ({"customer_id": {"$ne": None}}, {"created_at": "2026-01-01"},
                       {"expires_at": "2027-01-01T00:00:00+00:00"}):
            session = self.service.create_demo_session("client-a")
            key = self.service._key(session.token)
            data = json.loads(self.data[key])
            data.update(change)
            self.data[key] = json.dumps(data)
            with self.assertRaises(SessionExpiredError):
                self.service.resolve(session.token)

    def test_deleted_customer_revokes_session_and_updates_are_visible(self):
        session = self.service.create_demo_session("client-a")
        self.customers["client-a"]["name"] = "Updated"
        self.assertEqual(self.service.resolve(session.token).name, "Updated")
        del self.customers["client-a"]
        with self.assertRaises(SessionExpiredError):
            self.service.resolve(session.token)
        self.assertFalse(self.data)

    def test_redis_failures_never_authorize(self):
        session = self.service.create_demo_session("client-a")
        for operation, action in (
            ("set", lambda: self.service.create_demo_session("client-a")),
            ("get", lambda: self.service.resolve(session.token)),
            ("delete", lambda: self.service.logout(session.token)),
        ):
            previous = getattr(self.redis, operation).side_effect
            getattr(self.redis, operation).side_effect = ConnectionError("private connection details")
            with self.assertRaises(ServiceUnavailableError) as raised:
                action()
            self.assertNotIn("private", str(raised.exception))
            getattr(self.redis, operation).side_effect = previous

    def test_mongo_failure_or_bad_customer_data_never_authorizes(self):
        session = self.service.create_demo_session("client-a")
        self.collection.find_one.side_effect = ConnectionFailure("private details")
        with self.assertRaises(ServiceUnavailableError):
            self.service.resolve(session.token)
        self.collection.find_one.side_effect = None
        self.collection.find_one.return_value = {"_id": "client-a"}
        with self.assertRaises(ServiceUnavailableError):
            self.service.resolve(session.token)

    def test_collision_does_not_overwrite_an_existing_session(self):
        self.redis.set.side_effect = None
        self.redis.set.return_value = False
        with self.assertRaises(ServiceUnavailableError):
            self.service.create_demo_session("client-a")
        self.assertEqual(self.redis.set.call_count, 3)

    def test_session_configuration_is_independent_from_cache_and_neo4j(self):
        with patch("src.database.config.load_dotenv"), patch.dict("os.environ", {
            "REDIS_PASSWORD": "secret@password", "REDIS_PORT": "6380",
            "CATALOG_CACHE_TTL_SECONDS": "invalid",
        }, clear=True):
            settings = RedisSessionSettings.from_env()
            self.assertEqual(settings.redis_url, "redis://:secret%40password@localhost:6380/0")
            self.assertEqual(settings.timeout_seconds, 1)
            self.assertNotIn("secret", repr(settings))
        with patch("src.database.config.load_dotenv"), patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                RedisSessionSettings.from_env()
