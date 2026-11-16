"""Transactional MongoDB checkout with durable, idempotent post-commit recovery."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from neo4j.exceptions import Neo4jError, DriverError
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.read_preferences import ReadPreference
from pymongo.write_concern import WriteConcern
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from src.database.config import Settings
from src.domain.contracts import (
    CartLine, CartView, CheckoutResult, ConflictError, NotFoundError, ServiceUnavailableError,
    SessionExpiredError, StockUnavailableError, ValidationError,
)
from src.domain.models import Order, OrderItem
from src.services.cart import RedisCartService
from src.services.catalog import MongoCatalogService, book_from_document
from src.services.catalog_cache import CatalogInvalidator, RedisCatalogCache
from src.services.purchases_graph import PurchaseGraph
from src.services.sessions import RedisSessionService


CLEAN_CART = """
if redis.call('EXISTS', KEYS[1]) == 0 then return 2 end
if redis.call('HGET', KEYS[2], 'revision') ~= ARGV[1] then return 3 end
redis.call('DEL', KEYS[1], KEYS[2])
return 1
"""


def validate_uuid(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Identificador de tentativa ou revisão inválido.") from None


def order_from_document(document):
    try:
        order = Order(document["_id"], document["customer_id"],
                      tuple(OrderItem(**item) for item in document["items"]),
                      datetime.fromisoformat(document["created_at"].replace("Z", "+00:00")),
                      status=document["status"], currency=document["currency"])
        if order.total_cents != document["total_cents"] or order.status != "confirmed":
            raise ValueError()
        return order
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ServiceUnavailableError("O pedido contém dados inválidos. Solicite a verificação do cadastro.") from None


class MongoCheckoutService:
    def __init__(self, db, sessions, carts, redis, graph, invalidator, *, owned_resources=()):
        self.db, self.sessions, self.carts = db, sessions, carts
        self.redis, self.graph, self.invalidator = redis, graph, invalidator
        self._owned_resources = owned_resources

    @classmethod
    def from_env(cls):
        resources = []
        try:
            settings = Settings.from_env()
            timeout_ms = int(settings.timeout_seconds * 1000)
            mongo = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=timeout_ms,
                                connectTimeoutMS=timeout_ms, socketTimeoutMS=timeout_ms)
            resources.append(mongo)
            redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1,
                                   socket_connect_timeout=1, retry=Retry(NoBackoff(), 0))
            resources.append(redis)
            graph = PurchaseGraph.from_settings(settings)
            resources.append(graph)
            db = mongo[settings.mongo_database]
            sessions = RedisSessionService(db.customers, redis)
            carts = RedisCartService(redis, sessions, MongoCatalogService(db.books))
            service = cls(db, sessions, carts, redis, graph,
                          CatalogInvalidator(db.catalog_cache_state, RedisCatalogCache(redis)),
                          owned_resources=tuple(resources))
            service.ensure_schema()
            return service
        except (ValueError, TypeError, OSError, PyMongoError, RedisError, Neo4jError, DriverError):
            for resource in reversed(resources):
                resource.close()
            raise ServiceUnavailableError("Não foi possível configurar o checkout. Confira os bancos e o replica set MongoDB.") from None

    def close(self):
        for resource in reversed(self._owned_resources):
            resource.close()

    def ensure_schema(self):
        self.db.orders.create_index([("customer_id", 1), ("cart_revision", 1)], unique=True,
                                    partialFilterExpression={"cart_revision": {"$type": "string"}},
                                    name="one_order_per_cart_revision")
        self.db.orders.create_index([("integration.graph_status", 1), ("created_at", 1)], name="pending_graph")
        self.db.checkout_attempts.create_index("created_at", expireAfterSeconds=172800, name="review_expiration")

    @staticmethod
    def _owned(document, customer_id):
        if document is None or document["customer_id"] != customer_id:
            raise NotFoundError("Pedido ou tentativa não encontrado.")
        return document

    def prepare(self, session_token, request_id, expected_revision):
        customer = self.sessions.resolve(session_token)
        validate_uuid(request_id)
        validate_uuid(expected_revision)
        try:
            if self.db.orders.find_one({"_id": request_id}):
                self._owned(self.db.orders.find_one({"_id": request_id}), customer.customer_id)
                raise ConflictError("Esta tentativa já foi confirmada. Consulte o pedido.")
            existing = self.db.checkout_attempts.find_one({"_id": request_id})
            if existing is None:
                cart = self.carts.get_cart(session_token)
                if not cart.items:
                    raise ValidationError("O carrinho está vazio.")
                if cart.revision != expected_revision:
                    raise ConflictError("O carrinho mudou. Revise a compra novamente.")
                if any(line.quantity > line.book.stock for line in cart.items):
                    raise StockUnavailableError("Estoque insuficiente. Ajuste o carrinho antes de revisar a compra.")
                document = {"_id": request_id, "customer_id": customer.customer_id,
                            "cart_revision": cart.revision, "created_at": datetime.now(timezone.utc),
                            "items": [{"book": line.book.to_document(), "quantity": line.quantity} for line in cart.items]}
                try:
                    self.db.checkout_attempts.insert_one(document)
                    existing = document
                except DuplicateKeyError:
                    existing = self.db.checkout_attempts.find_one({"_id": request_id})
            existing = self._owned(existing, customer.customer_id)
            if existing["cart_revision"] != expected_revision:
                raise ConflictError("Esta tentativa pertence a outra revisão do carrinho.")
            lines = tuple(CartLine(book_from_document(item["book"]), item["quantity"],
                                   item["book"]["price_cents"] * item["quantity"]) for item in existing["items"])
            return CartView(customer.customer_id, existing["cart_revision"], lines,
                            sum(line.subtotal_cents for line in lines))
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível registrar a revisão da compra no MongoDB.") from None

    def checkout(self, session_token, request_id, expected_revision):
        customer = self.sessions.resolve(session_token)
        validate_uuid(request_id)
        validate_uuid(expected_revision)
        try:
            existing = self.db.orders.find_one({"_id": request_id})
            if existing is not None:
                return self._result(self._recover(self._owned(existing, customer.customer_id)))
            attempt = self._owned(self.db.checkout_attempts.find_one({"_id": request_id}), customer.customer_id)
            cart = self.carts.get_cart(session_token)
            # Another submission may have committed between the first lookup
            # and this Redis read, including clearing this exact cart revision.
            if not cart.items or cart.revision != expected_revision:
                existing = self.db.orders.find_one({"_id": request_id})
                if existing is not None:
                    return self._result(self._recover(self._owned(existing, customer.customer_id)))
            if not cart.items:
                raise ValidationError("O carrinho está vazio.")
            if cart.revision != expected_revision or attempt["cart_revision"] != expected_revision:
                raise ConflictError("O carrinho mudou. Revise a compra novamente.")
            approved = {item["book"]["_id"]: (item["quantity"], item["book"]["price_cents"]) for item in attempt["items"]}
            if approved != {line.book.isbn: (line.quantity, line.book.price_cents) for line in cart.items}:
                raise ConflictError("Os preços ou itens mudaram. Revise a compra novamente.")

            def commit(session):
                previous = self.db.orders.find_one({"_id": request_id}, session=session)
                if previous is not None:
                    return self._owned(previous, customer.customer_id)
                if not self.db.customers.find_one({"_id": customer.customer_id}, session=session):
                    raise SessionExpiredError("O cliente não está mais cadastrado.")
                lines = []
                for isbn, (quantity, approved_price) in sorted(approved.items()):
                    document = self.db.books.find_one({"_id": isbn}, session=session)
                    if document is None:
                        raise NotFoundError("Um livro foi excluído. Revise o carrinho.")
                    book = book_from_document(document)
                    if book.price_cents != approved_price:
                        raise ConflictError("Um preço mudou. Revise a compra novamente.")
                    if quantity > book.stock:
                        raise StockUnavailableError("Estoque insuficiente. Revise o carrinho.")
                    updated = self.db.books.update_one({"_id": isbn, "stock": {"$gte": quantity},
                                                        "price_cents": approved_price, "currency": "BRL"},
                                                       {"$inc": {"stock": -quantity}}, session=session)
                    if updated.modified_count != 1:
                        raise StockUnavailableError("Estoque ou preço alterado. Revise o carrinho.")
                    lines.append(OrderItem(isbn, book.title, quantity, book.price_cents))
                order = Order(request_id, customer.customer_id, tuple(lines), datetime.now(timezone.utc))
                document = order.to_document()
                document.update(cart_revision=expected_revision, integration={
                    "graph_status": "pending", "cart_status": "pending", "cache_status": "pending",
                    "cart_cleanup": "pending",
                })
                self.db.orders.insert_one(document, session=session)
                self.db.catalog_cache_state.update_one({"_id": "catalog"}, {"$set": {
                    "revision": uuid4().hex, "pending": True,
                }}, upsert=True, session=session)
                return document

            with self.db.client.start_session() as session:
                document = session.with_transaction(commit, read_concern=ReadConcern("snapshot"),
                                                    read_preference=ReadPreference.PRIMARY,
                                                    write_concern=WriteConcern("majority"), max_commit_time_ms=10000)
        except DuplicateKeyError:
            try:
                existing = self.db.orders.find_one({"_id": request_id})
                if existing is not None:
                    return self._result(self._recover(self._owned(existing, customer.customer_id)))
            except PyMongoError:
                raise ServiceUnavailableError("Não foi possível recuperar a confirmação. Consulte esta mesma tentativa.") from None
            raise ConflictError("Esta revisão do carrinho já possui uma compra. Consulte o pedido antes de tentar novamente.") from None
        except PyMongoError:
            # A lost commit reply is ambiguous. Never generate another request ID.
            raise ServiceUnavailableError("Não foi possível obter a confirmação. Consulte ou repita esta mesma tentativa; mantenha seu identificador.") from None
        return self._result(self._recover(document))

    def _result(self, document):
        state = document["integration"]
        return CheckoutResult(order_from_document(document), state["graph_status"], state["cart_status"],
                              state["cache_status"], state.get("cart_cleanup", "pending"))

    def _recover(self, document):
        order = order_from_document(document)
        state = dict(document["integration"])
        document = {**document, "integration": state}
        for stage in ("graph", "cart", "cache"):
            field = f"{stage}_status"
            if state[field] == "done":
                continue
            try:
                extra = {}
                if stage == "graph":
                    self.graph.record(order)
                elif stage == "cart":
                    code = self.redis.eval(CLEAN_CART, 2, *self.carts._keys(order.customer_id), document["cart_revision"])
                    extra["cart_cleanup"] = {1: "cleared", 2: "already_absent", 3: "preserved"}[code]
                elif not self.invalidator.flush():
                    continue
                changes = {field: "done", **extra}
                result = self.db.orders.update_one({"_id": order.order_id}, {"$set": {
                    f"integration.{key}": value for key, value in changes.items()
                }})
                if result.matched_count:
                    state.update(changes)
            except (PyMongoError, RedisError, Neo4jError, DriverError, OSError, ServiceUnavailableError):
                # The order is already committed; the durable marker remains pending.
                continue
        return document

    def get_order(self, session_token, order_id):
        customer = self.sessions.resolve(session_token)
        validate_uuid(order_id)
        try:
            document = self._owned(self.db.orders.find_one({"_id": order_id}), customer.customer_id)
            return self._result(self._recover(document))
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível consultar o pedido no MongoDB.") from None

    def retry_pending(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValidationError("O limite deve estar entre 1 e 1000.")
        try:
            documents = list(self.db.orders.find({"status": "confirmed", "$or": [
                {f"integration.{stage}_status": "pending"} for stage in ("graph", "cart", "cache")
            ]}).sort([("created_at", 1), ("_id", 1)]).limit(limit))
            completed = 0
            for document in documents:
                result = self._result(self._recover(document))
                completed += all(value == "done" for value in (result.graph_status, result.cart_status, result.cache_status))
            return completed
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível recuperar as pendências de checkout.") from None
