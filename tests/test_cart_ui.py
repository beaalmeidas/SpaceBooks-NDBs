import os
import unittest
from unittest.mock import patch

try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except ImportError:
    st = None

from src.domain.contracts import SessionExpiredError
from tests.test_cart_integration import CartFixture
from tests.test_catalog import example_book
from tests.test_catalog_ui import APP
from tests.test_sessions import example_customer


@unittest.skipUnless(st is not None and os.environ.get("SPACEBOOKS_INTEGRATION") == "1",
                     "Requires Streamlit, MongoDB and Redis")
class CartUITests(CartFixture):
    def setUp(self):
        super().setUp()
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        for target, service in (
            ("src.services.sessions.RedisSessionService.from_env", self.sessions),
            ("src.services.cart.RedisCartService.from_env", self.carts),
            ("src.services.cached_catalog.CachedCatalogService.from_env", self.cached),
        ):
            factory = patch(target, return_value=service)
            factory.start()
            self.addCleanup(factory.stop)

    def login(self, app, customer_id):
        app.checkbox(key="identificacao_aberta").check().run()
        next(button for button in app.button if button.label == "Buscar clientes").click().run()
        app.selectbox(key="cliente_selecionado").select(customer_id).run()
        app.button(key="entrar_cliente").click().run()
        self.assertFalse(app.exception)

    def assert_total(self, app, value):
        self.assertTrue(any(item.value == f"**Total: {value}**" for item in app.markdown),
                        [item.value for item in app.error])
        self.assertFalse(app.exception)

    def test_two_browsers_cart_controls_current_prices_and_independence(self):
        first = AppTest.from_file(APP, default_timeout=30).run()
        self.assertTrue(first.button(key=f"adicionar_{example_book().isbn}").disabled)
        second = AppTest.from_file(APP, default_timeout=30).run()
        self.login(first, "client-a")
        self.login(second, "client-b")
        isbn = example_book().isbn
        first.button(key=f"adicionar_{isbn}").click().run()
        self.assert_total(first, "R$ 12,34")
        first.number_input(key=f"carrinho_quantidade_{isbn}").set_value(2).run()
        first.button(key=f"salvar_{isbn}").click().run()
        self.assert_total(first, "R$ 24,68")
        second.button(key=f"adicionar_{isbn}").click().run()
        self.assert_total(second, "R$ 12,34")
        first.run()
        self.assert_total(first, "R$ 24,68")
        self.collection.update_one({"_id": isbn}, {"$set": {"price_cents": 999}})
        first.button(key="atualizar_carrinho").click().run()
        self.assert_total(first, "R$ 19,98")
        first.button(key=f"remover_{isbn}").click().run()
        self.assert_total(first, "R$ 0,00")
        self.assertTrue(any("carrinho está vazio" in item.value for item in first.info))
        second.run()
        self.assert_total(second, "R$ 9,99")

    def test_switching_customers_preserves_carts_without_reusing_quantity_drafts(self):
        isbn = example_book().isbn
        self.carts.add_item(self.alice, isbn, 2)
        self.carts.add_item(self.bruno, isbn, 3)
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.login(app, "client-a")
        app.checkbox(key="carrinho_aberto").check().run()
        app.number_input(key=f"carrinho_quantidade_{isbn}").set_value(5).run()
        app.button(key="trocar_cliente").click().run()
        self.login(app, "client-b")
        app.checkbox(key="carrinho_aberto").check().run()
        self.assertEqual(app.number_input(key=f"carrinho_quantidade_{isbn}").value, 3)
        self.assert_total(app, "R$ 37,02")
        app.button(key="sair_cliente").click().run()
        self.login(app, "client-a")
        app.checkbox(key="carrinho_aberto").check().run()
        self.assertEqual(app.number_input(key=f"carrinho_quantidade_{isbn}").value, 2)
        self.assert_total(app, "R$ 24,68")

    def test_deleted_book_removal_and_stock_warnings(self):
        isbn = example_book().isbn
        self.carts.add_item(self.alice, isbn, 2)
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.login(app, "client-a")
        app.checkbox(key="carrinho_aberto").check().run()
        self.collection.update_one({"_id": isbn}, {"$set": {"stock": 1}})
        app.run()
        self.assertTrue(any("Estoque atual: 1" in item.value for item in app.warning))
        self.collection.delete_one({"_id": isbn})
        app.run()
        self.assertTrue(any(isbn in item.value for item in app.error))
        app.text_input(key="remover_isbn").input(isbn)
        next(button for button in app.button if button.label == "Remover por ISBN").click().run()
        self.assert_total(app, "R$ 0,00")

    def test_session_expiring_between_identity_and_cart_clears_browser_state(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.login(app, "client-a")
        app.checkbox(key="carrinho_aberto").check().run()
        app.session_state["checkout_request_id"] = "private previous request"
        with patch.object(self.sessions, "resolve", side_effect=[example_customer(), SessionExpiredError("Sessão expirada.")]):
            app.run()
        self.assertFalse(app.exception)
        self.assertNotIn("_spacebooks_session_token", app.session_state)
        self.assertNotIn("checkout_request_id", app.session_state)
        self.assertTrue(any("Sessão expirada" in item.value for item in app.warning))
