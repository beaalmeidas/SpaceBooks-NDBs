import os
import unittest
from unittest.mock import patch

try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except ImportError:
    st = None

from src.domain.contracts import ServiceUnavailableError
from src.services.cached_catalog import CachedCatalogService
from tests.test_catalog import example_book
from tests.test_catalog_ui import APP
from tests.test_checkout_integration import CheckoutFixture


@unittest.skipUnless(st is not None and os.environ.get("SPACEBOOKS_INTEGRATION") == "1",
                     "Requires Streamlit, replica set, Redis and Neo4j")
class CheckoutUITests(CheckoutFixture):
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
        ):
            factory = patch(target, return_value=service)
            factory.start()
            self.addCleanup(factory.stop)

    def app_with_review(self):
        self.carts.add_item(self.alice, example_book().isbn, 2)
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.checkbox(key="identificacao_aberta").check().run()
        next(button for button in app.button if button.label == "Buscar clientes").click().run()
        app.selectbox(key="cliente_selecionado").select("client-a").run()
        app.button(key="entrar_cliente").click().run()
        app.checkbox(key="carrinho_aberto").check().run()
        app.button(key="revisar_compra").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.db.orders.count_documents({}), 0)
        return app

    def assert_confirmation(self, app, request_id):
        self.assertFalse(app.exception)
        self.assertTrue(any(request_id in item.value for item in app.success))
        self.assertEqual(self.db.orders.count_documents({}), 1)
        self.assertEqual(self.db.books.find_one({"_id": example_book().isbn})["stock"], 5)

    def test_review_confirmation_order_number_and_empty_cart(self):
        app = self.app_with_review()
        request_id = app.session_state["checkout_request_id"]
        self.assertTrue(any("Valor a confirmar: R$ 24,68" in item.value for item in app.markdown))
        app.button(key="confirmar_compra").click().run()
        self.assert_confirmation(app, request_id)
        self.assertTrue(any("carrinho está vazio" in item.value for item in app.info))
        self.assertEqual(self.purchases(request_id), [2])
        app.button(key="consultar_tentativa").click().run()
        self.assert_confirmation(app, request_id)

    def test_changed_price_requires_new_review_before_confirmation(self):
        app = self.app_with_review()
        first_id = app.session_state["checkout_request_id"]
        self.db.books.update_one({"_id": example_book().isbn}, {"$set": {"price_cents": 1500}})
        app.button(key="confirmar_compra").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertEqual(self.db.orders.count_documents({}), 0)
        self.assertEqual(app.session_state["checkout_request_id"], first_id)
        app.button(key="revisar_compra").click().run()
        self.assertNotEqual(app.session_state["checkout_request_id"], first_id)
        app.button(key="confirmar_compra").click().run()
        self.assert_confirmation(app, app.session_state["checkout_request_id"])
        self.assertTrue(any("Total do pedido: R$ 30,00" in item.value for item in app.markdown))

    def test_partial_failure_keeps_confirmation_and_can_be_recovered(self):
        app = self.app_with_review()
        request_id = app.session_state["checkout_request_id"]
        with patch.object(self.graph, "record", side_effect=ServiceUnavailableError("offline")):
            app.button(key="confirmar_compra").click().run()
        self.assert_confirmation(app, request_id)
        self.assertTrue(any("pendentes" in item.value for item in app.warning))
        app.button(key="consultar_tentativa").click().run()
        self.assert_confirmation(app, request_id)
        self.assertEqual(self.purchases(request_id), [2])

    def test_lost_confirmation_reply_reuses_the_same_attempt(self):
        app = self.app_with_review()
        request_id = app.session_state["checkout_request_id"]
        checkout = self.service.checkout

        def lost_reply(*args):
            checkout(*args)
            raise ServiceUnavailableError("Resposta perdida; mantenha esta tentativa.")

        with patch.object(self.service, "checkout", side_effect=lost_reply):
            app.button(key="confirmar_compra").click().run()
        self.assertEqual(app.session_state["checkout_request_id"], request_id)
        self.assertEqual(self.db.orders.count_documents({}), 1)
        app.button(key="confirmar_compra").click().run()
        self.assert_confirmation(app, request_id)
        self.assertEqual(self.purchases(request_id), [2])
