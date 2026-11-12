"""Load identified fictional profiles, without creating orders or changing stock."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from neo4j.exceptions import DriverError, Neo4jError
from pymongo.errors import PyMongoError

from src.domain.contracts import ServiceError, ValidationError
from src.domain.models import Customer, Order, OrderItem
from src.services.recommendations import Neo4jRecommendationService


DEMO_FILE = Path(__file__).resolve().parents[1] / "data/recommendation-demo.json"


def load_demo(service, path=DEMO_FILE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    dataset = data["dataset"]
    if dataset != "recommendations-v1":
        raise ValidationError("Conjunto de demonstração desconhecido.")
    customers = {}
    categories = set(service.db.books.distinct("categories"))
    authors = set(service.db.books.distinct("authors"))
    for row in data["customers"]:
        if not row["id"].startswith("DEMO_REC_") or row["id"] in customers:
            raise ValidationError("Os perfis fictícios devem usar IDs únicos DEMO_REC_.")
        customer = Customer(row["id"], row["name"], row["id"].lower() + "@example.com",
                            tuple(row["categories"]), tuple(row["authors"]), datetime.now(timezone.utc).date())
        if not set(customer.favorite_categories) <= categories or not set(customer.favorite_authors) <= authors:
            raise ValidationError("As preferências de demonstração precisam existir no catálogo carregado.")
        existing = service.db.customers.find_one({"_id": customer.customer_id})
        if existing is not None and existing.get("demo_dataset") != dataset:
            raise ValidationError("Um ID de demonstração já está em uso por outro cadastro.")
        customers[customer.customer_id] = customer
    books = {}
    for row in (*data["purchases"], *data["reviews"]):
        if row["customer"] not in customers:
            raise ValidationError("Referência de cliente fictício inválida.")
        books[row["book"]] = service.catalog.get_book(row["book"])
        if "rating" in row and (type(row["rating"]) is not int or not 1 <= row["rating"] <= 5):
            raise ValidationError("Nota fictícia inválida.")
    for customer in customers.values():
        document = customer.to_document()
        document["demo_dataset"] = dataset
        # Repeating the loader preserves subsequent user edits to demo profiles.
        service.db.customers.update_one({"_id": customer.customer_id}, {"$setOnInsert": document}, upsert=True)
        service._query("""
            MERGE (c:Cliente {id: $id}) SET c.nome = $name, c.demo_dataset = $dataset
        """, write=True, id=service._graph_id(customer.customer_id), name=customer.name, dataset=dataset)
    now = datetime.now(timezone.utc)
    for row in data["purchases"]:
        book = books[row["book"]]
        order = Order(f"DEMO-REC-{row['customer']}-{book.isbn}", row["customer"],
                      (OrderItem(book.isbn, book.title, 1, book.price_cents),), now)
        service.graph.record(order)
        service._query("""
            MATCH (:Cliente {id: $customer})-[r:COMPROU {pedido_id: $order}]->()
            SET r.demo_dataset = $dataset
        """, write=True, customer=service._graph_id(row["customer"]), order=order.order_id, dataset=dataset)
    for row in data["reviews"]:
        session = service.sessions.create_demo_session(row["customer"])
        try:
            service.submit_review(session.token, row["book"], row["rating"])
            service._query("""
                MATCH (:Cliente {id: $customer})-[r:AVALIOU]->(:Produto {id: $book})
                SET r.demo_dataset = $dataset
            """, write=True, customer=service._graph_id(row["customer"]), book=service._graph_id(row["book"]), dataset=dataset)
        finally:
            service.sessions.logout(session.token)
    return {"dataset": dataset, "customers": len(customers), "purchases": len(data["purchases"]), "reviews": len(data["reviews"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEMO_FILE)
    args = parser.parse_args()
    service = None
    try:
        service = Neo4jRecommendationService.from_env()
        print(json.dumps(load_demo(service, args.data), ensure_ascii=False))
    except ServiceError as error:
        parser.exit(1, f"{error}\n")
    except (PyMongoError, Neo4jError, DriverError, OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "Não foi possível carregar os perfis fictícios. Confira o arquivo e os três bancos.\n")
    finally:
        if service is not None:
            service.close()


if __name__ == "__main__":
    main()
