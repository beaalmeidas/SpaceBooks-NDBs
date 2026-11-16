"""Entrada Streamlit da SpaceBooks."""
import streamlit as st
from src.session_ui import render_identity
from src.catalog_ui import render_catalog
from src.navigation_ui import OVERVIEW, CATALOG, CATEGORIES, PRODUCT, CART, CHECKOUT, RECOMMENDATIONS, render_navigation, navigate
from src.cart_ui import render_cart
from src.bag_icon import render_bag_icon
from src.recommendations_ui import render_recommendations
from src.ui_theme import CSS
from src.ui_scroll import render_pending_scroll
from src.product_ui import render_product

st.set_page_config(page_title="SpaceBooks · Sua próxima história", page_icon="📚", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)

st.markdown('<div id="spacebooks-topo"></div>', unsafe_allow_html=True)
brand, menu, account, bag = st.columns([2, 4.3, 1.6, .55], gap="small", vertical_alignment="center")
with brand:
    st.markdown('<div class="logo">SpaceBooks<span>📚</span></div>', unsafe_allow_html=True)
with account:
    with st.popover("Identificar-se", icon=":material/person:", width="stretch"):
        cliente_atual = render_identity()
with bag:
    render_bag_icon(cliente_atual)
with menu:
    destino = render_navigation(cliente_atual)
st.divider()
add_notice = st.session_state.pop("carrinho_add_aviso", None)
if add_notice:
    if add_notice[0] == "success":
        st.toast(add_notice[1], icon="🛍️")
    else:
        st.error(add_notice[1])
if destino in (OVERVIEW, CATALOG, CATEGORIES):
    st.markdown('<div id="spacebooks-inicio"></div>', unsafe_allow_html=True)
    left, right = st.columns([1.25, 1], gap="large", vertical_alignment="center")
    with left:
        st.markdown('''<div class="eyebrow">✦ HISTÓRIAS PARA TODOS OS UNIVERSOS</div>
<h1 class="hero-title">Sua próxima grande<br>história começa <em>aqui.</em></h1>
<div class="hero-copy">Descubra livros que atravessam galáxias, épocas e ideias — escolhidos para encontrar um lugar especial na sua estante.</div>''', unsafe_allow_html=True)
        st.text_input("Buscar livros", placeholder="Busque por título ou autor…", key="pesquisa_catalogo", label_visibility="collapsed")
        st.markdown('<div class="hero-facts"><b>Novas descobertas</b> a cada página &nbsp; · &nbsp; <b>Recomendações</b> para você</div>', unsafe_allow_html=True)
    with right:
        st.markdown('''<div class="hero-art"><img src="https://images.unsplash.com/photo-1632900182533-c8ee9ba229f4?fit=crop&amp;q=88&amp;w=1000" alt="Livros e velas junto a uma janela"><div class="hero-note"><small>SEU PRÓXIMO CAPÍTULO</small>Leituras para viajar longe ↗</div></div>''', unsafe_allow_html=True)
    render_catalog(cliente_atual is not None, show_search=False)
    st.markdown('''<div class="recommend-banner"><div class="eyebrow">UMA ESCOLHA FEITA PARA VOCÊ</div><h2>Não sabe por onde começar?</h2><div class="section-copy">Encontre sua próxima leitura a partir das suas preferências e descobertas.</div></div>''', unsafe_allow_html=True)
    st.button("Encontrar meu próximo livro →", type="primary", on_click=navigate, args=(RECOMMENDATIONS,), key="descobrir_recomendacoes")
    if destino == OVERVIEW and cliente_atual is not None:
        render_cart(cliente_atual)
        render_recommendations(cliente_atual)
elif destino == PRODUCT:
    render_product(cliente_atual)
elif destino == CART:
    render_cart(cliente_atual, force_open=True, include_checkout=False)
elif destino == CHECKOUT:
    from src.review_ui import render_review_page
    render_review_page(cliente_atual)
elif destino == RECOMMENDATIONS:
    render_recommendations(cliente_atual, force_open=True)
st.markdown('<div class="footer">SpaceBooks &nbsp; · &nbsp; Um universo inteiro entre páginas.<br>Ambiente demonstrativo · Sem cobrança financeira.</div>', unsafe_allow_html=True)

render_pending_scroll()
