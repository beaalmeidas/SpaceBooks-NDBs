
# Importação das bibliotecas
from pathlib import Path
from html import escape

import pandas as pd
import streamlit as st

from src.prepare_data import demo_commerce


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


# Carregamento dos livros
@st.cache_data
def carregar_livros():
    caminho = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "books-processed.csv"
    )

    return pd.read_csv(
        caminho,
        dtype={"isbn13": str, "isbn10": str}
    )


# Cabeçalho centralizado
st.markdown(
    """
<div class="marca">
    <div class="marca-detalhe">✦ UM UNIVERSO DE LEITURAS ✦</div>
    <h1 class="marca-nome">spacebooks<span class="marca-ponto">.</span><span class="marca-livros">📚</span></h1>
    <div class="marca-frase">Histórias para todos os seus universos.</div>
</div>
    """,
    unsafe_allow_html=True
)


# Banner de boas-vindas
st.markdown(
    """
<div class="banner">
    <div class="banner-selo">BEM-VINDO À SUA ESTANTE DIGITAL</div>
    <div class="banner-titulo">Grandes histórias começam com uma escolha.</div>
    <div class="banner-texto">
        Explore, descubra e encontre sua próxima leitura favorita.
        Um mundo de possibilidades está esperando por você.
    </div>
</div>
    """,
    unsafe_allow_html=True
)


# Leitura e validação dos dados
try:
    livros = carregar_livros()
except (FileNotFoundError, pd.errors.ParserError) as erro:
    st.error(f"Não foi possível carregar o catálogo: {erro}")
    st.stop()


# Apresentação do catálogo
st.markdown(
    """
<div class="catalogo-cabecalho">
    <div class="catalogo-titulo">Descubra sua próxima leitura ✦</div>
    <div class="catalogo-descricao">
        Explore nossa coleção e encontre histórias
        que merecem um lugar na sua estante.
    </div>
</div>
    """,
    unsafe_allow_html=True
)


# Quantidade de livros
quantidade_formatada = f"{len(livros):,}".replace(",", ".")

st.markdown(
    f'<div class="quantidade-livros">'
    f'📚 {quantidade_formatada} livros no catálogo'
    f'</div>',
    unsafe_allow_html=True
)


# Campos de pesquisa e filtro por categoria
col_pesquisa, col_categoria = st.columns([2, 1])

with col_pesquisa:
    pesquisa = st.text_input(
        "Pesquisar livros",
        placeholder="Qual história você procura?",
    )

with col_categoria:
    categorias = sorted(
        livros["categories"].dropna().astype(str).unique()
    )

    categoria_selecionada = st.selectbox(
        "Explorar por categoria",
        ["Todas"] + categorias,
    )


# Aplicação dos filtros
livros_filtrados = livros.copy()

# Pesquisa por título ou autor
if pesquisa.strip():
    termo = pesquisa.strip()

    titulo = livros_filtrados["title"].fillna("").str.contains(
        termo,
        case=False,
        regex=False
    )

    autor = livros_filtrados["authors"].fillna("").str.contains(
        termo,
        case=False,
        regex=False
    )

    livros_filtrados = livros_filtrados[titulo | autor]

# Filtro por categoria
if categoria_selecionada != "Todas":
    livros_filtrados = livros_filtrados[
        livros_filtrados["categories"] == categoria_selecionada
    ]


# Quantidade de resultados
st.write(f"**{len(livros_filtrados)} livro(s) encontrado(s)**")


# Configuração da paginação
LIVROS_POR_PAGINA = 24

total_livros = len(livros_filtrados)

total_paginas = max(
    1,
    (total_livros + LIVROS_POR_PAGINA - 1) // LIVROS_POR_PAGINA
)


# Controle da página atual
if "pagina_catalogo" not in st.session_state:
    st.session_state.pagina_catalogo = 1

# Reinicia a paginação quando os filtros mudam
filtro_atual = (pesquisa.strip(), categoria_selecionada)

if st.session_state.get("filtro_anterior") != filtro_atual:
    st.session_state.pagina_catalogo = 1
    st.session_state.filtro_anterior = filtro_atual

# Impede páginas fora do intervalo
pagina_atual = min(
    st.session_state.pagina_catalogo,
    total_paginas
)

st.session_state.pagina_catalogo = pagina_atual


# Seleção dos livros da página
inicio = (pagina_atual - 1) * LIVROS_POR_PAGINA
fim = inicio + LIVROS_POR_PAGINA

