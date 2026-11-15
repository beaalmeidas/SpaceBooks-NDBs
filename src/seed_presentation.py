"""Add fictional presentation signals to existing customers, preserving their data."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from neo4j import unit_of_work
from neo4j.exceptions import DriverError, Neo4jError
from pymongo.errors import PyMongoError

from src.domain.contracts import ServiceError, ValidationError
from src.services.recommendations import Neo4jRecommendationService


DATA_FILE = Path(__file__).resolve().parents[1] / "data/presentation-existing.json"
DATASET = "presentation-existing-v1"


def load_presentation(service, path=DATA_FILE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data["dataset"] != DATASET:
        raise ValidationError("Conjunto de apresentação desconhecido.")
    customers = {}
    cold = []
    for row in data["customers"]:
        identifier = row["id"]
        if not isinstance(identifier, str) or not identifier or identifier in customers:
            raise ValidationError("IDs de clientes inválidos ou duplicados.")
        document = service.db.customers.find_one({"_id": identifier})
        if document is None:
            raise ValidationError(f"Cliente já cadastrado não encontrado: {identifier}.")
        customers[identifier] = document
        if type(row.get("without_history", False)) is not bool:
            raise ValidationError("A indicação de cliente sem histórico deve ser booleana.")
        if row.get("without_history"):
            if service.db.orders.count_documents({"customer_id": identifier, "status": "confirmed"}):
                raise ValidationError(f"O cliente {identifier} já possui pedidos; seu histórico foi preservado.")
            cold.append(service._graph_id(identifier))
    books = {}
    purchases, reviews = [], []
    for kind, destination in (("purchases", purchases), ("reviews", reviews)):
        seen = set()
        for row in data[kind]:
            pair = (row["customer"], row["book"])
            if pair[0] not in customers or pair in seen or service._graph_id(pair[0]) in cold:
                raise ValidationError("Referência duplicada/inválida ou sinal atribuído ao cliente sem histórico.")
            seen.add(pair)
            if pair[1] not in books:
                books[pair[1]] = service.catalog.get_book(pair[1])
            book = books[pair[1]]
            item = {"customer": service._graph_id(pair[0]), "book": service._graph_id(book.isbn)}
            if kind == "reviews":
                if type(row["rating"]) is not int or not 1 <= row["rating"] <= 5:
                    raise ValidationError("Avaliações fictícias devem ter notas inteiras de 1 a 5.")
                item["rating"] = row["rating"]
            else:
                item.update(order=f"DEMO-PRESENTATION-{pair[0]}-{book.isbn}", price=book.price_cents)
            destination.append(item)
    graph_customers = sorted(service._graph_id(identifier) for identifier in customers)
    graph_books = sorted(service._graph_id(identifier) for identifier in books)
    now = datetime.now(timezone.utc).isoformat()

    @unit_of_work(timeout=service.graph.timeout_seconds)
    def write(tx):
        def run(cypher, **params):
            return tx.run(cypher, **params)

        # Lock the same customer nodes used by normal purchases/reviews, in stable order.
        locked = list(run("""
            MATCH (c:Cliente) WHERE c.id IN $ids
            WITH c ORDER BY c.id
            SET c._presentation_lock = true
            RETURN c.id AS id
        """, ids=graph_customers))
        found = list(run("MATCH (p:Produto) WHERE p.id IN $ids RETURN p.id AS id", ids=graph_books))
        if len(locked) != len(graph_customers) or len(found) != len(graph_books):
            raise ValidationError("Clientes e livros devem estar carregados no Neo4j antes da apresentação.")
        history = run("""
            MATCH (c:Cliente)-[r:COMPROU|AVALIOU]->()
            WHERE c.id IN $ids RETURN count(r) AS count
        """, ids=cold).single()["count"]
        if history:
            raise ValidationError("O cliente reservado para início sem histórico já possui relações; nenhuma foi apagada.")
        created_purchases = created_reviews = 0
        for row in purchases:
            result = run("""
                MATCH (c:Cliente {id: $customer}), (p:Produto {id: $book})
                MERGE (c)-[r:COMPROU {pedido_id: $order}]->(p)
                ON CREATE SET r.quantidade = 1, r.unit_price_cents = $price,
                    r.created_at = $now, r.demo_dataset = $dataset, r.simulated = true
            """, **row, now=now, dataset=DATASET)
            created_purchases += result.consume().counters.relationships_created
        for row in reviews:
            result = run("""
                MATCH (c:Cliente {id: $customer}), (p:Produto {id: $book})
                MERGE (c)-[r:AVALIOU]->(p)
                ON CREATE SET r.nota = $rating, r.created_at = $now,
                    r.demo_dataset = $dataset, r.simulated = true
            """, **row, now=now, dataset=DATASET)
            created_reviews += result.consume().counters.relationships_created
        run("MATCH (c:Cliente) WHERE c.id IN $ids REMOVE c._presentation_lock", ids=graph_customers).consume()
        return created_purchases, created_reviews

    # All graph signals commit together; MongoDB is only read by this loader.
    with service.graph.driver.session(database=service.graph.database) as session:
        created_purchases, created_reviews = session.execute_write(write)
    return {"dataset": DATASET, "customers": [{"id": key, "name": value["name"]} for key, value in customers.items()],
            "purchases_created": created_purchases, "reviews_created": created_reviews,
            "purchases_preserved": len(purchases) - created_purchases,
            "reviews_preserved": len(reviews) - created_reviews}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_FILE)
    args = parser.parse_args()
    service = None
    try:
        service = Neo4jRecommendationService.from_env()
        print(json.dumps(load_presentation(service, args.data), ensure_ascii=False))
    except ServiceError as error:
        parser.exit(1, f"{error}\n")
    except (PyMongoError, Neo4jError, DriverError, OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "Não foi possível preparar a apresentação. Confira o arquivo e MongoDB/Neo4j.\n")
    finally:
        if service is not None:
            service.close()


if __name__ == "__main__":
    main()
