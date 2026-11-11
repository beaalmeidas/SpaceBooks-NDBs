"""Shared service interfaces. Adapters and UI flows are implemented separately.

See docs/data-model.md for normalization, authorization and persistence rules.
These Protocols describe behavior; they do not connect to databases.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

from .models import Book, Customer, Order, Review


SESSION_TTL_SECONDS = 28800
CART_TTL_SECONDS = 86400
CATALOG_CACHE_TTL_SECONDS = 60


class ServiceError(Exception):
    """Base for safe, user-facing service failures; never include credentials."""


class ValidationError(ServiceError):
    """Invalid input, including an empty checkout cart."""


class NotFoundError(ServiceError):
    """A requested book, customer or order does not exist or is inaccessible."""


class SessionExpiredError(ServiceError):
    """Session is missing, invalid, revoked or expired."""


class StockUnavailableError(ServiceError):
    """Requested quantity cannot be fulfilled."""


class ConflictError(ServiceError):
    """Cart revision or checkout request conflicts with current state."""


class ServiceUnavailableError(ServiceError):
    """A required dependency is unavailable; no secrets in the message."""


@dataclass(frozen=True)
class CatalogQuery:
    search: str = ""
    category: str | None = None
    page: int = 1
    page_size: int = 24
    sort: Literal["title_asc", "price_asc", "price_desc"] = "title_asc"


@dataclass(frozen=True)
class CatalogPage:
    items: tuple[Book, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class Session:
    """Internal DTO: token must not be rendered, logged or saved in MongoDB."""

    token: str = field(repr=False)
    customer_id: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class CartLine:
    book: Book
    quantity: int
    subtotal_cents: int


@dataclass(frozen=True)
class CartView:
    customer_id: str
    revision: str | None
    items: tuple[CartLine, ...]
    total_cents: int
    currency: Literal["BRL"] = "BRL"


@dataclass(frozen=True)
class CheckoutResult:
    order: Order
    graph_status: Literal["pending", "done"]
    cart_status: Literal["pending", "done"]
    cache_status: Literal["pending", "done"]


@dataclass(frozen=True)
class Recommendation:
    book: Book
    score: float
    reason: Literal["similar_customers", "preferences"]


class CatalogService(Protocol):
    def search(self, query: CatalogQuery) -> CatalogPage: ...
    def get_book(self, book_id: str) -> Book: ...
    def list_categories(self) -> tuple[str, ...]: ...
    def invalidate_cache(self) -> None: ...


class SessionService(Protocol):
    def create_demo_session(self, customer_id: str) -> Session: ...
    def resolve(self, token: str) -> Customer: ...
    def logout(self, token: str) -> None: ...


class CartService(Protocol):
    def get_cart(self, session_token: str) -> CartView: ...
    def add_item(self, session_token: str, book_id: str, quantity: int = 1) -> CartView: ...
    def set_quantity(self, session_token: str, book_id: str, quantity: int) -> CartView: ...
    def remove_item(self, session_token: str, book_id: str) -> CartView: ...


class CheckoutService(Protocol):
    def checkout(self, session_token: str, request_id: str, expected_revision: str) -> CheckoutResult: ...
    def get_order(self, session_token: str, order_id: str) -> CheckoutResult: ...
    def retry_pending(self, limit: int = 100) -> int: ...


class RecommendationService(Protocol):
    def recommend(self, session_token: str, limit: int = 10) -> tuple[Recommendation, ...]: ...
    def submit_review(self, session_token: str, book_id: str, rating: int) -> Review: ...