livros_exibidos = livros_filtrados.iloc[inicio:fim]


# Exibição dos cards dos livros
if livros_exibidos.empty:
    st.warning("Nenhum livro encontrado. Tente outra pesquisa.")

else:
    colunas = st.columns(4)

    for indice, (_, livro) in enumerate(livros_exibidos.iterrows()):
        with colunas[indice % 4]:
            with st.container(border=True):

                # Capa do livro
                capa = livro.get("thumbnail")

                if pd.notna(capa) and str(capa).strip():
                    capa_segura = escape(str(capa), quote=True)

                    st.markdown(
                        f'''
<div class="capa-area">
    <img src="{capa_segura}" alt="Capa do livro">
</div>
                        ''',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        """
<div class="capa-area">
    📖 Capa indisponível
</div>
                        """,
                        unsafe_allow_html=True
                    )

                # Título, autor e categoria
                titulo_livro = escape(str(livro["title"]))
                autor_livro = escape(str(livro["authors"]))
                categoria_livro = escape(str(livro["categories"]))

                st.markdown(
                    f'<div class="livro-titulo" '
                    f'title="{escape(str(livro["title"]), quote=True)}">'
                    f'{titulo_livro}</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    f'<div class="livro-autor" '
                    f'title="{escape(str(livro["authors"]), quote=True)}">'
                    f'Autor(es): {autor_livro}</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    f'<div class="livro-categoria" '
                    f'title="{escape(str(livro["categories"]), quote=True)}">'
                    f'Categoria: {categoria_livro}</div>',
                    unsafe_allow_html=True
                )

                # Avaliação do livro
                avaliacao = livro.get("average_rating")

                if pd.notna(avaliacao):
                    texto_avaliacao = f"⭐ {float(avaliacao):.1f}/5"
                else:
                    texto_avaliacao = "Sem avaliação"

                st.markdown(
                    f'<div class="livro-avaliacao">'
                    f'{texto_avaliacao}</div>',
                    unsafe_allow_html=True
                )

                # Preço e estoque demonstrativos
                preco_centavos, estoque = demo_commerce(
                    str(livro["isbn13"])
                )

                preco_reais = preco_centavos / 100

                preco_formatado = (
                    f"R$ {preco_reais:,.2f}"
                    .replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )

                st.markdown(
                    f'<div class="livro-preco">'
                    f'{preco_formatado}</div>',
                    unsafe_allow_html=True
                )

                st.markdown(
                    f'<div class="livro-estoque">'
                    f'📦 {estoque} unidades disponíveis</div>',
                    unsafe_allow_html=True
                )

                # Detalhes do livro
                with st.expander("Ver detalhes"):

                    # Descrição
                    descricao = livro.get("description")

                    if pd.notna(descricao) and str(descricao).strip():
                        st.write(str(descricao))
                    else:
                        st.write("Descrição indisponível.")

                    # Ano de publicação
                    ano = livro.get("published_year")

                    if pd.notna(ano):
                        st.write(
                            f"**Ano de publicação:** {int(float(ano))}"
                        )

                    # Quantidade de páginas
                    paginas = livro.get("num_pages")

                    if pd.notna(paginas) and float(paginas) > 0:
                        st.write(
                            f"**Páginas:** {int(float(paginas))}"
                        )

                    # ISBN
                    st.write(f"**ISBN:** {livro['isbn13']}")


# Navegação entre páginas
st.divider()

col_anterior, col_indicador, col_proxima = st.columns([1, 2, 1])

# Botão anterior
with col_anterior:
    if st.button(
        "← Anterior",
        disabled=pagina_atual == 1,
        width="stretch",
    ):
        st.session_state.pagina_catalogo -= 1
        st.rerun()

# Indicador da página
with col_indicador:
    st.markdown(
        f'<div class="indicador-pagina">'
        f'Página {pagina_atual} de {total_paginas}'
        f'</div>',
        unsafe_allow_html=True
    )

# Botão próxima
with col_proxima:
    if st.button(
        "Próxima →",
        disabled=pagina_atual >= total_paginas,
        width="stretch",
    ):
        st.session_state.pagina_catalogo += 1
        st.rerun()


# Rodapé
st.markdown(
    """
<div class="rodape">
    SpaceBooks · Um universo inteiro entre páginas.
</div>
    """,
    unsafe_allow_html=True
)
