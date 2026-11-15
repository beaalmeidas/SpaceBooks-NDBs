
# Importação das bibliotecas

import streamlit as st

from src.session_ui import render_identity
from src.catalog_ui import render_catalog
from src.navigation_ui import OVERVIEW, CATALOG, CART, CHECKOUT, RECOMMENDATIONS, render_navigation
from src.cart_ui import render_cart
from src.recommendations_ui import render_recommendations
from src.theme import apply_theme, brand_html, render_footer, render_hero


# Configuração da página
st.set_page_config(
    page_title="SpaceBooks | Livraria",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()


# Barra superior: marca à esquerda e navegação à direita. A navegação é desenhada
# depois da identificação porque depende do cliente atual.
with st.container(key="topbar"):
    col_marca, col_navegacao = st.columns([1, 1.5], vertical_alignment="center")
    col_marca.markdown(brand_html(), unsafe_allow_html=True)

with st.container(key="identidade"):
    cliente_atual = render_identity()

destino = render_navigation(cliente_atual, container=col_navegacao)
if destino == OVERVIEW:
    render_hero()
    render_cart(cliente_atual)
    render_recommendations(cliente_atual)
    render_catalog(cliente_atual is not None)
elif destino == CATALOG:
    render_catalog(cliente_atual is not None)
elif destino == CART:
    render_cart(cliente_atual, force_open=True, include_checkout=False)
elif destino == CHECKOUT:
    render_cart(cliente_atual, force_open=True, checkout_only=True)
elif destino == RECOMMENDATIONS:
    render_recommendations(cliente_atual, force_open=True)

render_footer()
