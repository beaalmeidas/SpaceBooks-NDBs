import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.database.clients import DatabaseError, operation
from src.database.config import Settings
from src.database.seed import PreparedData, book_update, verify_schema


class DatabaseUnitTests(unittest.TestCase):
    def schema_connections(self):
        connections = MagicMock()
        connections.db.list_collection_names.return_value = ["books", "customers", "orders"]
        collections = {name: MagicMock() for name in ("books", "customers", "orders")}
        connections.db.__getitem__.side_effect = collections.__getitem__
        indexes = {
            "books": [{"name": "book_search", "key": {"_fts": "text", "_ftsx": 1}, "weights": {"title": 1, "authors": 1}},
                      {"name": "book_categories", "key": {"categories": 1}},
                      {"name": "book_authors", "key": {"authors": 1}}],
            "customers": [{"name": "customer_email", "key": {"email": 1}, "unique": True}],
            "orders": [{"name": "customer_history", "key": {"customer_id": 1, "created_at": -1}}],
        }
        for collection, definitions in indexes.items():
            connections.db[collection].list_indexes.return_value = [{"name": "_id_", "key": {"_id": 1}}, *definitions]
        connections.query.return_value = [
            {"type": "UNIQUENESS", "entityType": "NODE", "labelsOrTypes": [label], "properties": ["id"]}
            for label in ("Cliente", "Produto", "Categoria")
        ]
        return connections

    def test_schema_verification_rejects_email_index_without_uniqueness(self):
        connections = self.schema_connections()
        connections.db["customers"].list_indexes.return_value[1]["unique"] = False
        with self.assertRaisesRegex(DatabaseError, "customer_email"):
            verify_schema(connections)
        connections.db["customers"].create_index.assert_not_called()

    def test_schema_verification_rejects_constraint_on_wrong_property(self):
        connections = self.schema_connections()
        connections.query.return_value[0]["properties"] = ["name"]
        with self.assertRaisesRegex(DatabaseError, "Cliente.id"):
            verify_schema(connections)

    def test_settings_encode_credentials_and_do_not_print_secrets(self):
        environment = {"MONGO_PASSWORD": "m@/secret", "REDIS_PASSWORD": "r@/secret", "NEO4J_PASSWORD": "n-secret"}
        with patch.dict(os.environ, environment, clear=True), patch("src.database.config.load_dotenv"):
            settings = Settings.from_env()
        self.assertIn("m%40%2Fsecret", settings.mongo_uri)
        self.assertIn("r%40%2Fsecret", settings.redis_url)
        self.assertNotIn("secret", repr(settings))

    def test_settings_respect_explicit_connection_urls(self):
        environment = {"MONGO_URI": "mongodb://custom:27017", "REDIS_URL": "redis://custom:6379/2",
                       "NEO4J_URI": "neo4j+s://example.com", "NEO4J_PASSWORD": "secret"}
        with patch.dict(os.environ, environment, clear=True), patch("src.database.config.load_dotenv"):
            settings = Settings.from_env()
        self.assertEqual(settings.mongo_uri, environment["MONGO_URI"])
        self.assertEqual(settings.redis_url, environment["REDIS_URL"])

    def test_driver_error_does_not_expose_connection_string(self):
        with self.assertRaises(DatabaseError) as caught:
            with operation("MongoDB", "connect"):
                raise RuntimeError("mongodb://user:secret@host")
        self.assertNotIn("secret", str(caught.exception))
        self.assertIn("MongoDB", str(caught.exception))

    def test_commerce_values_are_insert_only(self):
        update = book_update({"_id": "123", "title": "New title", "price_cents": 4990, "stock": 20, "currency": "BRL"})
        # Simulate applying the update to a book after a purchase/price change.
        existing = {"_id": "123", "title": "Old title", "stock": 2, "price_cents": 5990}
        existing.update(update["$set"])
        self.assertEqual(existing["stock"], 2)
        self.assertEqual(existing["price_cents"], 5990)
        self.assertEqual(existing["title"], "New title")
        self.assertEqual(update["$setOnInsert"]["stock"], 20)

    def write_prepared(self, root, graph):
        files = {
            "books": [{"_id": "ISBN"}],
            "customers": [{"_id": "U1", "email": "ana@example.com"}],
            "graph": graph,
        }
        for filename, records in files.items():
            (root / f"{filename}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
        (root / "manifest.json").write_text(json.dumps({
            "schema_version": 1, "books": 1, "customers": 1, "categories": 0, "graph_records": len(graph),
        }), encoding="utf-8")

    def test_preflight_rejects_mismatched_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_prepared(root, [
                {"type": "node", "label": "Produto", "id": "OTHER", "properties": {}},
                {"type": "node", "label": "Cliente", "id": "U1", "properties": {}},
            ])
            with self.assertRaisesRegex(ValueError, "product identifiers differ"):
                PreparedData.read(root)

    def test_preflight_rejects_dynamic_cypher_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_prepared(root, [{"type": "node", "label": "Unexpected", "id": "ISBN", "properties": {}}])
            with self.assertRaisesRegex(ValueError, "Unsupported graph node"):
                PreparedData.read(root)
