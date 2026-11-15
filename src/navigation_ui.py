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


def render_navigation(customer, *, container=None):
    """Draw the view selector (optionally inside ``container``) and gate private views."""
    with container if container is not None else st.container():
        destination = st.radio("Navegar", VIEWS, horizontal=True, key="navegacao", label_visibility="collapsed")
    if destination not in (OVERVIEW, CATALOG) and customer is None:
        st.info("Identifique um cliente para acessar esta tela.")
        st.button("Identificar cliente", key="abrir_identificacao", on_click=_open_identity, type="primary")
        return None
    return destination


def _open_identity():
    st.session_state["identificacao_aberta"] = True
