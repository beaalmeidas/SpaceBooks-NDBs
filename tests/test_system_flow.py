"""Whole-application acceptance scenarios with isolated real persistence."""

import os
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except ImportError:
    st = None

from neo4j.exceptions import ServiceUnavailable
from redis.exceptions import ConnectionError

from src.domain.contracts import ServiceUnavailableError, SessionExpiredError
from src.services.cached_catalog import CachedCatalogService
from tests.test_catalog import example_book
from tests.test_catalog_ui import APP
from tests.test_recommendations_integration import RecommendationFixture
from tests.test_sessions import example_customer

if st is not None:
    from src.navigation_ui import OVERVIEW, CATALOG, CART, CHECKOUT, RECOMMENDATIONS


@unittest.skipUnless(st is not None and os.environ.get("SPACEBOOKS_INTEGRATION") == "1",
                     "Requires Streamlit, MongoDB replica set, Redis and Neo4j")
class SystemFlowTests(RecommendationFixture):
    def setUp(self):
        super().setUp()
        self.cached = CachedCatalogService(self.catalog, self.cache, self.db.catalog_cache_state)
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        for target, service in (
            ("src.services.sessions.RedisSessionService.from_env", self.sessions),
            ("src.services.cart.RedisCartService.from_env", self.carts),
            ("src.services.cached_catalog.CachedCatalogService.from_env", self.cached),
            ("src.services.checkout.MongoCheckoutService.from_env", self.service),
            ("src.services.recommendations.Neo4jRecommendationService.from_env", self.recommendations),
        ):
            factory = patch(target, return_value=service)
            factory.start()
            self.addCleanup(factory.stop)

    def login(self, app, customer="client-a"):
        app.checkbox(key="identificacao_aberta").check().run()
        next(button for button in app.button if button.label == "Buscar clientes").click().run()
        app.selectbox(key="cliente_selecionado").select(customer).run()
        app.button(key="entrar_cliente").click().run()
        self.assertFalse(app.exception)
        return app.session_state["_spacebooks_session_token"]

    def app(self, customer="client-a"):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.login(app, customer)
        return app

    def go(self, app, view):
        token = app.session_state.get("_spacebooks_session_token")
        app.radio(key="navegacao").set_value(view).run()
        self.assertFalse(app.exception)
        if token is not None:
            self.assertEqual(app.session_state["_spacebooks_session_token"], token)

    def add_and_review(self, app, quantity=1):
        self.go(app, CATALOG)
        isbn = example_book().isbn
        app.button(key=f"adicionar_{isbn}").click().run()
        self.assertEqual(app.radio(key="navegacao").value, CART)
        if quantity != 1:
            app.number_input(key=f"carrinho_quantidade_{isbn}").set_value(quantity).run()
            app.button(key=f"salvar_{isbn}").click().run()
        app.button(key="ir_checkout").click().run()
        self.assertEqual(app.radio(key="navegacao").value, CHECKOUT)
        app.button(key="revisar_compra").click().run()
        return app.session_state["checkout_request_id"]

    def assert_order(self, app, request_id, *, quantity=1, graph=True):
        self.assertFalse(app.exception)
        self.assertTrue(any(request_id in item.value for item in app.success))
        self.assertEqual(self.db.orders.count_documents({}), 1)
        document = self.db.orders.find_one({"_id": request_id})
        self.assertEqual(document["total_cents"], 1234 * quantity)
        self.assertEqual(document["items"][0]["unit_price_cents"], 1234)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 7 - quantity)
        self.assertEqual(self.redis.exists(*self.carts._keys("client-a")), 0)
        if graph:
            self.assertEqual(self.purchases(request_id), [quantity])
        return document

    def test_complete_purchase_navigation_three_banks_and_new_recommendations(self):
        app = self.app()
        self.cached.get_book(example_book().isbn)
        generation = self.cache.generation()
        request_id = self.add_and_review(app, quantity=2)
        self.go(app, RECOMMENDATIONS)
        self.assertTrue(app.button(key=f"recomendado_adicionar_{example_book().isbn}"))
        self.assertEqual(app.session_state["checkout_request_id"], request_id)
        self.go(app, CHECKOUT)
        app.button(key="confirmar_compra").click().run()
        document = self.assert_order(app, request_id, quantity=2)
        self.assertTrue(all(document["integration"][f"{stage}_status"] == "done" for stage in ("graph", "cart", "cache")))
        self.assertNotEqual(self.cache.generation(), generation)
        self.assertEqual(self.cached.get_book(example_book().isbn).stock, 5)
        self.go(app, RECOMMENDATIONS)
        self.assertFalse(any(button.key == f"recomendado_adicionar_{example_book().isbn}" for button in app.button))
        self.assertTrue(app.button(key=f"recomendado_adicionar_{example_book(3).isbn}"))
        self.go(app, CHECKOUT)
        app.button(key="voltar_catalogo").click().run()
        self.assertEqual(app.radio(key="navegacao").value, CATALOG)
        self.assertTrue(any("5 unidades disponíveis" in item.value for item in app.markdown))

    def test_insufficient_stock_is_rejected_then_quantity_can_be_corrected(self):
        app = self.app()
        first_attempt = self.add_and_review(app, quantity=2)
        self.db.books.update_one({"_id": example_book().isbn}, {"$set": {"stock": 1}})
        app.button(key="confirmar_compra").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Estoque insuficiente" in item.value for item in app.error))
        self.assertEqual(self.db.orders.count_documents({}), 0)
        self.assertEqual(self.redis.hget(self.carts._keys("client-a")[0], example_book().isbn), "2")
        app.button(key="editar_carrinho").click().run()
        app.number_input(key=f"carrinho_quantidade_{example_book().isbn}").set_value(1).run()
        app.button(key=f"salvar_{example_book().isbn}").click().run()
        app.button(key="ir_checkout").click().run()
        app.button(key="revisar_compra").click().run()
        self.assertNotEqual(app.session_state["checkout_request_id"], first_attempt)
        app.button(key="confirmar_compra").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.success)
        self.assertEqual(self.db.orders.count_documents({}), 1)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 0)

    def test_repeated_confirmation_after_lost_reply_and_navigation_is_idempotent(self):
        app = self.app()
        request_id = self.add_and_review(app)
        checkout = self.service.checkout

        def lost_reply(*args):
            checkout(*args)
            raise ServiceUnavailableError("Resposta perdida. Consulte a mesma tentativa.")

        with patch.object(self.service, "checkout", side_effect=lost_reply):
            app.button(key="confirmar_compra").click().run()
        self.assertTrue(app.error)
        self.go(app, CATALOG)
        self.go(app, CHECKOUT)
        self.assertEqual(app.session_state["checkout_request_id"], request_id)
        app.button(key="confirmar_compra").click().run()
        self.assert_order(app, request_id)
        app.button(key="consultar_tentativa").click().run()
        self.assert_order(app, request_id)

    def test_real_session_expiration_discards_checkout_state_but_preserves_cart(self):
        app = self.app()
        self.add_and_review(app)
        token = app.session_state["_spacebooks_session_token"]
        key = self.sessions._key(token)
        self.redis.pexpire(key, 30)
        deadline = time.monotonic() + 2
        while self.redis.exists(key) and time.monotonic() < deadline:
            time.sleep(0.01)
        app.radio(key="navegacao").set_value(RECOMMENDATIONS).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.warning)
        self.assertNotIn("_spacebooks_session_token", app.session_state)
        self.assertNotIn("checkout_request_id", app.session_state)
        self.assertEqual(self.db.orders.count_documents({}), 0)
        self.assertEqual(self.redis.hget(self.carts._keys("client-a")[0], example_book().isbn), "1")
        self.login(app)
        self.go(app, CART)
        self.assertEqual(app.number_input(key=f"carrinho_quantidade_{example_book().isbn}").value, 1)

    def test_two_customers_keep_independent_carts_while_navigating(self):
        first, second = self.app(), self.app("client-b")
        for app, quantity in ((first, 2), (second, 3)):
            self.go(app, CATALOG)
            app.button(key=f"adicionar_{example_book().isbn}").click().run()
            app.number_input(key=f"carrinho_quantidade_{example_book().isbn}").set_value(quantity).run()
            app.button(key=f"salvar_{example_book().isbn}").click().run()
            self.go(app, RECOMMENDATIONS)
            self.go(app, CART)
            self.assertEqual(app.number_input(key=f"carrinho_quantidade_{example_book().isbn}").value, quantity)
        self.assertEqual(self.carts.get_cart(self.alice).items[0].quantity, 2)
        self.assertEqual(self.carts.get_cart(self.bruno).items[0].quantity, 3)

    def test_catalog_uses_mongodb_during_redis_outage(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.radio(key="navegacao").set_value(CATALOG).run()
        self.db.books.update_one({"_id": example_book().isbn}, {"$set": {"price_cents": 1500}})
        with patch.object(self.redis, "get", side_effect=ConnectionError("offline")), \
                patch.object(self.redis, "set", side_effect=ConnectionError("offline")):
            app.run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertTrue(any("R$ 15,00" in item.value for item in app.markdown))

    def test_neo4j_outage_after_order_preserves_confirmation_and_recovers_once(self):
        app = self.app()
        request_id = self.add_and_review(app)
        with patch.object(self.graph.driver, "execute_query", side_effect=ServiceUnavailable("offline")):
            app.button(key="confirmar_compra").click().run()
        document = self.assert_order(app, request_id, graph=False)
        self.assertEqual(document["integration"]["graph_status"], "pending")
        self.assertTrue(any("pendentes" in item.value for item in app.warning))
        self.assertTrue(any("carrinho está vazio" in item.value for item in app.info))
        self.assertFalse(any(item.value == "**Total: R$ 12,34**" for item in app.markdown))
        app.button(key="consultar_tentativa").click().run()
        self.assert_order(app, request_id)
        self.assertEqual(self.db.orders.find_one({"_id": request_id})["integration"]["graph_status"], "done")

    def test_manual_catalog_refresh_invalidates_price_and_stock_cache(self):
        app = self.app()
        self.go(app, CATALOG)
        isbn = example_book().isbn
        before = self.cached.get_book(isbn)
        generation = self.cache.generation()
        self.db.books.update_one({"_id": isbn}, {"$set": {"price_cents": 4321, "stock": 2}})
        self.assertEqual(self.cached.get_book(isbn), before)
        app.button(key="atualizar_catalogo").click().run()
        self.assertFalse(app.exception)
        self.assertNotEqual(self.cache.generation(), generation)
        self.assertEqual((self.cached.get_book(isbn).price_cents, self.cached.get_book(isbn).stock), (4321, 2))
        self.assertTrue(any("R$ 43,21" in item.value for item in app.markdown))
        self.assertTrue(any("2 unidades disponíveis" in item.value for item in app.markdown))

    def test_protected_navigation_requires_identification(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        for view in (CART, CHECKOUT, RECOMMENDATIONS):
            app.radio(key="navegacao").set_value(view).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Identifique um cliente" in item.value for item in app.info))
            self.assertFalse(any(button.key == "confirmar_compra" for button in app.button))
        app.button(key="abrir_identificacao").click().run()
        self.assertTrue(app.checkbox(key="identificacao_aberta").value)

    def test_expiration_during_manual_order_lookup_uses_shared_session_reset(self):
        app = self.app()
        self.go(app, CHECKOUT)
        app.text_input(key="numero_pedido").input(str(uuid4()))
        with patch.object(self.sessions, "resolve", side_effect=[
            example_customer(), example_customer(), SessionExpiredError("Sessão expirada."),
        ]):
            next(button for button in app.button if button.label == "Consultar pedido").click().run()
        self.assertFalse(app.exception)
        self.assertNotIn("_spacebooks_session_token", app.session_state)
        self.assertNotIn("numero_pedido", app.session_state)
        self.assertTrue(any("Sessão expirada" in item.value for item in app.warning))
        self.assertEqual(self.db.orders.count_documents({}), 0)
