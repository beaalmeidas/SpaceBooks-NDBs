"""Live MongoDB catalog queries; result caching belongs to the next stage."""

import re
from dataclasses import fields, replace

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from src.database.config import MongoSettings
from src.domain.contracts import CatalogPage, CatalogQuery, NotFoundError, ServiceUnavailableError, ValidationError
from src.domain.models import Book


SORTS = {
    "title_asc": [("title", 1), ("_id", 1)],
    "price_asc": [("price_cents", 1), ("_id", 1)],
    "price_desc": [("price_cents", -1), ("_id", 1)],
}
BOOK_FIELDS = {item.name for item in fields(Book)} - {"isbn"}
BOOK_PROJECTION = {key: 1 for key in BOOK_FIELDS | {"_id"}}


def normalize_query(query: CatalogQuery) -> CatalogQuery:
    if not isinstance(query, CatalogQuery) or not isinstance(query.search, str):
        raise ValidationError("Pesquisa inválida.")
    if query.category is not None and (not isinstance(query.category, str) or not query.category.strip()):
        raise ValidationError("Categoria inválida.")
    if type(query.page) is not int or not 1 <= query.page <= 2_147_483_647:
        raise ValidationError("Página inválida.")
    if type(query.page_size) is not int or not 1 <= query.page_size <= 100:
        raise ValidationError("O tamanho da página deve estar entre 1 e 100.")
    if not isinstance(query.sort, str) or query.sort not in SORTS:
        raise ValidationError("Ordenação inválida.")
    return replace(query, search=query.search.strip().casefold())


def book_from_document(document: dict) -> Book:
    try:
        values = {key: document[key] for key in BOOK_FIELDS if key in document}
        for key in ("isbn10", "subtitle", "description", "thumbnail"):
            if values.get(key) is not None and not isinstance(values[key], str):
                raise ValueError("Expected an optional string")
        for key in ("authors", "categories"):
            if not isinstance(values.get(key), list):
                raise ValueError("Expected a list")
            values[key] = tuple(values[key])
        return Book(isbn=document["_id"], **values)
    except (KeyError, TypeError, ValueError):
        raise ServiceUnavailableError("O catálogo contém dados inválidos. Verifique o cadastro dos livros.") from None


def validate_book_id(book_id):
    if not isinstance(book_id, str) or len(book_id) != 13 or not book_id.isascii() or not book_id.isdigit():
        raise ValidationError("ISBN inválido.")


class MongoCatalogService:
    def __init__(self, collection, *, query_timeout_ms: int = 60000, client=None):
        self._collection = collection
        self._query_timeout_ms = query_timeout_ms
        self._client = client

    @classmethod
    def from_env(cls) -> "MongoCatalogService":
        client = None
        try:
            settings = MongoSettings.from_env()
            client = MongoClient(
                settings.mongo_uri, serverSelectionTimeoutMS=int(settings.timeout_seconds * 1000),
                connectTimeoutMS=int(settings.timeout_seconds * 1000),
                socketTimeoutMS=int(settings.timeout_seconds * 1000),
            )
            return cls(client[settings.mongo_database].books,
                       query_timeout_ms=int(settings.query_timeout_seconds * 1000), client=client)
        except (PyMongoError, ValueError, TypeError, OSError):
            if client is not None:
                client.close()
            raise ServiceUnavailableError("Não foi possível configurar o MongoDB. Confira a configuração local.") from None

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    @property
    def cache_state(self):
        return self._collection.database.catalog_cache_state

    def search(self, query: CatalogQuery) -> CatalogPage:
        query = normalize_query(query)
        filters = {}
        if query.search:
            expression = {"$regex": re.escape(query.search), "$options": "i"}
            filters["$or"] = [{"title": expression}, {"authors": expression}]
        if query.category is not None:
            filters["categories"] = query.category
        try:
            total = self._collection.count_documents(filters, maxTimeMS=self._query_timeout_ms)
            with self._collection.find(filters, BOOK_PROJECTION).sort(SORTS[query.sort]).skip(
                (query.page - 1) * query.page_size
            ).limit(query.page_size).max_time_ms(self._query_timeout_ms) as cursor:
                items = tuple(book_from_document(document) for document in cursor)
            return CatalogPage(items, total, query.page, query.page_size)
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível consultar o catálogo. Tente novamente em instantes.") from None

    def get_book(self, book_id: str) -> Book:
        validate_book_id(book_id)
        try:
            document = self._collection.find_one({"_id": book_id}, BOOK_PROJECTION, max_time_ms=self._query_timeout_ms)
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível consultar o livro. Tente novamente em instantes.") from None
        if document is None:
            raise NotFoundError("Livro não encontrado.")
        return book_from_document(document)

    def list_categories(self) -> tuple[str, ...]:
        try:
            values = self._collection.distinct("categories", maxTimeMS=self._query_timeout_ms)
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível consultar as categorias. Tente novamente em instantes.") from None
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ServiceUnavailableError("O catálogo contém categorias inválidas.")
        return tuple(sorted(values))

    def invalidate_cache(self) -> None:
        """No-op: every query reads MongoDB directly in this stage."""
