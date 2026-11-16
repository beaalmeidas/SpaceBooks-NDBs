"""Single application navigation; identity and checkout attempts live outside widgets."""

import streamlit as st


OVERVIEW = "Visão geral"
CATALOG = "Catálogo"
CART = "Carrinho"
CHECKOUT = "Checkout"
RECOMMENDATIONS = "Recomendações"
CATEGORIES = "Categorias"
PRODUCT = "Detalhes do livro"
VIEWS = (OVERVIEW, CATALOG, CATEGORIES, RECOMMENDATIONS, CART, CHECKOUT)


def navigate(destination):
    st.session_state["navegacao"] = destination
    targets = {OVERVIEW: "spacebooks-inicio", CATALOG: "spacebooks-catalogo", CATEGORIES: "spacebooks-categorias"}
    st.session_state["_scroll_target"] = targets.get(destination, "spacebooks-topo")


def open_product(book_id):
    st.session_state["produto_isbn"] = book_id
    navigate(PRODUCT)


def render_navigation(customer):
    destination = st.session_state.get("navegacao", OVERVIEW)
    with st.container(key="header_nav"):
        columns = st.columns([.8, 1, 1.15, 1.65], gap="small")
        for column, view in zip(columns, (OVERVIEW, CATALOG, CATEGORIES, RECOMMENDATIONS)):
            with column:
                st.button("Início" if view == OVERVIEW else view,
                          key=f"nav_{view}", width="stretch",
                          type="primary" if destination == view else "secondary",
                          on_click=navigate, args=(view,))
    if destination not in (OVERVIEW, CATALOG, CATEGORIES, PRODUCT, CART) and customer is None:
        st.info("Identifique um cliente para acessar esta tela.")
        st.button("Identificar cliente", key="abrir_identificacao", on_click=_open_identity)
        return None
    return destination


def _open_identity():
    st.session_state["identificacao_aberta"] = True
