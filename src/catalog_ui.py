"""Catalog view with shared connections and Redis-backed query cache."""

import atexit
from html import escape
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from src.domain.contracts import CatalogQuery, ServiceError
from src.services.cached_catalog import CachedCatalogService
from src.book_card_ui import render_book_card

from src.services.covers import cover_image
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


def _choose_category(category):
    st.session_state.categoria_catalogo = category
    st.session_state.pagina_catalogo = 1


def render_catalog(identified=False, *, show_search=True):

    try:
        catalogo = obter_catalogo()
        categorias = catalogo.list_categories()
    except ServiceError as erro:
        mostrar_erro(erro)

    st.markdown('<div id="spacebooks-categorias"></div>', unsafe_allow_html=True)
    st.caption("EXPLORE POR GÊNERO")
    shortcuts = [(None, "Todos"), *[(value, label) for value, label in
        (("Fiction", "Ficção"), ("Computers", "Tecnologia"), ("History", "História"),
         ("Biography & Autobiography", "Biografias")) if value in categorias]]
    buttons = st.columns(len(shortcuts))
    for column, (value, label) in zip(buttons, shortcuts):
        with column:
            st.button(label, key=f"genero_{value}", width="stretch",
                      type="primary" if st.session_state.get("categoria_catalogo") == value else "secondary",
                      on_click=_choose_category, args=(value,))
    st.divider()
    st.markdown('<div id="spacebooks-catalogo" class="eyebrow">CURADORIA SPACEBOOKS</div><h2 class="section-title">Livros para começar uma nova jornada</h2><div class="section-copy">Uma seleção entre clássicos, descobertas e novos favoritos.</div>', unsafe_allow_html=True)
    if show_search:
        pesquisa = st.text_input("Pesquisar livros", placeholder="Busque por título ou autor…", key="pesquisa_catalogo")
    else:
        pesquisa = st.session_state.get("pesquisa_catalogo", "")
    col_categoria, col_ordem, col_atualizar = st.columns([2, 2, 1])
    with col_categoria:
        opcoes_categorias = [None, *categorias]
        if st.session_state.get("categoria_catalogo") not in opcoes_categorias:
            st.session_state.categoria_catalogo = None
        categoria = st.selectbox("Explorar por categoria", opcoes_categorias,
                                 format_func=lambda valor: "Todas" if valor is None else valor, key="categoria_catalogo")
    with col_ordem:
        ordens = {"Título (A–Z)": "title_asc", "Menor preço": "price_asc", "Maior preço": "price_desc"}
        ordem = st.selectbox("Ordenar por", list(ordens), key="ordem_catalogo")
    with col_atualizar:
        st.caption("CATÁLOGO")
        if st.button("Atualizar catálogo", key="atualizar_catalogo", width="stretch"):
            try:
                catalogo.invalidate_cache()
            except ServiceError as erro:
                mostrar_erro(erro)

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
    st.markdown(f'<div class="quantidade-livros">{quantidade_formatada} livros encontrados · Página {pagina_atual} de {total_paginas}</div>', unsafe_allow_html=True)
    if not resultado.items:
        st.info("Nenhum livro encontrado. Tente outra pesquisa ou categoria.")
    else:
        with ThreadPoolExecutor(max_workers=6) as pool:
            covers = list(pool.map(lambda book: cover_image(book.isbn, book.thumbnail), resultado.items))
        colunas = st.columns(4, gap='medium')
        for indice, livro in enumerate(resultado.items):
            with colunas[indice % 4]:
                render_book_card(livro, identified, covers[indice])

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
