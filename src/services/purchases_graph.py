"""Idempotent purchase projection, serialized by customer node write lock."""

from neo4j import GraphDatabase, Query


class PurchaseGraph:
    def __init__(self, driver, database="neo4j", *, id_prefix="", timeout_seconds=10):
        self.driver = driver
        self.database = database
        self.id_prefix = id_prefix
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls, settings):
        driver = GraphDatabase.driver(settings.neo4j_uri,
                                     auth=(settings.neo4j_username, settings.neo4j_password),
                                     connection_timeout=2, connection_acquisition_timeout=2,
                                     max_transaction_retry_time=0)
        return cls(driver, settings.neo4j_database, timeout_seconds=settings.query_timeout_seconds)

    def close(self):
        self.driver.close()

    def record(self, order):
        rows = [{"id": self.id_prefix + item.book_id, "title": item.title,
                 "quantity": item.quantity, "price": item.unit_price_cents} for item in order.items]
        self.driver.execute_query(Query("""
            MERGE (c:Cliente {id: $customer})
            SET c._checkout_lock = true
            WITH c
            UNWIND $rows AS row
            MERGE (p:Produto {id: row.id})
            ON CREATE SET p.titulo = row.title
            MERGE (c)-[r:COMPROU {pedido_id: $order_id}]->(p)
            SET r.quantidade = row.quantity, r.unit_price_cents = row.price,
                r.created_at = $created_at
            REMOVE c._checkout_lock
        """, timeout=self.timeout_seconds),
            customer=self.id_prefix + order.customer_id, rows=rows, order_id=order.order_id,
            created_at=order.created_at.isoformat(), database_=self.database)
