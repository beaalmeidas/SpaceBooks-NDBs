"""Card de livro compartilhado entre catálogo e recomendações."""
from html import escape
import streamlit as st
from src.cart_ui import add_button, money
from src.navigation_ui import open_product


def render_book_card(book, identified, cover, *, prefix='', reason=None):
    source, high_resolution = cover
    with st.container(border=True, key=f'book_card_{prefix}{book.isbn}'):
        if source:
            size = '' if high_resolution else 'style="max-width:128px;max-height:198px"'
            st.markdown(f'<div class="capa-area"><img {size} src="{escape(source, quote=True)}" alt="Capa de {escape(book.title, quote=True)}"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="capa-area">📖 Capa indisponível</div>', unsafe_allow_html=True)
        categories = '; '.join(book.categories)
        authors = '; '.join(book.authors)
        st.markdown(f'<div class="livro-categoria" title="{escape(categories, quote=True)}">{escape(categories)}</div><div class="livro-titulo" title="{escape(book.title, quote=True)}">{escape(book.title)}</div><div class="livro-autor" title="{escape(authors, quote=True)}">{escape(authors)}</div>', unsafe_allow_html=True)
        rating = f'⭐ {book.average_rating:.1f}/5' if book.average_rating is not None else 'Sem avaliação'
        st.markdown(f'<div class="livro-avaliacao">{rating}</div><div class="livro-preco"><small>Preço</small>{money(book.price_cents)}</div><div class="livro-estoque">{book.stock} unidades disponíveis</div>', unsafe_allow_html=True)
        if reason:
            st.markdown(f'<div class="recommendation-reason">✦ {escape(reason)}</div>', unsafe_allow_html=True)
        add_button(book, identified, key_prefix=f'{prefix}adicionar')
        st.button('Ver detalhes', key=f'{prefix}detalhes_{book.isbn}', width='stretch', on_click=open_product, args=(book.isbn,))
