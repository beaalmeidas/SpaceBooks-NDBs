import os
import unittest
from uuid import uuid4

from pymongo import MongoClient

from src.database.config import MongoSettings
from src.domain.contracts import CatalogQuery
from src.services.catalog import MongoCatalogService
from tests.test_catalog import example_book


class MongoCatalogFixture(unittest.TestCase):
    def setUp(self):
        settings = MongoSettings.from_env()
        self.client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)
        self.addCleanup(self.client.close)
        self.collection = self.client[settings.mongo_database][f"catalog_test_{uuid4().hex}"]
        self.addCleanup(self.collection.drop)
        self.collection.insert_many([example_book(index).to_document() for index in range(30)])
        self.service = MongoCatalogService(self.collection)


@unittest.skipUnless(os.environ.get("SPACEBOOKS_INTEGRATION") == "1", "Requires running MongoDB")
class CatalogIntegrationTests(MongoCatalogFixture):
    def test_title_author_and_combined_category_search(self):
        self.assertEqual(self.service.search(CatalogQuery(search="[GUIDE]")).total, 2)
        self.assertEqual(self.service.search(CatalogQuery(search=" jane DOE ")).total, 15)
        page = self.service.search(CatalogQuery(search="jane", category="Science"))
        self.assertEqual(page.total, 5)
        self.assertTrue(all(book.categories == ("Science",) for book in page.items))
        self.assertEqual(self.service.list_categories(), ("Fiction", "Science"))

    def test_stable_pagination_empty_results_and_price_sort(self):
        first = self.service.search(CatalogQuery(page_size=1))
        second = self.service.search(CatalogQuery(page=2, page_size=1))
        self.assertEqual(first.items[0].isbn, example_book(0).isbn)
        self.assertEqual(second.items[0].isbn, example_book(1).isbn)
        beyond = self.service.search(CatalogQuery(page=100))
        self.assertEqual(beyond.items, ())
        self.assertEqual(beyond.total, 30)
        self.assertEqual(self.service.search(CatalogQuery(search="not in this catalog")).total, 0)
        self.assertEqual(self.service.search(CatalogQuery(sort="price_desc", page_size=1)).items[0].isbn, example_book(29).isbn)

    def test_reads_current_price_and_stock_without_result_cache(self):
        identifier = example_book().isbn
        self.collection.update_one({"_id": identifier}, {"$set": {"price_cents": 4321, "stock": 2}})
        book = self.service.get_book(identifier)
        self.assertEqual((book.price_cents, book.stock), (4321, 2))
        self.assertEqual(self.service.search(CatalogQuery(page_size=1)).items[0], book)
