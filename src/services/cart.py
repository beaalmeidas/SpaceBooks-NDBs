"""Customer carts in Redis; commercial values always come from MongoDB."""

from uuid import UUID, uuid4

from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError, WatchError
from redis.retry import Retry

from src.database.config import RedisSessionSettings
from src.domain.contracts import (
    CART_TTL_SECONDS, CartLine, CartView, ConflictError, NotFoundError,
    ServiceUnavailableError, StockUnavailableError, ValidationError,
)
from src.services.catalog import MongoCatalogService, validate_book_id
from src.services.sessions import RedisSessionService


MAX_QUANTITY = 2_147_483_647


def validate_quantity(quantity):
    if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
        raise ValidationError("A quantidade deve ser um inteiro positivo de até 2.147.483.647.")


class RedisCartService:
    def __init__(self, redis, sessions, catalog, *, namespace="cart", owned_resources=()):
        self._redis = redis
        self._sessions = sessions
        self._catalog = catalog  # Direct MongoCatalogService, never the catalog cache.
        self._namespace = namespace
        self._owned_resources = owned_resources

    @classmethod
    def from_env(cls):
        resources = []
        try:
            settings = RedisSessionSettings.from_env()
            redis = Redis.from_url(settings.redis_url, decode_responses=True,
                                   socket_timeout=settings.timeout_seconds,
                                   socket_connect_timeout=settings.timeout_seconds,
                                   retry=Retry(NoBackoff(), 0))
            resources.append(redis)
            sessions = RedisSessionService.from_env()
            resources.append(sessions)
            catalog = MongoCatalogService.from_env()
            resources.append(catalog)
            return cls(redis, sessions, catalog, owned_resources=tuple(resources))
        except (ValueError, TypeError, OSError, RedisError, ServiceUnavailableError):
            for resource in reversed(resources):
                resource.close()
            raise ServiceUnavailableError("Não foi possível configurar o carrinho. Confira MongoDB e Redis.") from None

    def close(self):
        for resource in reversed(self._owned_resources):
            resource.close()

    def _keys(self, customer_id):
        return f"{self._namespace}:{customer_id}", f"{self._namespace}:meta:{customer_id}"

    @staticmethod
    def _decode(items, metadata):
        try:
            quantities = {}
            for isbn, raw in items.items():
                validate_book_id(isbn)
                if not isinstance(raw, str) or not raw.isascii() or not raw.isdigit():
                    raise ValueError("Invalid stored quantity")
                quantity = int(raw)
                validate_quantity(quantity)
                if str(quantity) != raw:
                    raise ValueError("Invalid stored quantity")
                quantities[isbn] = quantity
            revision = metadata.get("revision") if quantities else None
            if quantities and (not isinstance(revision, str) or str(UUID(revision)) != revision):
                raise ValueError("Invalid revision")
            return quantities, revision
        except (ValueError, TypeError, AttributeError, ValidationError):
            raise ServiceUnavailableError("O carrinho contém dados inválidos. Solicite a verificação do Redis.") from None

    def _view(self, customer_id, quantities, revision):
        lines = []
        for isbn, quantity in sorted(quantities.items()):
            try:
                book = self._catalog.get_book(isbn)
            except NotFoundError:
                raise NotFoundError(f"O livro {isbn} não está mais no catálogo. Remova-o do carrinho pelo ISBN.") from None
            lines.append(CartLine(book, quantity, book.price_cents * quantity))
        return CartView(customer_id, revision, tuple(lines), sum(line.subtotal_cents for line in lines))

    def get_cart(self, session_token):
        customer = self._sessions.resolve(session_token)
        keys = self._keys(customer.customer_id)
        try:
            with self._redis.pipeline(transaction=True) as pipe:
                items, metadata = pipe.hgetall(keys[0]).hgetall(keys[1]).execute()
            quantities, revision = self._decode(items, metadata)
        except (RedisError, UnicodeError):
            raise ServiceUnavailableError("Não foi possível consultar o carrinho no Redis.") from None
        return self._view(customer.customer_id, quantities, revision)

    def add_item(self, session_token, book_id, quantity=1):
        return self._mutate(session_token, book_id, "add", quantity)

    def set_quantity(self, session_token, book_id, quantity):
        return self._mutate(session_token, book_id, "set", quantity)

    def remove_item(self, session_token, book_id):
        return self._mutate(session_token, book_id, "remove")

    def _mutate(self, token, isbn, operation, quantity=None):
        customer = self._sessions.resolve(token)
        validate_book_id(isbn)
        if operation != "remove":
            validate_quantity(quantity)
            book = self._catalog.get_book(isbn)
        keys = self._keys(customer.customer_id)
        try:
            for _ in range(5):
                with self._redis.pipeline() as pipe:
                    try:
                        pipe.watch(*keys)
                        items, revision = self._decode(pipe.hgetall(keys[0]), pipe.hgetall(keys[1]))
                        previous = items.get(isbn)
                        if operation == "set" and previous is None:
                            raise NotFoundError("O livro não está no carrinho.")
                        if operation == "remove":
                            target = None
                        else:
                            target = quantity + (previous or 0) if operation == "add" else quantity
                            validate_quantity(target)
                            if target > book.stock:
                                raise StockUnavailableError("A quantidade solicitada supera o estoque atual. O carrinho não reserva unidades.")
                        if previous == target:
                            # Validate WATCH even on no-ops, without renewing TTL.
                            pipe.multi()
                            pipe.ping()
                            pipe.execute()
                            return self._view(customer.customer_id, items, revision)
                        if target is None:
                            items.pop(isbn, None)
                        else:
                            items[isbn] = target
                        revision = str(uuid4()) if items else None
                        pipe.multi()
                        if not items:
                            pipe.delete(*keys)
                        else:
                            if target is None:
                                pipe.hdel(keys[0], isbn)
                            else:
                                pipe.hset(keys[0], isbn, str(target))
                            pipe.hset(keys[1], "revision", revision)
                            pipe.expire(keys[0], CART_TTL_SECONDS)
                            pipe.expire(keys[1], CART_TTL_SECONDS)
                        pipe.execute()
                    except WatchError as error:
                        # redis-py can wrap a lost EXEC reply as WatchError. Only
                        # optimistic conflicts are safe to replay automatically.
                        cause = error.__cause__ or error.__context__
                        if isinstance(cause, (RedisConnectionError, RedisTimeoutError)):
                            raise ServiceUnavailableError("A conexão caiu durante a alteração. Atualize o carrinho antes de repetir a operação.") from None
                        continue
                    return self._view(customer.customer_id, items, revision)
        except (RedisError, UnicodeError):
            raise ServiceUnavailableError("Redis indisponível. Atualize o carrinho para conferir os itens antes de repetir a alteração.") from None
        raise ConflictError("O carrinho foi alterado simultaneamente. Atualize e tente novamente.")
