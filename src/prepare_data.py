"""Prepare validated JSONL documents and graph records from the source CSVs."""

import argparse
import csv
import hashlib
import json
import tempfile
from contextlib import ExitStack
from datetime import date
from pathlib import Path

from .domain import Book, Customer
from .domain.models import parse_integer


ROOT = Path(__file__).resolve().parents[1]


def demo_commerce(isbn: str) -> tuple[int, int]:
    """Stable fictitious BRL prices (19.90–149.90) and stock (5–50)."""
    digest = hashlib.sha256(isbn.encode("ascii")).digest()
    return 1990 + int.from_bytes(digest[:4], "big") % 131 * 100, 5 + digest[4] % 46


def book_from_row(row: dict[str, str]) -> Book:
    price, stock = demo_commerce(row["isbn13"])
    pages = parse_integer(row["num_pages"], "num_pages")
    return Book(
        isbn=row["isbn13"], isbn10=row["isbn10"], title=row["title"],
        authors=tuple(dict.fromkeys(name.strip() for name in row["authors"].split(";") if name.strip())),
        categories=tuple(dict.fromkeys(name.strip() for name in row["categories"].split(";") if name.strip())),
        price_cents=price, stock=stock, subtitle=row["subtitle"] or None,
        description=row["description"] or None, thumbnail=row["thumbnail"] or None,
        published_year=parse_integer(row["published_year"], "published_year"),
        average_rating=float(row["average_rating"]),
        num_pages=None if pages == 0 else pages,
        ratings_count=parse_integer(row["ratings_count"], "ratings_count"),
    )


def customer_from_row(row: dict[str, str]) -> Customer:
    categories = json.loads(row["favorite_categories"])
    authors = json.loads(row["favorite_authors"])
    if not isinstance(categories, list) or not isinstance(authors, list):
        raise ValueError("customer preferences must be JSON arrays")
    return Customer(
        customer_id=row["user_id"], name=row["name"], email=row["email"],
        favorite_categories=tuple(categories), favorite_authors=tuple(authors),
        created_at=date.fromisoformat(row["created_at"]),
    )


def read_entities(path: Path, factory, id_field: str):
    entities = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        for index, row in enumerate(reader, start=2):
            try:
                entity = factory(row)
                identifier = getattr(entity, id_field)
                if identifier in seen:
                    raise ValueError(f"duplicate {id_field}: {identifier}")
                seen.add(identifier)
                entities.append(entity)
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError(f"{path.name}, record {index}: {error}") from error
    if not entities:
        raise ValueError(f"{path.name} has no records")
    return entities


def prepare(books_path: Path, users_path: Path, output_dir: Path) -> dict:
    books = read_entities(books_path, book_from_row, "isbn")
    customers = read_entities(users_path, customer_from_row, "customer_id")
    categories = {category for book in books for category in book.categories}
    authors = {author for book in books for author in book.authors}
    for customer in customers:
        if not set(customer.favorite_categories) <= categories:
            raise ValueError(f"{customer.customer_id}: unknown favorite category")
        if not set(customer.favorite_authors) <= authors:
            raise ValueError(f"{customer.customer_id}: unknown favorite author")

    # Stage complete files so validation failures never replace existing output.
    output_dir.mkdir(parents=True, exist_ok=True)
    graph_records = 0
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=output_dir) as temporary:
        stage = Path(temporary)
        with ExitStack() as stack:
            books_file = stack.enter_context((stage / "books.jsonl").open("w", encoding="utf-8", newline="\n"))
            users_file = stack.enter_context((stage / "customers.jsonl").open("w", encoding="utf-8", newline="\n"))
            graph_file = stack.enter_context((stage / "graph.jsonl").open("w", encoding="utf-8", newline="\n"))

            def write(handle, record):
                handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")

            def graph(record):
                nonlocal graph_records
                write(graph_file, record)
                graph_records += 1

            for category in sorted(categories):
                graph({"type": "node", "label": "Categoria", "id": category, "properties": {"nome": category}})
            for book in books:
                write(books_file, book.to_document())
                graph({"type": "node", "label": "Produto", "id": book.isbn, "properties": {"titulo": book.title}})
                for category in book.categories:
                    graph({"type": "relationship", "relationship": "PERTENCE_A",
                           "source": {"label": "Produto", "id": book.isbn},
                           "target": {"label": "Categoria", "id": category}, "properties": {}})
            for customer in customers:
                write(users_file, customer.to_document())
                graph({"type": "node", "label": "Cliente", "id": customer.customer_id,
                       "properties": {"nome": customer.name}})
                for category in customer.favorite_categories:
                    graph({"type": "relationship", "relationship": "PREFERE",
                           "source": {"label": "Cliente", "id": customer.customer_id},
                           "target": {"label": "Categoria", "id": category}, "properties": {}})

        manifest = {
            "schema_version": 1, "books": len(books), "customers": len(customers),
            "categories": len(categories), "graph_records": graph_records,
            "currency": "BRL", "demo_prices_and_stock": True,
            "price_rule": "1990 + (SHA256(ISBN13)[0:4] as big-endian integer % 131) * 100 cents",
            "stock_rule": "5 + SHA256(ISBN13)[4] % 46",
            "source_sha256": {
                "books": hashlib.sha256(books_path.read_bytes()).hexdigest(),
                "customers": hashlib.sha256(users_path.read_bytes()).hexdigest(),
            },
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for filename in ("books.jsonl", "customers.jsonl", "graph.jsonl", "manifest.json"):
            (stage / filename).replace(output_dir / filename)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--books", type=Path, default=ROOT / "data/books-processed.csv")
    parser.add_argument("--users", type=Path, default=ROOT / "data/users.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data/prepared")
    args = parser.parse_args()
    try:
        manifest = prepare(args.books, args.users, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Data preparation failed: {error}\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
