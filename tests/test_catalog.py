import os
import unittest
from unittest.mock import MagicMock, patch

from pymongo.errors import ServerSelectionTimeoutError

from src.database.config import MongoSettings
from src.domain.contracts import CatalogQuery, NotFoundError, ServiceUnavailableError, ValidationError
from src.domain.models import Book
from src.services.catalog import MongoCatalogService, book_from_document


def example_book(index=0):
    return Book(str(9780000000000 + index), "Alpha [Guide]" if index < 2 else f"Book {index:02d}",
                ("Jane Doe" if index % 2 == 0 else "John Smith",),
                ("Fiction" if index % 3 else "Science",), 1234 + index, 7)


class CatalogUnitTests(unittest.TestCase):
    def setUp(self):
        self.collection = MagicMock()
        self.service = MongoCatalogService(self.collection)

    def test_literal_filter_and_server_pagination(self):
        self.collection.count_documents.return_value = 30
        cursor = MagicMock()
        self.collection.find.return_value = cursor
        for method in ("sort", "skip", "limit", "max_time_ms"):
            getattr(cursor, method).return_value = cursor
        cursor.__enter__.return_value = cursor
        cursor.__iter__.return_value = iter([example_book().to_document()])
        result = self.service.search(CatalogQuery(search=" [GUIDE] ", category="Science", page=2, page_size=5))
        filters = self.collection.find.call_args.args[0]
        self.assertEqual(filters["$or"][0]["title"], {"$regex": r"\[guide\]", "$options": "i"})
        self.assertEqual(filters["categories"], "Science")
        cursor.sort.assert_called_once_with([("title", 1), ("_id", 1)])
        cursor.skip.assert_called_once_with(5)
        cursor.limit.assert_called_once_with(5)
        self.assertEqual(result.total, 30)
        self.assertEqual(result.items[0].price_cents, 1234)

    def test_invalid_queries_fail_before_accessing_database(self):
        for query in (CatalogQuery(page=0), CatalogQuery(page=True), CatalogQuery(page_size=101),
                      CatalogQuery(category=""), CatalogQuery(search={"$ne": ""}), CatalogQuery(sort="invalid")):
            with self.subTest(query=query), self.assertRaises(ValidationError):
                self.service.search(query)
        self.collection.find.assert_not_called()

    def test_unavailable_database_does_not_leak_credentials(self):
        self.collection.count_documents.side_effect = ServerSelectionTimeoutError("mongodb://user:secret@host")
        with self.assertRaises(ServiceUnavailableError) as caught:
            self.service.search(CatalogQuery())
        self.assertNotIn("secret", str(caught.exception))

    def test_missing_book_and_invalid_document(self):
        self.collection.find_one.return_value = None
        with self.assertRaises(NotFoundError):
            self.service.get_book(example_book().isbn)
        document = example_book().to_document()
        del document["stock"]
        with self.assertRaises(ServiceUnavailableError):
            book_from_document(document)

    def test_mongo_config_does_not_require_other_database_credentials(self):
        with patch.dict(os.environ, {"MONGO_URI": "mongodb://localhost:27017"}, clear=True), patch("src.database.config.load_dotenv"):
            settings = MongoSettings.from_env()
        self.assertEqual(settings.mongo_database, "spacebooks")
