import os
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except ImportError:
    st = None

from redis.exceptions import ConnectionError

from src.domain.contracts import CatalogPage, SessionExpiredError
if st is not None:
    from src.session_ui import TOKEN_KEY
from tests.test_catalog_ui import APP
from tests import test_sessions as fixtures
from tests.test_catalog_cache_integration import CacheFixture


@unittest.skipUnless(st is not None, "Install requirements-app.txt for UI tests")
class SessionUITests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.SessionTests()
        fixture.setUp()
        self.fixture = fixture
        self.service = fixture.service
        self.service.list_customers = MagicMock(return_value=(
            fixtures.example_customer(), fixtures.example_customer("client-b", "Bruno"),
        ))
        catalog = MagicMock()
        catalog.list_categories.return_value = ()
        catalog.search.return_value = CatalogPage((), 0, 1, 24)
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        for target, value in (
            ("src.services.sessions.RedisSessionService.from_env", self.service),
            ("src.services.cached_catalog.CachedCatalogService.from_env", catalog),
        ):
            factory = patch(target, return_value=value)
            factory.start()
            self.addCleanup(factory.stop)

    def button(self, app, label):
        return next(item for item in app.button if item.label == label)

    def identify(self, app, customer_id):
        app.checkbox(key="identificacao_aberta").check().run()
        self.button(app, "Buscar clientes").click().run()
        app.selectbox(key="cliente_selecionado").select(customer_id).run()
        app.button(key="entrar_cliente").click().run()
        self.assertFalse(app.exception)
        return app.session_state[TOKEN_KEY]

    def test_two_browser_sessions_switch_and_logout_are_isolated(self):
        first = AppTest.from_file(APP).run()
        second = AppTest.from_file(APP).run()
        alice = self.identify(first, "client-a")
        bruno = self.identify(second, "client-b")
        self.assertEqual(self.service.resolve(alice).customer_id, "client-a")
        self.assertEqual(self.service.resolve(bruno).customer_id, "client-b")
        self.assertTrue(any("Alice" in item.value for item in first.markdown))
        self.assertTrue(any("Bruno" in item.value for item in second.markdown))
        first.session_state["cart_snapshot"] = "old private cart"
        first.session_state["checkout_request_id"] = "old request"
        first.button(key="trocar_cliente").click().run()
        with self.assertRaises(SessionExpiredError):
            self.service.resolve(alice)
        self.assertNotIn("cart_snapshot", first.session_state)
        self.assertNotIn("checkout_request_id", first.session_state)
        self.button(first, "Buscar clientes").click().run()
        first.selectbox(key="cliente_selecionado").select("client-b").run()
        first.button(key="entrar_cliente").click().run()
        replacement = first.session_state[TOKEN_KEY]
        self.assertNotEqual(replacement, alice)
        first.button(key="sair_cliente").click().run()
        self.assertNotIn(TOKEN_KEY, first.session_state)
        with self.assertRaises(SessionExpiredError):
            self.service.resolve(replacement)
        second.run()
        self.assertEqual(second.session_state[TOKEN_KEY], bruno)
        self.assertFalse(first.exception or second.exception)

    def test_expired_session_clears_private_state_and_catalog_remains_public(self):
        app = AppTest.from_file(APP).run()
        self.identify(app, "client-a")
        app.session_state["cart_snapshot"] = "old cart"
        self.fixture.now += timedelta(hours=8)
        app.run()
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.assertNotIn("cart_snapshot", app.session_state)
        self.assertTrue(app.warning)
        self.assertTrue(app.button(key="atualizar_catalogo"))
        self.assertFalse(app.exception)

    def test_failed_redis_login_does_not_keep_identity_or_old_private_data(self):
        app = AppTest.from_file(APP).run()
        app.checkbox(key="identificacao_aberta").check().run()
        self.button(app, "Buscar clientes").click().run()
        app.session_state["cart_snapshot"] = "old cart"
        self.fixture.redis.set.side_effect = ConnectionError("secret")
        app.button(key="entrar_cliente").click().run()
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.assertNotIn("cart_snapshot", app.session_state)
        self.assertTrue(app.warning)
        self.assertFalse(app.exception)

    def test_failed_logout_clears_local_identity_and_reports_revocation_failure(self):
        app = AppTest.from_file(APP).run()
        self.identify(app, "client-a")
        self.fixture.redis.delete.side_effect = ConnectionError("secret")
        app.button(key="trocar_cliente").click().run()
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.assertFalse(app.session_state["identificacao_aberta"])
        self.assertIn("revogação", app.warning[0].value)
        self.assertFalse(app.exception)

    def test_redis_outage_during_resolution_does_not_reuse_identity(self):
        app = AppTest.from_file(APP).run()
        self.identify(app, "client-a")
        app.session_state["cart_snapshot"] = "old cart"
        self.fixture.redis.get.side_effect = ConnectionError("secret")
        app.run()
        self.assertNotIn(TOKEN_KEY, app.session_state)
        self.assertNotIn("cart_snapshot", app.session_state)
        self.assertTrue(app.warning)
        self.assertFalse(app.exception)


@unittest.skipUnless(st is not None and os.environ.get("SPACEBOOKS_INTEGRATION") == "1",
                     "Requires Streamlit, MongoDB and Redis")
class RealSessionUITests(CacheFixture):
    # Reuse the complete two-browser acceptance scenario with real persistence.
    button = SessionUITests.button
    identify = SessionUITests.identify
    test_two_browser_sessions_switch_and_logout_are_isolated = (
        SessionUITests.test_two_browser_sessions_switch_and_logout_are_isolated
    )

    def setUp(self):
        super().setUp()
        from src.services.sessions import RedisSessionService

        customers = self.collection.database[f"customers_{self.prefix.replace(':', '_')}"]
        self.addCleanup(customers.drop)
        customers.insert_many([fixtures.example_customer().to_document(),
                               fixtures.example_customer("client-b", "Bruno").to_document()])
        self.service = RedisSessionService(customers, self.redis, namespace=f"{self.prefix}session")
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        for target, value in (
            ("src.services.sessions.RedisSessionService.from_env", self.service),
            ("src.services.cached_catalog.CachedCatalogService.from_env", self.cached),
        ):
            factory = patch(target, return_value=value)
            factory.start()
            self.addCleanup(factory.stop)
