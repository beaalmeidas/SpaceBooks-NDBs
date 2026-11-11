import os
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except ImportError:
    st = None

from src.domain.contracts import ServiceUnavailableError
from tests.test_catalog import example_book
from tests.test_catalog_cache_integration import CacheFixture


APP = str(Path(__file__).resolve().parents[1] / "src/catalogo.py")


@unittest.skipUnless(st is not None, "Install requirements-app.txt for UI tests")
class CatalogUIErrorTests(unittest.TestCase):
    def test_connection_error_is_shown_with_retry(self):
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        with patch("src.services.cached_catalog.CachedCatalogService.from_env", side_effect=ServiceUnavailableError("MongoDB indisponível.")):
            app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.error[0].value, "MongoDB indisponível.")
        self.assertEqual(app.button(key="tentar_catalogo").label, "Tentar novamente")


@unittest.skipUnless(st is not None and os.environ.get("SPACEBOOKS_INTEGRATION") == "1", "Requires Streamlit and running MongoDB")
class CatalogUIIntegrationTests(CacheFixture):
    def setUp(self):
        super().setUp()
        self.service = self.cached
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        factory = patch("src.services.cached_catalog.CachedCatalogService.from_env", return_value=self.service)
        factory.start()
        self.addCleanup(factory.stop)

    def test_page_updates_from_mongodb_and_filters(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.expander), 24)
        self.assertTrue(any("R$ 12,34" in element.value for element in app.markdown))
        self.collection.update_one({"_id": example_book().isbn}, {"$set": {"price_cents": 4321, "stock": 2}})
        app.button(key="atualizar_catalogo").click().run()
        self.assertTrue(any("R$ 43,21" in element.value for element in app.markdown))
        self.assertTrue(any("2 unidades disponíveis" in element.value for element in app.markdown))
        app.button(key="pagina_proxima").click().run()
        self.assertEqual(len(app.expander), 6)
        app.text_input(key="pesquisa_catalogo").input("no such book").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        self.assertTrue(app.button(key="pagina_proxima").disabled)
        app.text_input(key="pesquisa_catalogo").input("").run()
        app.selectbox(key="categoria_catalogo").select("Science").run()
        self.assertEqual(len(app.expander), 10)

    def test_page_clamps_when_catalog_shrinks(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.button(key="pagina_proxima").click().run()
        self.collection.delete_many({"_id": {"$in": [example_book(index).isbn for index in range(10)]}})
        app.button(key="atualizar_catalogo").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["pagina_catalogo"], 1)
        self.assertEqual(len(app.expander), 20)
