"""Página de produto com detalhes e acesso ao checkout existente."""
from html import escape
import streamlit as st
from src.catalog_ui import obter_catalogo
from src.cart_ui import add_button, cart_service, money
from src.domain.contracts import ServiceError, SessionExpiredError
from src.navigation_ui import CATALOG, CHECKOUT, navigate
from src.recommendations_ui import render_review
from src.session_ui import TOKEN_KEY
from src.ui_feedback import show_error, clear_session
from src.services.covers import cover_image


def buy_now(isbn):
    try:
        token = st.session_state.get(TOKEN_KEY)
        if not token:
            raise SessionExpiredError('Identifique-se para comprar este livro.')
        cart_service().ensure_item(token, isbn)
    except SessionExpiredError as error:
        clear_session(error)
        return
    except ServiceError as error:
        st.session_state['produto_erro'] = str(error)
        return
    navigate(CHECKOUT)


def render_product(customer):
    st.button('← Voltar ao catálogo', key='voltar_catalogo', on_click=navigate, args=(CATALOG,))
    isbn = st.session_state.get('produto_isbn')
    if not isbn:
        st.info('Escolha um livro no catálogo para ver os detalhes.')
        return
    try:
        book = obter_catalogo().get_book(isbn)
    except ServiceError as error:
        show_error(error)
        return
    notice = st.session_state.pop('produto_erro', None)
    if notice:
        st.error(notice)
    st.caption('Catálogo / Detalhes do livro')
    image, content = st.columns([1, 1.35], gap='large')
    with image:
        source, high_resolution = cover_image(book.isbn, book.thumbnail)
        if source:
            cover = f'<img style="width:{320 if high_resolution else 128}px" src="{escape(source, quote=True)}" alt="Capa de {escape(book.title, quote=True)}">'
        else:
            cover = '<span>Capa original pendente de cadastro</span>'
        st.markdown(f'<div class="produto-capa">{cover}</div>', unsafe_allow_html=True)
        if not high_resolution:
            st.caption("A fonte ainda não disponibiliza uma capa em alta resolução para esta edição.")
    with content:
        st.caption(' · '.join(book.categories))
        st.title(book.title)
        if book.subtitle:
            st.write(book.subtitle)
        st.write('**Autor(es):** ' + '; '.join(book.authors))
        if book.average_rating is not None:
            st.caption(f'⭐ {book.average_rating:.1f}/5 · Média do catálogo')
        st.divider()
        st.markdown(f'<div class="produto-preco">{money(book.price_cents)}</div>', unsafe_allow_html=True)
        st.caption(f'{book.stock} unidades disponíveis' if book.stock else 'Indisponível no momento')
        if customer is None:
            st.info('Use “Identificar-se” no cabeçalho para adicionar ao carrinho ou comprar.')
        add, buy = st.columns(2)
        with add:
            add_button(book, customer is not None, key_prefix='produto_adicionar')
        with buy:
            st.button('Comprar agora', key='produto_comprar', type='primary', width='stretch',
                      disabled=customer is None or book.stock < 1, on_click=buy_now, args=(book.isbn,))
        st.caption('Comprar agora inclui o livro se necessário e abre o checkout do seu carrinho. Você revisa todos os itens antes de confirmar.')
        st.subheader('Sobre o livro')
        st.write(book.description or 'Descrição indisponível.')
    st.divider()
    info, reviews = st.columns(2, gap='large')
    with info:
        st.subheader('Informações do produto')
        st.write(f'**ISBN-13:** {book.isbn}')
        if book.isbn10:
            st.write(f'**ISBN-10:** {book.isbn10}')
        if book.published_year is not None:
            st.write(f'**Publicação:** {book.published_year}')
        if book.num_pages is not None:
            st.write(f'**Páginas:** {book.num_pages}')
    with reviews:
        st.subheader('Sua avaliação')
        render_review(book, customer is not None)
