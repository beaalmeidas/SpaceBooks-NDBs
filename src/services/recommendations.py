"""Editable Neo4j ratings and recommendations with live MongoDB commerce data."""

from datetime import datetime, timezone

from neo4j import Query
from neo4j.exceptions import DriverError, Neo4jError
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from src.database.config import Settings
from src.domain.contracts import Recommendation, ServiceUnavailableError, ValidationError
from src.domain.models import Review
from src.services.catalog import BOOK_PROJECTION, MongoCatalogService, book_from_document, validate_book_id
from src.services.purchases_graph import PurchaseGraph
from src.services.sessions import RedisSessionService


HISTORY = """
MATCH (c:Cliente {id: $customer})
MATCH (c)-[r:COMPROU|AVALIOU]->(p:Produto)
RETURN p.id AS id, type(r) AS kind, r.nota AS rating
"""
SIMILAR = """
MATCH (peer:Cliente)-[signal:COMPROU|AVALIOU]->(common:Produto)
WHERE common.id IN $signals AND peer.id <> $customer
  AND (type(signal) = 'COMPROU' OR signal.nota IN [4, 5])
WITH DISTINCT peer
MATCH (peer)-[r:COMPROU|AVALIOU]->(p:Produto)
WHERE (type(r) = 'COMPROU' OR r.nota IN [4, 5]) AND NOT p.id IN $excluded
RETURN p.id AS id, count(DISTINCT peer) AS score
ORDER BY score DESC, id ASC
"""


