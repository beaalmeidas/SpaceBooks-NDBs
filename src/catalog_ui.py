"""Catalog view with shared connections and Redis-backed query cache."""

import atexit
from html import escape

import streamlit as st

from src.domain.contracts import CatalogQuery, ServiceError
from src.services.cached_catalog import CachedCatalogService
from src.cart_ui import add_button
from src.recommendations_ui import render_review
from src.theme import cover_html, money, section_header, stars_html, stock_html
from src.ui_feedback import show_error


@st.cache_resource
def obter_catalogo():
    service = CachedCatalogService.from_env()
    atexit.register(service.close)
    return service


def mostrar_erro(erro):
    show_error(erro)
    st.button("Tentar novamente", key="tentar_catalogo")
    st.stop()


LIVROS_POR_PAGINA = 24
COLUNAS = 4


def _book_card(livro, identified):
    autores = "; ".join(livro.authors) or "Autor desconhecido"
    categorias_livro = "; ".join(livro.categories)
    categoria_html = (f'<span class="livro-categoria" title="{escape(categorias_livro, quote=True)}">'
                      f'{escape(categorias_livro)}</span>') if categorias_livro else '<span class="livro-categoria">Geral</span>'
    st.markdown(
        f'<div class="livro">{cover_html(livro)}{categoria_html}'
        f'<div class="livro-titulo" title="{escape(livro.title, quote=True)}">{escape(livro.title)}</div>'
        f'<div class="livro-autor" title="{escape(autores, quote=True)}">por {escape(autores)}</div>'
        f'{stars_html(livro.average_rating)}'
        f'<div class="livro-rodape"><span class="livro-preco">{money(livro.price_cents)}</span>'
        f'{stock_html(livro.stock)}</div></div>',
        unsafe_allow_html=True,
    )
    add_button(livro, identified)
    with st.expander("Ver detalhes"):
        st.write(livro.description or "Descrição indisponível.")
        if livro.published_year is not None:
            st.write(f"**Ano de publicação:** {livro.published_year}")
        if livro.num_pages is not None:
            st.write(f"**Páginas:** {livro.num_pages}")
        st.write(f"**ISBN:** {livro.isbn}")
        render_review(livro, identified)


def render_catalog(identified=False):
    titulo, acao = st.columns([4, 1], vertical_alignment="bottom")
    with titulo:
        section_header("Descubra sua próxima leitura",
                       "Busque por título ou autor, filtre por categoria e encontre histórias para a sua estante.",
                       eyebrow="Catálogo")

    try:
        catalogo = obter_catalogo()
        with acao.container(horizontal=True, horizontal_alignment="right"):
            if st.button("Atualizar catálogo", key="atualizar_catalogo", icon=":material/refresh:",
                         help="Descarta o cache do Redis e consulta o MongoDB novamente."):
                catalogo.invalidate_cache()
        categorias = catalogo.list_categories()
    except ServiceError as erro:
        mostrar_erro(erro)

    with st.container(key="filtros"):
        col_pesquisa, col_categoria, col_ordem = st.columns([3, 2, 2])
        with col_pesquisa:
            pesquisa = st.text_input("Pesquisar livros", placeholder="Título ou autor…", key="pesquisa_catalogo",
                                     icon=":material/search:")
        with col_categoria:
            opcoes_categorias = [None, *categorias]
            if st.session_state.get("categoria_catalogo") not in opcoes_categorias:
                st.session_state.categoria_catalogo = None
            categoria = st.selectbox("Explorar por categoria", opcoes_categorias,
                                     format_func=lambda valor: "Todas as categorias" if valor is None else valor,
                                     key="categoria_catalogo")
        with col_ordem:
            ordens = {"Título (A–Z)": "title_asc", "Menor preço": "price_asc", "Maior preço": "price_desc"}
            ordem = st.selectbox("Ordenar por", list(ordens), key="ordem_catalogo")

    filtros = (pesquisa.strip().casefold(), categoria, ordens[ordem])
    if st.session_state.get("filtro_anterior") != filtros:
        st.session_state.pagina_catalogo = 1
        st.session_state.filtro_anterior = filtros

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

    quantidade = f"{resultado.total:,}".replace(",", ".")
    rotulo = "livro encontrado" if resultado.total == 1 else "livros encontrados"
    aviso = "" if identified else '<span class="pilula pilula-azul">Identifique-se para comprar e avaliar</span>'
    st.markdown(f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 4px">'
                f'<span class="pilula pilula-verde">📚 {quantidade} {rotulo}</span>{aviso}</div>',
                unsafe_allow_html=True)
    if not resultado.items:
        st.info("Nenhum livro encontrado. Tente outra pesquisa ou categoria.")
    else:
        # Uma linha de colunas por vez mantém os cartões alinhados quando um detalhe é aberto.
        for inicio in range(0, len(resultado.items), COLUNAS):
            colunas = st.columns(COLUNAS)
            for coluna, livro in zip(colunas, resultado.items[inicio:inicio + COLUNAS]):
                with coluna, st.container(border=True):
                    _book_card(livro, identified)

    col_anterior, col_indicador, col_proxima = st.columns([1, 2, 1], vertical_alignment="center")
    with col_anterior:
        if st.button("← Anterior", disabled=pagina_atual == 1, width="stretch", key="pagina_anterior"):
            st.session_state.pagina_catalogo -= 1
            st.rerun()
    with col_indicador:
        st.markdown(f'<div class="indicador-pagina">Página <b>{pagina_atual}</b> de {total_paginas}</div>',
                    unsafe_allow_html=True)
    with col_proxima:
        if st.button("Próxima →", disabled=pagina_atual >= total_paginas, width="stretch", key="pagina_proxima"):
            st.session_state.pagina_catalogo += 1
            st.rerun()
