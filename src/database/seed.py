"""Idempotent seed loading and verification, scoped to prepared identifiers."""

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from pymongo import ASCENDING, DESCENDING, TEXT, UpdateOne

from .clients import DatabaseError, operation


LABELS = ("Cliente", "Produto", "Categoria")
RELATIONSHIPS = {
    "PERTENCE_A": ("Produto", "Categoria"),
    "PREFERE": ("Cliente", "Categoria"),
}
BATCH_SIZE = 500


def batches(records):
    for start in range(0, len(records), BATCH_SIZE):
        yield records[start:start + BATCH_SIZE]


def read_jsonl(path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


@dataclass
class PreparedData:
    books: list
    customers: list
    nodes: dict
    relationships: dict

    @classmethod
    def read(cls, directory: Path):
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise ValueError("Unsupported prepared data schema; run src.prepare_data")
        books = read_jsonl(directory / "books.jsonl")
        customers = read_jsonl(directory / "customers.jsonl")
        graph = read_jsonl(directory / "graph.jsonl")
        for name, records in (("books", books), ("customers", customers)):
            if not records or len(records) != manifest[name]:
                raise ValueError(f"Prepared {name} count does not match manifest")
            ids = [record["_id"] for record in records]
            if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
                raise ValueError(f"Invalid or duplicate identifiers in {name}")
        if len(graph) != manifest["graph_records"]:
            raise ValueError("Prepared graph count does not match manifest")
        emails = [customer["email"].strip().lower() for customer in customers]
        if len(set(emails)) != len(emails):
            raise ValueError("Duplicate normalized customer e-mails")
        nodes, relationships = defaultdict(list), defaultdict(list)
        seen_nodes, seen_edges = set(), set()
        for record in graph:
            if record["type"] == "node":
                label, identifier = record["label"], record["id"]
                if label not in LABELS or not isinstance(identifier, str) or not identifier:
                    raise ValueError("Unsupported graph node")
                identity = (label, identifier)
                if identity in seen_nodes or "id" in record["properties"]:
                    raise ValueError("Duplicate graph node or reserved id property")
                seen_nodes.add(identity)
                nodes[label].append(record)
            elif record["type"] == "relationship":
                kind = record["relationship"]
                if kind not in RELATIONSHIPS:
                    raise ValueError("Unsupported seed relationship")
                source, target = record["source"], record["target"]
                if (source["label"], target["label"]) != RELATIONSHIPS[kind]:
                    raise ValueError("Invalid relationship endpoint labels")
                identity = (kind, source["id"], target["id"])
                if identity in seen_edges:
                    raise ValueError("Duplicate seed relationship")
                seen_edges.add(identity)
                relationships[kind].append(record)
            else:
                raise ValueError("Unsupported graph record")
        expected_products = {("Produto", book["_id"]) for book in books}
        expected_customers = {("Cliente", customer["_id"]) for customer in customers}
        if {node for node in seen_nodes if node[0] == "Produto"} != expected_products:
            raise ValueError("MongoDB and Neo4j product identifiers differ")
        if {node for node in seen_nodes if node[0] == "Cliente"} != expected_customers:
            raise ValueError("MongoDB and Neo4j customer identifiers differ")
        if len(nodes["Categoria"]) != manifest["categories"]:
            raise ValueError("Prepared category count does not match manifest")
        for records in relationships.values():
            for record in records:
                for endpoint in ("source", "target"):
                    node = record[endpoint]
                    if (node["label"], node["id"]) not in seen_nodes:
                        raise ValueError("Graph relationship references a missing node")
        return cls(books, customers, dict(nodes), dict(relationships))


def book_update(document):
    """Refresh bibliographic metadata, preserving live stock and prices."""
    metadata = {key: value for key, value in document.items() if key not in ("_id", "price_cents", "stock", "currency")}
    commerce = {key: document[key] for key in ("price_cents", "stock", "currency")}
    return {"$set": metadata, "$setOnInsert": commerce}


def create_schema(connections):
    with operation("MongoDB", "index creation"):
        db = connections.db
        db.books.create_index([("title", TEXT), ("authors", TEXT)], name="book_search")
        db.books.create_index([("categories", ASCENDING)], name="book_categories")
        db.books.create_index([("authors", ASCENDING)], name="book_authors")
        # Imported e-mails are normalized by the loader before indexing.
        db.customers.create_index([("email", ASCENDING)], unique=True, name="customer_email")
        if "orders" not in db.list_collection_names():
            db.create_collection("orders")
        db.orders.create_index([("customer_id", ASCENDING), ("created_at", DESCENDING)], name="customer_history")
    for label in LABELS:
        connections.query(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")


def load(connections, data: PreparedData):
    create_schema(connections)
    with operation("MongoDB", "seed upserts"):
        for batch in batches(data.books):
            connections.db.books.bulk_write([
                UpdateOne({"_id": document["_id"]}, book_update(document), upsert=True)
                for document in batch
            ], ordered=False)
        for batch in batches(data.customers):
            connections.db.customers.bulk_write([
                UpdateOne({"_id": document["_id"]}, {"$setOnInsert": {
                    **{key: value for key, value in document.items() if key != "_id"},
                    "email": document["email"].strip().lower(),
                }}, upsert=True)
                for document in batch
            ], ordered=False)
    # Load every node type before relationships, regardless of file order.
    for label, records in data.nodes.items():
        for batch in batches(records):
            connections.query(f"UNWIND $rows AS row MERGE (n:{label} {{id: row.id}}) SET n += row.properties", rows=batch)
    for kind, records in data.relationships.items():
        source, target = RELATIONSHIPS[kind]
        for batch in batches(records):
            connections.query(
                f"UNWIND $rows AS row MATCH (a:{source} {{id: row.source.id}}) "
                f"MATCH (b:{target} {{id: row.target.id}}) MERGE (a)-[r:{kind}]->(b) "
                "SET r += row.properties", rows=batch,
            )


def verify(connections, data: PreparedData) -> dict:
    report = {}
    with operation("MongoDB", "seed verification"):
        for name, records in (("books", data.books), ("customers", data.customers)):
            count = sum(connections.db[name].count_documents({"_id": {"$in": [row["_id"] for row in batch]}})
                        for batch in batches(records))
            if count != len(records):
                raise DatabaseError(f"MongoDB: missing seeded {name}")
            report[name] = count
    for label, records in data.nodes.items():
        count = sum(connections.query(
            f"MATCH (n:{label}) WHERE n.id IN $ids RETURN count(n) AS count",
            ids=[row["id"] for row in batch],
        )[0]["count"] for batch in batches(records))
        if count != len(records):
            raise DatabaseError(f"Neo4j: missing seeded {label} nodes")
        report[label] = count
    for kind, records in data.relationships.items():
        source, target = RELATIONSHIPS[kind]
        count = sum(connections.query(
            f"UNWIND $rows AS row MATCH (a:{source} {{id: row.source.id}}) "
            f"MATCH (b:{target} {{id: row.target.id}}) OPTIONAL MATCH (a)-[r:{kind}]->(b) "
            "WITH row, count(r) AS found RETURN sum(CASE WHEN found = 1 THEN 1 ELSE 0 END) AS count",
            rows=batch,
        )[0]["count"] for batch in batches(records))
        if count != len(records):
            raise DatabaseError(f"Neo4j: missing or duplicated {kind} relationships")
        report[kind] = count
    return report


def totals(connections) -> dict:
    """Global counts detect unexpected duplication after rerunning the loader."""
    with operation("MongoDB", "count"):
        result = {name: connections.db[name].count_documents({}) for name in ("books", "customers", "orders")}
    result["graph_nodes"] = connections.query("MATCH (n) RETURN count(n) AS count")[0]["count"]
    result["graph_relationships"] = connections.query("MATCH ()-[r]->() RETURN count(r) AS count")[0]["count"]
    return result
