"""Opt-in live tests. Only the test's own UUID document is removed."""

import os
import unittest
from uuid import uuid4

from pymongo import UpdateOne

from src.database.clients import connect
from src.database.config import Settings
from src.database.seed import PreparedData, book_update, load, totals, verify
from src.prepare_data import ROOT


@unittest.skipUnless(os.environ.get("SPACEBOOKS_INTEGRATION") == "1", "Set SPACEBOOKS_INTEGRATION=1 with running databases")
class DatabaseIntegrationTests(unittest.TestCase):
    def test_real_connections_ttl_and_idempotent_seed(self):
        data = PreparedData.read(ROOT / "data/prepared")
        with connect(Settings.from_env()) as connections:
            self.assertEqual(connections.health()["redis"], "ok")
            load(connections, data)
            expected = verify(connections, data)
            before = totals(connections)
            load(connections, data)
            self.assertEqual(verify(connections, data), expected)
            self.assertEqual(totals(connections), before)

    def test_real_mongodb_upsert_preserves_live_price_and_stock(self):
        identifier = f"integration:{uuid4().hex}"
        with connect(Settings.from_env()) as connections:
            collection = connections.db.books
            document = {"_id": identifier, "title": "Fixture", "stock": 20, "price_cents": 4990, "currency": "BRL"}
            try:
                collection.bulk_write([UpdateOne({"_id": identifier}, book_update(document), upsert=True)])
                collection.update_one({"_id": identifier}, {"$set": {"stock": 2, "price_cents": 5990}})
                document["title"] = "Updated fixture"
                collection.bulk_write([UpdateOne({"_id": identifier}, book_update(document), upsert=True)])
                saved = collection.find_one({"_id": identifier})
                self.assertEqual(saved["stock"], 2)
                self.assertEqual(saved["price_cents"], 5990)
                self.assertEqual(saved["title"], "Updated fixture")
            finally:
                collection.delete_one({"_id": identifier})
