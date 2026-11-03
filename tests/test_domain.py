import unittest
from dataclasses import replace
from datetime import datetime, timezone

from src.domain import Book, Cart, Order, OrderItem, Review
from src.domain.models import parse_integer


NOW = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.book = Book("9780002005883", "Gilead", ("Marilynne Robinson",), ("Fiction",), 4990, 3)

    def test_checkout_uses_catalog_and_preserves_price_snapshot(self):
        cart = Cart("U0001", ((self.book.isbn, 2),))
        catalog = {self.book.isbn: self.book}
        order = Order.from_cart("P1", cart, catalog, NOW)
        catalog[self.book.isbn] = replace(self.book, price_cents=5990)
        self.assertEqual(order.total_cents, 9980)
        self.assertEqual(order.to_document()["items"][0]["unit_price_cents"], 4990)
        self.assertEqual(order.to_document()["created_at"], "2026-11-03T15:00:00Z")
        self.assertEqual(order.to_graph_records()[0]["properties"]["pedido_id"], "P1")

    def test_checkout_rejects_unknown_book_insufficient_stock_and_empty_cart(self):
        for cart, catalog in (
            (Cart("U1", (("unknown", 1),)), {}),
            (Cart("U1", ((self.book.isbn, 4),)), {self.book.isbn: self.book}),
            (Cart("U1"), {}),
        ):
            with self.subTest(cart=cart), self.assertRaises(ValueError):
                Order.from_cart("P1", cart, catalog, NOW)

    def test_invalid_money_and_quantities(self):
        for value in (-1, 0, 49.9, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(self.book, price_cents=value)
            with self.subTest(quantity=value), self.assertRaises(ValueError):
                Cart("U1", ((self.book.isbn, value),))

    def test_duplicate_items_and_naive_timestamps_are_rejected(self):
        with self.assertRaises(ValueError):
            Cart("U1", ((self.book.isbn, 1), (self.book.isbn, 2)))
        item = OrderItem(self.book.isbn, self.book.title, 1, 4990)
        with self.assertRaises(ValueError):
            Order("P1", "U1", (item, item), NOW)
        with self.assertRaises(ValueError):
            Order("P1", "U1", (item,), NOW.replace(tzinfo=None))

    def test_cart_contains_only_ids_and_quantities(self):
        cart = Cart("U1", ((self.book.isbn, 2),))
        self.assertEqual(cart.redis_key, "cart:U1")
        self.assertEqual(cart.to_redis_hash(), {self.book.isbn: "2"})
        self.assertEqual(cart.ttl_seconds, 86400)

    def test_review_requires_rating_between_one_and_five(self):
        review = Review("U1", self.book.isbn, 5, NOW)
        self.assertEqual(review.to_graph_record()["relationship"], "AVALIOU")
        for value in (0, 6, 3.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(review, rating=value)

    def test_numeric_csv_conversion_does_not_round(self):
        self.assertEqual(parse_integer("247.0", "pages"), 247)
        for value in ("247.5", "NaN", "Infinity", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_integer(value, "pages")
