import os
import unittest
from unittest.mock import patch

try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except ImportError:
    st = None

from neo4j.exceptions import ServiceUnavailable

from src.domain.contracts import SessionExpiredError
from src.services.cached_catalog import CachedCatalogService
from tests.test_catalog import example_book
from tests.test_catalog_ui import APP
from tests.test_recommendations_integration import RecommendationFixture
from tests.test_sessions import example_customer


@unittest.skipUnless(st is not None and os.environ.get("SPACEBOOKS_INTEGRATION") == "1",
                     "Requires Streamlit, MongoDB, Redis and Neo4j")
class RecommendationUITests(RecommendationFixture):
    def setUp(self):
        super().setUp()
        self.cached = CachedCatalogService(self.catalog, self.cache, self.db.catalog_cache_state)
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        for target, service in (
            ("src.services.sessions.RedisSessionService.from_env", self.sessions),
            ("src.services.cart.RedisCartService.from_env", self.carts),
            ("src.services.cached_catalog.CachedCatalogService.from_env", self.cached),
            ("src.services.recommendations.Neo4jRecommendationService.from_env", self.recommendations),
        ):
            factory = patch(target, return_value=service)
            factory.start()
            self.addCleanup(factory.stop)

    def app(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.checkbox(key="identificacao_aberta").check().run()
        next(button for button in app.button if button.label == "Buscar clientes").click().run()
        app.selectbox(key="cliente_selecionado").select("client-a").run()
        app.button(key="entrar_cliente").click().run()
        return app

    def test_cold_recommendations_current_prices_and_add_to_cart(self):
        app = self.app()
        app.checkbox(key="recomendacoes_abertas").check().run()
        isbn = example_book().isbn
        self.assertFalse(app.exception)
        self.assertTrue(any("Combina com suas categorias" in item.value for item in app.caption))
        self.db.books.update_one({"_id": isbn}, {"$set": {"price_cents": 1500}})
        app.button(key="atualizar_recomendacoes").click().run()
        self.assertTrue(any("R$ 15,00 · Estoque" in item.value for item in app.markdown))
        app.button(key=f"recomendado_adicionar_{isbn}").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("**Total: R$ 15,00**" == item.value for item in app.markdown))
        self.assertEqual(self.carts.get_cart(self.alice).items[0].quantity, 1)

    def test_rating_creation_edit_and_recommendation_change(self):
        common, candidate = example_book(0).isbn, example_book(1).isbn
        self.recommendations.submit_review(self.bruno, common, 5)
        self.recommendations.submit_review(self.bruno, candidate, 5)
        app = self.app()
        app.checkbox(key="recomendacoes_abertas").check().run()
        app.checkbox(key=f"avaliar_{common}").check().run()
        app.number_input(key=f"nota_{common}").set_value(5).run()
        app.button(key=f"salvar_avaliacao_{common}").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Sua nota: 5/5" in item.value for item in app.caption))
        self.assertTrue(any("gostos semelhantes" in item.value for item in app.caption))
        self.assertTrue(app.button(key=f"recomendado_adicionar_{candidate}"))
        app.number_input(key=f"nota_{common}").set_value(1).run()
        app.button(key=f"salvar_avaliacao_{common}").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Sua nota: 1/5" in item.value for item in app.caption))
        self.assertEqual(len(self.rows("client-a", 0)), 1)
        self.assertEqual(self.rows("client-a", 0)[0]["rating"], 1)
        app.button(key="sair_cliente").click().run()
        self.assertNotIn(f"nota_{common}", app.session_state)
        self.assertNotIn("recomendacoes_abertas", app.session_state)

    def test_graph_failure_shows_safe_error_without_blocking_catalog(self):
        app = self.app()
        with patch.object(self.recommendations, "_query", side_effect=ServiceUnavailable("private details")):
            app.checkbox(key="recomendacoes_abertas").check().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertNotIn("private", app.error[0].value)
        self.assertTrue(app.button(key="atualizar_catalogo"))

    def test_expired_session_clears_recommendation_and_rating_state(self):
        app = self.app()
        app.checkbox(key="recomendacoes_abertas").check().run()
        app.session_state["nota_private"] = 5
        with patch.object(self.sessions, "resolve", side_effect=[example_customer(), SessionExpiredError("Sessão expirada.")]):
            app.run()
        self.assertFalse(app.exception)
        self.assertNotIn("_spacebooks_session_token", app.session_state)
        self.assertNotIn("nota_private", app.session_state)
        self.assertTrue(app.warning)
