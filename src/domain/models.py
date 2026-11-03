"""Domain rules and storage projections, without database connections."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _integer(value: int, field: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")


def _labels(values: tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be a tuple of strings")
    for value in values:
        _text(value, field)
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("created_at must be a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Book:
    isbn: str
    title: str
    authors: tuple[str, ...]
    categories: tuple[str, ...]
    price_cents: int
    stock: int
    isbn10: str | None = None
    subtitle: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    published_year: int | None = None
    average_rating: float | None = None
    num_pages: int | None = None
    ratings_count: int = 0
    currency: str = "BRL"

    def __post_init__(self) -> None:
        if not isinstance(self.isbn, str) or len(self.isbn) != 13 or not self.isbn.isascii() or not self.isbn.isdigit():
            raise ValueError("isbn must contain 13 ASCII digits")
        _text(self.title, "title")
        _labels(self.authors, "authors")
        _labels(self.categories, "categories")
        if not self.authors or not self.categories:
            raise ValueError("book must have at least one author and category")
        _integer(self.price_cents, "price_cents", 1)
        _integer(self.stock, "stock")
        _integer(self.ratings_count, "ratings_count")
        if self.num_pages is not None:
            _integer(self.num_pages, "num_pages", 1)
        if self.published_year is not None:
            _integer(self.published_year, "published_year", 1)
        if self.average_rating is not None:
            if type(self.average_rating) not in (int, float) or not 0 <= self.average_rating <= 5:
                raise ValueError("average_rating must be between 0 and 5")
        if self.currency != "BRL":
            raise ValueError("only BRL is supported")

    def to_document(self) -> dict[str, Any]:
        document = asdict(self)
        document["_id"] = document.pop("isbn")
        document["authors"] = list(self.authors)
        document["categories"] = list(self.categories)
        return document


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str
    email: str
    favorite_categories: tuple[str, ...]
    favorite_authors: tuple[str, ...]
    created_at: date

    def __post_init__(self) -> None:
        _text(self.customer_id, "customer_id")
        _text(self.name, "name")
        _text(self.email, "email")
        local, separator, domain = self.email.partition("@")
        if not separator or not local or "." not in domain or "@" in domain or any(c.isspace() for c in self.email):
            raise ValueError("email must have a local part and domain")
        _labels(self.favorite_categories, "favorite_categories")
        _labels(self.favorite_authors, "favorite_authors")
        if type(self.created_at) is not date:
            raise ValueError("created_at must be a date")

    def to_document(self) -> dict[str, Any]:
        document = asdict(self)
        document["_id"] = document.pop("customer_id")
        document["favorite_categories"] = list(self.favorite_categories)
        document["favorite_authors"] = list(self.favorite_authors)
        document["created_at"] = self.created_at.isoformat()
        return document


@dataclass(frozen=True)
class OrderItem:
    book_id: str
    title: str
    quantity: int
    unit_price_cents: int

    def __post_init__(self) -> None:
        _text(self.book_id, "book_id")
        _text(self.title, "title")
        _integer(self.quantity, "quantity", 1)
        _integer(self.unit_price_cents, "unit_price_cents", 1)

    @property
    def subtotal_cents(self) -> int:
        return self.quantity * self.unit_price_cents


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    items: tuple[OrderItem, ...]
    created_at: datetime
    status: str = "confirmed"
    currency: str = "BRL"

    def __post_init__(self) -> None:
        _text(self.order_id, "order_id")
        _text(self.customer_id, "customer_id")
        _timestamp(self.created_at)
        if not isinstance(self.items, tuple) or not self.items or not all(isinstance(item, OrderItem) for item in self.items):
            raise ValueError("items must be a non-empty tuple of OrderItem")
        if len({item.book_id for item in self.items}) != len(self.items):
            raise ValueError("an order must have one item per book")
        if self.status not in ("confirmed", "cancelled"):
            raise ValueError("invalid order status")
        if self.currency != "BRL":
            raise ValueError("only BRL is supported")

    @property
    def total_cents(self) -> int:
        return sum(item.subtotal_cents for item in self.items)

    @classmethod
    def from_cart(cls, order_id: str, cart: "Cart", catalog: dict[str, Book], created_at: datetime) -> "Order":
        """Snapshot current catalog prices; stock reservation belongs to checkout."""
        items = []
        for book_id, quantity in cart.items:
            if book_id not in catalog:
                raise ValueError(f"unknown book: {book_id}")
            book = catalog[book_id]
            if book.isbn != book_id:
                raise ValueError(f"catalog key does not match ISBN: {book_id}")
            if quantity > book.stock:
                raise ValueError(f"insufficient stock for {book_id}")
            items.append(OrderItem(book_id, book.title, quantity, book.price_cents))
        return cls(order_id, cart.customer_id, tuple(items), created_at)

    def to_document(self) -> dict[str, Any]:
        return {
            "_id": self.order_id,
            "customer_id": self.customer_id,
            "items": [asdict(item) for item in self.items],
            "total_cents": self.total_cents,
            "currency": self.currency,
            "created_at": _timestamp(self.created_at),
            "status": self.status,
        }

    def to_graph_records(self) -> list[dict[str, Any]]:
        """Project confirmed purchases; cancellation cleanup belongs to its service."""
        if self.status != "confirmed":
            return []
        return [
            {
                "type": "relationship", "relationship": "COMPROU",
                "source": {"label": "Cliente", "id": self.customer_id},
                "target": {"label": "Produto", "id": item.book_id},
                "properties": {
                    "pedido_id": self.order_id, "quantidade": item.quantity,
                    "unit_price_cents": item.unit_price_cents,
                    "created_at": _timestamp(self.created_at),
                },
            }
            for item in self.items
        ]


@dataclass(frozen=True)
class Review:
    customer_id: str
    book_id: str
    rating: int
    created_at: datetime

    def __post_init__(self) -> None:
        _text(self.customer_id, "customer_id")
        _text(self.book_id, "book_id")
        _integer(self.rating, "rating", 1)
        if self.rating > 5:
            raise ValueError("rating must be between 1 and 5")
        _timestamp(self.created_at)

    def to_graph_record(self) -> dict[str, Any]:
        return {
            "type": "relationship", "relationship": "AVALIOU",
            "source": {"label": "Cliente", "id": self.customer_id},
            "target": {"label": "Produto", "id": self.book_id},
            "properties": {"nota": self.rating, "created_at": _timestamp(self.created_at)},
        }


@dataclass(frozen=True)
class Cart:
    customer_id: str
    items: tuple[tuple[str, int], ...] = ()
    ttl_seconds: int = 86400

    def __post_init__(self) -> None:
        _text(self.customer_id, "customer_id")
        _integer(self.ttl_seconds, "ttl_seconds", 1)
        if not isinstance(self.items, tuple):
            raise ValueError("items must be a tuple of (book_id, quantity) tuples")
        seen = set()
        for item in self.items:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("each cart item must be a (book_id, quantity) tuple")
            book_id, quantity = item
            _text(book_id, "book_id")
            _integer(quantity, "quantity", 1)
            if book_id in seen:
                raise ValueError("a cart must have one item per book")
            seen.add(book_id)

    @property
    def redis_key(self) -> str:
        return f"cart:{self.customer_id}"

    def to_redis_hash(self) -> dict[str, str]:
        """HSET mapping; the adapter must apply EXPIRE separately."""
        return {book_id: str(quantity) for book_id, quantity in self.items}


def parse_integer(value: str, field: str) -> int:
    """Accept CSV values such as '247.0' without silently rounding."""
    try:
        number = Decimal(value)
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError(f"{field} must be an integer")
        return int(number)
    except (InvalidOperation, TypeError) as error:
        raise ValueError(f"invalid {field}: {value!r}") from error
