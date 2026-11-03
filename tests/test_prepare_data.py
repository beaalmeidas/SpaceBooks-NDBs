import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.prepare_data import prepare


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.books = self.root / "books.csv"
        self.users = self.root / "users.csv"
        self.output = self.root / "output"
        self.book = {
            "isbn13": "9780002005883", "isbn10": "0002005883", "title": "Gilead",
            "authors": "Marilynne Robinson;Other Author", "categories": "Fiction",
            "subtitle": "", "description": "Description", "thumbnail": "https://example.com/cover",
            "published_year": "2004.0", "average_rating": "3.85", "num_pages": "247.0", "ratings_count": "361.0",
        }
        self.user = {
            "user_id": "U1", "name": "Ana", "email": "ana@example.com",
            "favorite_categories": '["Fiction"]', "favorite_authors": '["Other Author"]',
            "created_at": "2025-03-07",
        }
        self.write_csv(self.books, [self.book])
        self.write_csv(self.users, [self.user])

    @staticmethod
    def write_csv(path, rows):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_reproducible_output_and_graph_references(self):
        manifest = prepare(self.books, self.users, self.output)
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        prepare(self.books, self.users, self.output)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.output.iterdir()})
        self.assertEqual(manifest["books"], 1)
        book = json.loads((self.output / "books.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(book["authors"], ["Marilynne Robinson", "Other Author"])
        self.assertEqual(book["isbn10"], "0002005883")
        self.assertTrue(1990 <= book["price_cents"] <= 14990)
        self.assertTrue(5 <= book["stock"] <= 50)
        graph = [json.loads(line) for line in (self.output / "graph.jsonl").read_text(encoding="utf-8").splitlines()]
        nodes = {(record["label"], record["id"]) for record in graph if record["type"] == "node"}
        for record in graph:
            if record["type"] == "relationship":
                for endpoint in ("source", "target"):
                    self.assertIn((record[endpoint]["label"], record[endpoint]["id"]), nodes)
                self.assertNotIn(record["relationship"], ("COMPROU", "AVALIOU"))

    def test_duplicate_book_fails_without_replacing_output(self):
        prepare(self.books, self.users, self.output)
        original = (self.output / "books.jsonl").read_bytes()
        self.write_csv(self.books, [self.book, self.book])
        with self.assertRaisesRegex(ValueError, "duplicate isbn"):
            prepare(self.books, self.users, self.output)
        self.assertEqual((self.output / "books.jsonl").read_bytes(), original)

    def test_unknown_preference_is_rejected(self):
        self.user["favorite_categories"] = '["Unknown"]'
        self.write_csv(self.users, [self.user])
        with self.assertRaisesRegex(ValueError, "unknown favorite category"):
            prepare(self.books, self.users, self.output)

    def test_preference_must_be_an_array(self):
        self.user["favorite_categories"] = '"Fiction"'
        self.write_csv(self.users, [self.user])
        with self.assertRaisesRegex(ValueError, "JSON arrays"):
            prepare(self.books, self.users, self.output)

    def test_zero_pages_is_unknown_without_discarding_book(self):
        self.book["num_pages"] = "0.0"
        self.write_csv(self.books, [self.book])
        manifest = prepare(self.books, self.users, self.output)
        book = json.loads((self.output / "books.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(manifest["books"], 1)
        self.assertIsNone(book["num_pages"])
