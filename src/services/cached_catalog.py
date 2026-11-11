"""Catalog cache-aside: hits bypass MongoDB queries, outages fall back to it."""

import hashlib
import json
from dataclasses import asdict

from pymongo.errors import PyMongoError

from src.domain.contracts import CatalogPage, ServiceUnavailableError
from src.services.catalog import MongoCatalogService, book_from_document, normalize_query, validate_book_id
from src.services.catalog_cache import CatalogInvalidator, RedisCatalogCache


def search_digest(query):
    normalized = normalize_query(query)
    canonical = json.dumps(asdict(normalized), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def page_to_json(page):
    return {"items": [book.to_document() for book in page.items], "total": page.total,
            "page": page.page, "page_size": page.page_size}


def page_from_json(value, query):
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise ValueError("Invalid cached page")
    if type(value.get("total")) is not int or value["total"] < 0:
        raise ValueError("Invalid cached total")
    if value.get("page") != query.page or value.get("page_size") != query.page_size:
        raise ValueError("Cached page does not match query")
    if len(value["items"]) > query.page_size or len(value["items"]) > value["total"]:
        raise ValueError("Invalid cached items")
    return CatalogPage(tuple(book_from_document(book) for book in value["items"]),
                       value["total"], query.page, query.page_size)


def categories_from_json(value):
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError("Invalid cached categories")
    return tuple(sorted(set(value)))


class CachedCatalogService:
    def __init__(self, backend, cache, state_collection):
        self.backend = backend
        self.cache = cache
        self.invalidator = CatalogInvalidator(state_collection, cache)
        self._redis_failed = False

    @classmethod
    def from_env(cls):
        backend = MongoCatalogService.from_env()
        return cls(backend, RedisCatalogCache.from_env(), backend.cache_state)

    def close(self):
        self.backend.close()
        if self.cache is not None:
            self.cache.close()

    def _read(self, key_for_generation, loader, encode, decode):
        if self.cache is None:
            return loader()
        generation = self.cache.generation()
        if generation is None:
            self._redis_failed = True
            return loader()
        if self._redis_failed:
            self.invalidator.flush()
            self._redis_failed = False
            generation = self.cache.generation()
            if generation is None:
                return loader()
        cached = self.cache.get_json(key_for_generation(generation))
        if cached is not None:
            try:
                return decode(cached)
            except (ValueError, TypeError, KeyError, ServiceUnavailableError):
                pass
        # Resume durable invalidations on misses before capturing the write generation.
        self.invalidator.flush()
        generation = self.cache.generation()
        if generation is None:
            self._redis_failed = True
        result = loader()
        if generation is not None:
            # Never recapture after reading MongoDB: invalidation may run during loader().
            self.cache.put_json(key_for_generation(generation), encode(result))
        return result

    def search(self, query):
        query = normalize_query(query)
        digest = search_digest(query)
        return self._read(lambda generation: f"{self.cache.namespace}:{generation}:search:{digest}",
                          lambda: self.backend.search(query), page_to_json, lambda value: page_from_json(value, query))

    def get_book(self, book_id):
        validate_book_id(book_id)
        def decode(value):
            book = book_from_document(value)
            if book.isbn != book_id:
                raise ValueError("Cached ISBN mismatch")
            return book
        return self._read(lambda generation: f"{self.cache.product_namespace}:{generation}:{book_id}",
                          lambda: self.backend.get_book(book_id), lambda book: book.to_document(), decode)

    def list_categories(self):
        return self._read(lambda generation: f"{self.cache.namespace}:{generation}:categories",
                          self.backend.list_categories, list, categories_from_json)

    def invalidate_cache(self):
        try:
            if not self.invalidator.invalidate():
                self._redis_failed = True
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível registrar a atualização do catálogo. Tente novamente.") from None
