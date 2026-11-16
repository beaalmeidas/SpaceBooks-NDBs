"""Demonstration identity: MongoDB customers and fixed-lifetime Redis sessions."""

import hashlib
import json
import re
import secrets
from datetime import date, datetime, timedelta, timezone

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from src.database.config import MongoSettings, RedisSessionSettings
from src.domain.contracts import (
    SESSION_TTL_SECONDS, NotFoundError, ServiceUnavailableError, Session,
    SessionExpiredError, ValidationError,
)
from src.domain.models import Customer


CUSTOMER_FIELDS = {key: 1 for key in (
    "_id", "name", "email", "favorite_categories", "favorite_authors", "created_at",
)}


def customer_from_document(document: dict) -> Customer:
    try:
        categories, authors = document["favorite_categories"], document["favorite_authors"]
        if not isinstance(categories, list) or not isinstance(authors, list):
            raise ValueError("Expected lists")
        return Customer(document["_id"], document["name"], document["email"],
                        tuple(categories), tuple(authors), date.fromisoformat(document["created_at"]))
    except (KeyError, TypeError, ValueError):
        raise ServiceUnavailableError("O cadastro do cliente contém dados inválidos.") from None


class RedisSessionService:
    def __init__(self, customers, redis, *, namespace="session", mongo_client=None,
                 owns_redis=False, query_timeout_ms=60000, clock=None):
        self._customers = customers
        self._redis = redis
        self._namespace = namespace
        self._mongo_client = mongo_client
        self._owns_redis = owns_redis
        self._query_timeout_ms = query_timeout_ms
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def from_env(cls):
        mongo = redis = None
        try:
            settings = MongoSettings.from_env()
            session_settings = RedisSessionSettings.from_env()
            timeout_ms = int(settings.timeout_seconds * 1000)
            mongo = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=timeout_ms,
                                connectTimeoutMS=timeout_ms, socketTimeoutMS=timeout_ms)
            redis = Redis.from_url(
                session_settings.redis_url, decode_responses=True,
                socket_timeout=session_settings.timeout_seconds,
                socket_connect_timeout=session_settings.timeout_seconds,
                retry=Retry(NoBackoff(), 0),
            )
            return cls(mongo[settings.mongo_database].customers, redis, mongo_client=mongo,
                       owns_redis=True, query_timeout_ms=int(settings.query_timeout_seconds * 1000))
        except (ValueError, TypeError, OSError, PyMongoError, RedisError):
            if redis is not None:
                redis.close()
            if mongo is not None:
                mongo.close()
            raise ServiceUnavailableError("Não foi possível configurar a identificação. Confira MongoDB e Redis.") from None

    def close(self):
        if self._owns_redis:
            self._redis.close()
        if self._mongo_client is not None:
            self._mongo_client.close()

    def list_customers(self, search: str = "") -> tuple[Customer, ...]:
        """At most 50 candidates, ordered by name and ID; input is literal text."""
        if not isinstance(search, str) or len(search) > 200:
            raise ValidationError("Pesquise por nome ou ID usando até 200 caracteres.")
        expression = {"$regex": re.escape(search.strip()), "$options": "i"}
        filters = {"$or": [{"name": expression}, {"_id": expression}]} if search.strip() else {}
        try:
            with self._customers.find(filters, CUSTOMER_FIELDS).sort([
                ("name", 1), ("_id", 1),
            ]).limit(50).max_time_ms(self._query_timeout_ms) as cursor:
                return tuple(customer_from_document(document) for document in cursor)
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível consultar os clientes no MongoDB.") from None

    def _customer(self, customer_id):
        if not isinstance(customer_id, str) or not customer_id.strip() or len(customer_id) > 200:
            raise ValidationError("Cliente inválido.")
        try:
            document = self._customers.find_one({"_id": customer_id}, CUSTOMER_FIELDS,
                                                max_time_ms=self._query_timeout_ms)
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível consultar o cliente no MongoDB.") from None
        if document is None:
            raise NotFoundError("Cliente não encontrado.")
        return customer_from_document(document)

    def _key(self, token):
        if not isinstance(token, str) or re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is None:
            raise SessionExpiredError("Sessão inválida ou expirada. Identifique-se novamente.")
        return f"{self._namespace}:{hashlib.sha256(token.encode('ascii')).hexdigest()}"

    def create_demo_session(self, customer_id: str) -> Session:
        customer = self._customer(customer_id)
        now = self._clock()
        expires = now + timedelta(seconds=SESSION_TTL_SECONDS)
        payload = json.dumps({"customer_id": customer.customer_id, "created_at": now.isoformat(),
                              "expires_at": expires.isoformat()})
        try:
            for _ in range(3):
                token = secrets.token_urlsafe(32)
                if self._redis.set(self._key(token), payload, nx=True, ex=SESSION_TTL_SECONDS):
                    return Session(token, customer.customer_id, now, expires)
        except RedisError:
            raise ServiceUnavailableError("Redis indisponível. Não foi possível iniciar a sessão.") from None
        raise ServiceUnavailableError("Não foi possível gerar uma sessão. Tente novamente.")

    def resolve(self, token: str) -> Customer:
        key = self._key(token)
        try:
            payload = self._redis.get(key)
            if payload is None:
                raise SessionExpiredError("Sessão inválida ou expirada. Identifique-se novamente.")
            try:
                data = json.loads(payload)
                created = datetime.fromisoformat(data["created_at"])
                expires = datetime.fromisoformat(data["expires_at"])
                customer_id = data["customer_id"]
                if (not isinstance(customer_id, str) or not customer_id.strip() or len(customer_id) > 200
                        or created.tzinfo is None or expires.tzinfo is None
                        or expires - created != timedelta(seconds=SESSION_TTL_SECONDS)
                        or not created <= self._clock() < expires):
                    raise ValueError("Invalid session")
            except (TypeError, KeyError, ValueError, OverflowError):
                self._redis.delete(key)
                raise SessionExpiredError("Sessão inválida ou expirada. Identifique-se novamente.") from None
            try:
                return self._customer(customer_id)
            except NotFoundError:
                self._redis.delete(key)
                raise SessionExpiredError("O cliente desta sessão não está mais cadastrado.") from None
        except (RedisError, UnicodeError):
            raise ServiceUnavailableError("Redis indisponível. Não foi possível validar a sessão.") from None

    def logout(self, token: str) -> None:
        try:
            key = self._key(token)
        except SessionExpiredError:
            return
        try:
            self._redis.delete(key)
        except RedisError:
            raise ServiceUnavailableError("Saída local concluída. A revogação no Redis não foi confirmada; a sessão remota expira em até 8 horas.") from None
