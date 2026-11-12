"""Single application navigation; identity and checkout attempts live outside widgets."""

import streamlit as st


OVERVIEW = "Visão geral"
CATALOG = "Catálogo"
CART = "Carrinho"
CHECKOUT = "Checkout"
RECOMMENDATIONS = "Recomendações"
VIEWS = (OVERVIEW, CATALOG, CART, CHECKOUT, RECOMMENDATIONS)


def navigate(destination):
    st.session_state["navegacao"] = destination


def render_navigation(customer):
    destination = st.radio("Navegar", VIEWS, horizontal=True, key="navegacao")
    if destination not in (OVERVIEW, CATALOG) and customer is None:
        st.info("Identifique um cliente para acessar esta tela.")
        st.button("Identificar cliente", key="abrir_identificacao", on_click=_open_identity)
        return None
    return destination


def _open_identity():
    st.session_state["identificacao_aberta"] = True
