
# Importação das bibliotecas

import streamlit as st

from src.session_ui import render_identity
from src.catalog_ui import render_catalog
from src.navigation_ui import OVERVIEW, CATALOG, CART, CHECKOUT, RECOMMENDATIONS, render_navigation
from src.cart_ui import render_cart
from src.recommendations_ui import render_recommendations


# Configuração da página
st.set_page_config(
    page_title="SpaceBooks | Catálogo",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# Estilização da página
st.markdown(
    """
<style>
    :root {
        --azul: #1749D7;
        --verde: #176440;
        --amarelo: #F4D85D;
        --fundo: #F7F8F4;
        --texto: #172B27;
        --cinza: #69746E;
    }

    .stApp {
        background-color: var(--fundo);
        color: var(--texto);
    }

    .block-container {
        max-width: 1250px;
        padding-top: 0.8rem;
        padding-bottom: 3rem;
    }

    /* Cabeçalho */
    .marca {
        text-align: center;
        padding: 18px 10px 20px;
    }

    .marca-detalhe {
        color: var(--azul);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2.5px;
        margin-bottom: 8px;
    }

    .marca-nome {
        color: var(--azul);
        font-family: 'Trebuchet MS', Arial, sans-serif;
        font-size: clamp(52px, 7vw, 86px);
        font-weight: 900;
        letter-spacing: -4px;
        line-height: 1.1;
        margin: 0;
    }

    .marca-ponto {
        color: var(--verde);
    }

    .marca-livros {
        font-size: 48px;
        vertical-align: middle;
        margin-left: 8px;
        letter-spacing: 0;
    }

    .marca-frase {
        color: #53635C;
        font-size: 16px;
        margin-top: 10px;
    }

    /* Banner principal */
    .banner {
        background: var(--amarelo);
        border-radius: 24px;
        padding: 28px 36px;
        margin-bottom: 20px;
        position: relative;
        overflow: hidden;
    }

    .banner::after {
        content: "";
        position: absolute;
        width: 150px;
        height: 150px;
        border: 22px solid rgba(23, 73, 215, 0.12);
        border-radius: 50%;
        right: -50px;
        top: -65px;
        pointer-events: none;
    }

    .banner-selo {
        display: inline-block;
        color: #FFFFFF;
        background: var(--azul);
        padding: 7px 13px;
        border-radius: 30px;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
        margin-bottom: 12px;
    }

    .banner-titulo {
        color: var(--texto);
        font-size: clamp(25px, 3vw, 34px);
        font-weight: 800;
        line-height: 1.2;
        max-width: 720px;
        margin-bottom: 8px;
    }

    .banner-texto {
        color: #34443E;
        font-size: 15px;
        line-height: 1.5;
        max-width: 650px;
    }

    /* Apresentação do catálogo */
    .catalogo-cabecalho {
        margin-top: 8px;
        margin-bottom: 12px;
    }

    .catalogo-titulo {
        color: var(--texto);
        font-size: 27px;
        font-weight: 800;
        letter-spacing: -1px;
        margin-bottom: 5px;
    }

    .catalogo-descricao {
        color: var(--cinza);
        font-size: 14px;
    }

    .quantidade-livros {
        display: inline-block;
        color: var(--verde);
        background: #DDEFE1;
        border-radius: 30px;
        padding: 7px 14px;
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 12px;
    }

    /* Campos de pesquisa */
    div[data-testid="stTextInput"] input {
        background: #FFFFFF;
        border: 1px solid #DBE1DB;
        border-radius: 14px;
        padding: 12px 16px;
    }

    div[data-testid="stTextInput"] input:focus {
        border-color: var(--azul);
        box-shadow: 0 0 0 1px var(--azul);
    }

    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background: #FFFFFF;
        border-color: #DBE1DB;
        border-radius: 14px;
    }

    /* Cards dos livros */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(
        .livro-titulo
    ) {
        background: #FFFFFF;
        border: 1px solid #E3E7E1;
        border-radius: 20px;
        box-shadow: 0 4px 16px rgba(23, 43, 39, 0.04);
        transition: transform 0.2s ease,
                    box-shadow 0.2s ease;
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(
        .livro-titulo
    ):hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 25px rgba(23, 43, 39, 0.10);
    }

    /* Capas dos livros */
    .capa-area {
        height: 250px;
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
        border-radius: 14px;
        background: #E1E9FC;
        margin-bottom: 12px;
        padding: 12px;
    }

    .capa-area img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
        border-radius: 4px;
    }

    /* Informações dos livros */
    .livro-titulo {
        height: 52px;
        line-height: 26px;
        font-size: 16px;
        font-weight: 700;
        color: var(--texto);
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }

    .livro-autor {
        height: 24px;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
        color: #69746E;
        font-size: 13px;
    }

    .livro-categoria {
        height: 24px;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
        color: #69746E;
        font-size: 13px;
    }

    .livro-avaliacao {
        height: 30px;
        font-size: 14px;
        color: #46534C;
    }

    .livro-preco {
        color: var(--azul);
        font-size: 25px;
        font-weight: 800;
        margin-top: 8px;
        margin-bottom: 4px;
    }

    .livro-estoque {
        color: var(--verde);
        font-size: 13px;
        margin-bottom: 12px;
    }

    /* Botões */
    .stButton > button {
        background: var(--azul);
        color: #FFFFFF;
        border: none;
        border-radius: 13px;
        font-weight: 700;
        padding: 10px 18px;
    }

    .stButton > button:hover:not(:disabled) {
        background: var(--verde);
        color: #FFFFFF;
        border: none;
    }

    .stButton > button:disabled {
        background: #E5E8E3;
        color: #919A93;
    }

    /* Paginação */
    .indicador-pagina {
        text-align: center;
        color: var(--verde);
        font-size: 14px;
        font-weight: 700;
        padding-top: 10px;
    }

    /* Rodapé */
    .rodape {
        text-align: center;
        border-top: 1px solid #DCE2DB;
        padding-top: 25px;
        margin-top: 50px;
        color: #69746E;
        font-size: 13px;
    }

    /* Adaptação para telas menores */
    @media (max-width: 768px) {
        .marca {
            padding: 18px 8px;
        }

        .marca-nome {
            font-size: 48px;
            letter-spacing: -2px;
        }

        .marca-livros {
            font-size: 30px;
        }

        .banner {
            padding: 25px 22px;
        }

        .catalogo-titulo {
            font-size: 24px;
        }
    }
</style>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
<div class="marca">
    <div class="marca-detalhe">✦ UM UNIVERSO DE LEITURAS ✦</div>
    <h1 class="marca-nome">spacebooks<span class="marca-ponto">.</span><span class="marca-livros">📚</span></h1>
    <div class="marca-frase">Histórias para todos os seus universos.</div>
</div>
<div class="banner">
    <div class="banner-selo">BEM-VINDO À SUA ESTANTE DIGITAL</div>
    <div class="banner-titulo">Grandes histórias começam com uma escolha.</div>
    <div class="banner-texto">Explore, descubra e encontre sua próxima leitura favorita.
        Um mundo de possibilidades está esperando por você.</div>
</div>

    """, unsafe_allow_html=True,
)

cliente_atual = render_identity()
destino = render_navigation(cliente_atual)
if destino == OVERVIEW:
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

st.markdown('<div class="rodape">SpaceBooks · Um universo inteiro entre páginas.</div>', unsafe_allow_html=True)