class Neo4jRecommendationService:
    def __init__(self, db, sessions, graph, *, owned_resources=(), query_timeout_ms=60000):
        self.db, self.sessions, self.graph = db, sessions, graph
        self.catalog = MongoCatalogService(db.books, query_timeout_ms=query_timeout_ms)
        self.query_timeout_ms = query_timeout_ms
        self._owned_resources = owned_resources

    @classmethod
    def from_env(cls):
        resources = []
        try:
            settings = Settings.from_env()
            ms = int(settings.timeout_seconds * 1000)
            mongo = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=ms,
                                connectTimeoutMS=ms, socketTimeoutMS=ms)
            resources.append(mongo)
            redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1,
                                   socket_connect_timeout=1, retry=Retry(NoBackoff(), 0))
            resources.append(redis)
            graph = PurchaseGraph.from_settings(settings)
            resources.append(graph)
            db = mongo[settings.mongo_database]
            return cls(db, RedisSessionService(db.customers, redis), graph,
                       owned_resources=tuple(resources), query_timeout_ms=int(settings.query_timeout_seconds * 1000))
        except (ValueError, TypeError, OSError, PyMongoError, RedisError, Neo4jError, DriverError):
            for resource in reversed(resources):
                resource.close()
            raise ServiceUnavailableError("Não foi possível configurar avaliações e recomendações. Confira os bancos.") from None

    def close(self):
        for resource in reversed(self._owned_resources):
            resource.close()

    def _query(self, cypher, *, write=False, **parameters):
        records, _, _ = self.graph.driver.execute_query(
            Query(cypher, timeout=self.graph.timeout_seconds), parameters_=parameters,
            database_=self.graph.database, routing_="w" if write else "r")
        return records

    def _graph_id(self, identifier):
        return self.graph.id_prefix + identifier

    def _book_id(self, identifier):
        prefix = self.graph.id_prefix
        if not isinstance(identifier, str) or not identifier.startswith(prefix):
            return None
        isbn = identifier[len(prefix):]
        try:
            validate_book_id(isbn)
        except ValidationError:
            return None
        return isbn

    def get_review(self, session_token, book_id):
        customer = self.sessions.resolve(session_token)
        self.catalog.get_book(book_id)
        try:
            records = self._query("""
                MATCH (:Cliente {id: $customer})-[r:AVALIOU]->(:Produto {id: $book})
                RETURN r.nota AS rating, r.created_at AS created_at
            """, customer=self._graph_id(customer.customer_id), book=self._graph_id(book_id))
            if not records:
                return None
            if len(records) != 1:
                raise ValueError("Duplicate rating")
            return Review(customer.customer_id, book_id, records[0]["rating"],
                          datetime.fromisoformat(records[0]["created_at"].replace("Z", "+00:00")))
        except (Neo4jError, DriverError, ValueError, TypeError, KeyError, AttributeError):
            raise ServiceUnavailableError("Não foi possível consultar sua avaliação no Neo4j.") from None

    def submit_review(self, session_token, book_id, rating):
        customer = self.sessions.resolve(session_token)
        if type(rating) is not int or not 1 <= rating <= 5:
            raise ValidationError("A nota deve ser um número inteiro de 1 a 5.")
        book = self.catalog.get_book(book_id)
        review = Review(customer.customer_id, book_id, rating, datetime.now(timezone.utc))
        try:
            self._query("""
                MERGE (c:Cliente {id: $customer})
                ON CREATE SET c.nome = $name
                SET c._review_lock = true
                WITH c
                MERGE (p:Produto {id: $book})
                ON CREATE SET p.titulo = $title
                MERGE (c)-[r:AVALIOU]->(p)
                SET r.nota = $rating, r.created_at = $created_at
                REMOVE c._review_lock
            """, write=True, customer=self._graph_id(customer.customer_id), name=customer.name,
                book=self._graph_id(book_id), title=book.title, rating=rating,
                created_at=review.to_graph_record()["properties"]["created_at"])
            return review
        except (Neo4jError, DriverError):
            raise ServiceUnavailableError("Não foi possível salvar sua avaliação no Neo4j. Consulte-a antes de tentar novamente.") from None

    def _books(self, filters):
        try:
            with self.db.books.find(filters, BOOK_PROJECTION).max_time_ms(self.query_timeout_ms) as cursor:
                return tuple(book_from_document(document) for document in cursor)
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível consultar preço e disponibilidade das recomendações.") from None

    def recommend(self, session_token, limit=10):
        customer = self.sessions.resolve(session_token)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValidationError("A quantidade de recomendações deve estar entre 1 e 50.")
        try:
            # Confirmed MongoDB orders also exclude purchases whose graph
            # projection is pending. Graph history includes identified demo data.
            purchased = set(self.db.orders.distinct("items.book_id", {
                "customer_id": customer.customer_id, "status": "confirmed",
            }, maxTimeMS=self.query_timeout_ms))
        except PyMongoError:
            raise ServiceUnavailableError("Não foi possível consultar as compras para gerar recomendações.") from None
        try:
            history = self._query(HISTORY, customer=self._graph_id(customer.customer_id))
        except (Neo4jError, DriverError):
            raise ServiceUnavailableError("Neo4j indisponível. Não foi possível conferir o histórico para recomendar livros com segurança.") from None
        excluded, signals = set(purchased), set(purchased)
        for row in history:
            isbn = self._book_id(row["id"])
            if isbn is None:
                continue
            excluded.add(isbn)  # Do not suggest books this customer already rated.
            if row["kind"] == "COMPROU" or row["rating"] in (4, 5):
                signals.add(isbn)
        scores = {}
        if signals:
            try:
                candidates = self._query(SIMILAR, customer=self._graph_id(customer.customer_id),
                                         signals=[self._graph_id(isbn) for isbn in sorted(signals)],
                                         excluded=[self._graph_id(isbn) for isbn in sorted(excluded)])
                for row in candidates:
                    isbn = self._book_id(row["id"])
                    if isbn is not None and isbn not in excluded and type(row["score"]) is int and row["score"] > 0:
                        scores[isbn] = row["score"]
            except (Neo4jError, DriverError):
                # History is already known, so preferences can still exclude purchases.
                scores = {}
        similar = [Recommendation(book, float(scores[book.isbn]), "similar_customers") for book in self._books({
            "_id": {"$in": sorted(scores)}, "stock": {"$gt": 0},
        })] if scores else []
        similar.sort(key=lambda item: (-item.score, item.book.isbn))
        result = similar[:limit]
        if len(result) < limit and (customer.favorite_categories or customer.favorite_authors):
            excluded.update(item.book.isbn for item in result)
            preferences = []
            for book in self._books({"_id": {"$nin": sorted(excluded)}, "stock": {"$gt": 0}, "$or": [
                {"categories": {"$in": list(customer.favorite_categories)}},
                {"authors": {"$in": list(customer.favorite_authors)}},
            ]}):
                score = len(set(book.categories) & set(customer.favorite_categories)) + len(set(book.authors) & set(customer.favorite_authors))
                if score:
                    preferences.append(Recommendation(book, float(score), "preferences"))
            preferences.sort(key=lambda item: (-item.score, item.book.isbn))
            result.extend(preferences[:limit - len(result)])
        return tuple(result)
