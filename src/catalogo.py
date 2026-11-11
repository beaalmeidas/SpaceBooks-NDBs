
# Importação das bibliotecas
import atexit
from html import escape

import streamlit as st

from src.domain.contracts import CatalogQuery, ServiceError
from src.services.cached_catalog import CachedCatalogService


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


# Clientes são compartilhados; resultados usam cache Redis com TTL.
@st.cache_resource
def obter_catalogo():
    service = CachedCatalogService.from_env()
    atexit.register(service.close)
    return service


def mostrar_erro(erro):
    st.error(str(erro))
    st.button("Tentar novamente", key="tentar_catalogo")
    st.stop()


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
<div class="catalogo-cabecalho">
    <div class="catalogo-titulo">Descubra sua próxima leitura ✦</div>
    <div class="catalogo-descricao">Explore nossa coleção e encontre histórias
        que merecem um lugar na sua estante.</div>
</div>
    """, unsafe_allow_html=True,
)

try:
    catalogo = obter_catalogo()
    if st.button("Atualizar catálogo", key="atualizar_catalogo"):
        catalogo.invalidate_cache()
    categorias = catalogo.list_categories()
except ServiceError as erro:
    mostrar_erro(erro)

col_pesquisa, col_categoria, col_ordem = st.columns([3, 2, 2])
with col_pesquisa:
    pesquisa = st.text_input("Pesquisar livros", placeholder="Qual história você procura?", key="pesquisa_catalogo")
with col_categoria:
    opcoes_categorias = [None, *categorias]
    if st.session_state.get("categoria_catalogo") not in opcoes_categorias:
        st.session_state.categoria_catalogo = None
    categoria = st.selectbox("Explorar por categoria", opcoes_categorias,
                             format_func=lambda valor: "Todas" if valor is None else valor, key="categoria_catalogo")
with col_ordem:
    ordens = {"Título (A–Z)": "title_asc", "Menor preço": "price_asc", "Maior preço": "price_desc"}
    ordem = st.selectbox("Ordenar por", list(ordens), key="ordem_catalogo")

filtros = (pesquisa.strip().casefold(), categoria, ordens[ordem])
if st.session_state.get("filtro_anterior") != filtros:
    st.session_state.pagina_catalogo = 1
    st.session_state.filtro_anterior = filtros

LIVROS_POR_PAGINA = 24
pagina_atual = max(1, st.session_state.get("pagina_catalogo", 1))
try:
    consulta = CatalogQuery(search=pesquisa, category=categoria, page=pagina_atual,
                            page_size=LIVROS_POR_PAGINA, sort=ordens[ordem])
    resultado = catalogo.search(consulta)
    total_paginas = max(1, (resultado.total + LIVROS_POR_PAGINA - 1) // LIVROS_POR_PAGINA)
    if pagina_atual > total_paginas:
        pagina_atual = total_paginas
        resultado = catalogo.search(CatalogQuery(search=pesquisa, category=categoria, page=pagina_atual,
                                                page_size=LIVROS_POR_PAGINA, sort=ordens[ordem]))
except ServiceError as erro:
    mostrar_erro(erro)
st.session_state.pagina_catalogo = pagina_atual

quantidade_formatada = f"{resultado.total:,}".replace(",", ".")
st.markdown(f'<div class="quantidade-livros">📚 {quantidade_formatada} livro(s) encontrado(s)</div>', unsafe_allow_html=True)
if not resultado.items:
    st.info("Nenhum livro encontrado. Tente outra pesquisa ou categoria.")
else:
    colunas = st.columns(4)
    for indice, livro in enumerate(resultado.items):
        with colunas[indice % 4]:
            with st.container(border=True):
                if livro.thumbnail:
                    st.markdown(f'<div class="capa-area"><img src="{escape(livro.thumbnail, quote=True)}" alt="Capa do livro"></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="capa-area">📖 Capa indisponível</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="livro-titulo" title="{escape(livro.title, quote=True)}">{escape(livro.title)}</div>', unsafe_allow_html=True)
                autores = "; ".join(livro.authors)
                categorias_livro = "; ".join(livro.categories)
                st.markdown(f'<div class="livro-autor" title="{escape(autores, quote=True)}">Autor(es): {escape(autores)}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="livro-categoria" title="{escape(categorias_livro, quote=True)}">Categoria: {escape(categorias_livro)}</div>', unsafe_allow_html=True)
                avaliacao = f"⭐ {livro.average_rating:.1f}/5" if livro.average_rating is not None else "Sem avaliação"
                st.markdown(f'<div class="livro-avaliacao">{avaliacao}</div>', unsafe_allow_html=True)
                reais = f"{livro.price_cents // 100:,}".replace(",", ".")
                preco = f"R$ {reais},{livro.price_cents % 100:02d}"
                st.markdown(f'<div class="livro-preco">{preco}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="livro-estoque">📦 {livro.stock} unidades disponíveis</div>', unsafe_allow_html=True)
                with st.expander("Ver detalhes"):
                    st.write(livro.description or "Descrição indisponível.")
                    if livro.published_year is not None:
                        st.write(f"**Ano de publicação:** {livro.published_year}")
                    if livro.num_pages is not None:
                        st.write(f"**Páginas:** {livro.num_pages}")
                    st.write(f"**ISBN:** {livro.isbn}")

st.divider()
col_anterior, col_indicador, col_proxima = st.columns([1, 2, 1])
with col_anterior:
    if st.button("← Anterior", disabled=pagina_atual == 1, width="stretch", key="pagina_anterior"):
        st.session_state.pagina_catalogo -= 1
        st.rerun()
with col_indicador:
    st.markdown(f'<div class="indicador-pagina">Página {pagina_atual} de {total_paginas}</div>', unsafe_allow_html=True)
with col_proxima:
    if st.button("Próxima →", disabled=pagina_atual >= total_paginas, width="stretch", key="pagina_proxima"):
        st.session_state.pagina_catalogo += 1
        st.rerun()
st.markdown('<div class="rodape">SpaceBooks · Um universo inteiro entre páginas.</div>', unsafe_allow_html=True)
