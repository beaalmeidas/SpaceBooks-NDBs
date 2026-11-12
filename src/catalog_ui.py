"""Catalog view with shared connections and Redis-backed query cache."""

import atexit
from html import escape

import streamlit as st

from src.domain.contracts import CatalogQuery, ServiceError
from src.services.cached_catalog import CachedCatalogService
from src.cart_ui import add_button
from src.recommendations_ui import render_review
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


def render_catalog(identified=False):
    st.markdown('''
    <div class="catalogo-cabecalho">
        <div class="catalogo-titulo">Descubra sua próxima leitura ✦</div>
        <div class="catalogo-descricao">Explore nossa coleção e encontre histórias
            que merecem um lugar na sua estante.</div>
    </div>
    ''', unsafe_allow_html=True)

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
                    add_button(livro, identified)
                    with st.expander("Ver detalhes"):
                        st.write(livro.description or "Descrição indisponível.")
                        if livro.published_year is not None:
                            st.write(f"**Ano de publicação:** {livro.published_year}")
                        if livro.num_pages is not None:
                            st.write(f"**Páginas:** {livro.num_pages}")
                        st.write(f"**ISBN:** {livro.isbn}")
                        render_review(livro, identified)

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
