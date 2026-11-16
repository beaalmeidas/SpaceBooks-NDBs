"""Streamlit recommendations and per-book editable ratings."""

import atexit
from concurrent.futures import ThreadPoolExecutor
from html import escape

import streamlit as st

from src.book_card_ui import render_book_card
from src.services.covers import cover_image
from src.navigation_ui import CATALOG, navigate
from src.domain.contracts import ServiceError, SessionExpiredError
from src.services.recommendations import Neo4jRecommendationService
from src.session_ui import TOKEN_KEY
from src.ui_feedback import clear_session, show_error, show_message


@st.cache_resource
def recommendation_service():
    service = Neo4jRecommendationService.from_env()
    atexit.register(service.close)
    return service


def _expired(error):
    clear_session(error, rerun=True)


def _save_review(isbn):
    try:
        recommendation_service().submit_review(st.session_state.get(TOKEN_KEY), isbn,
                                                st.session_state[f"nota_{isbn}"])
        st.session_state[f"avaliacao_aviso_{isbn}"] = ("success", "Avaliação salva. Você pode alterar a nota quando quiser.")
    except SessionExpiredError as error:
        clear_session(error)
    except ServiceError as error:
        st.session_state[f"avaliacao_aviso_{isbn}"] = ("error", str(error))


def render_review(book, identified):
    if not identified:
        st.caption("Identifique-se para avaliar este livro.")
        return
    if not st.checkbox("Minha avaliação", key=f"avaliar_{book.isbn}"):
        return
    notice = st.session_state.pop(f"avaliacao_aviso_{book.isbn}", None)
    if notice:
        show_message(*notice)
    try:
        previous = recommendation_service().get_review(st.session_state.get(TOKEN_KEY), book.isbn)
        if previous:
            st.caption(f"Sua nota: {previous.rating}/5 · Atualizada em {previous.created_at.strftime('%d/%m/%Y %H:%M')} UTC")
        else:
            st.caption("Você ainda não avaliou este livro. Não é necessário tê-lo comprado.")
        st.number_input("Nota de 1 a 5", min_value=1, max_value=5, step=1,
                        value=previous.rating if previous else 5, key=f"nota_{book.isbn}")
        st.button("Salvar avaliação", key=f"salvar_avaliacao_{book.isbn}", on_click=_save_review, args=(book.isbn,))
    except SessionExpiredError as error:
        _expired(error)
    except ServiceError as error:
        show_error(error)


def render_recommendations(customer, *, force_open=False):
    if customer is None or (not force_open and not st.checkbox("Recomendações para você", key="recomendacoes_abertas")):
        return
    st.markdown('<div class="eyebrow">SELEÇÃO PARA O SEU UNIVERSO</div><h1 class="section-title">Sua próxima história pode estar aqui.</h1>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-copy">Uma seleção para {escape(customer.name)}, inspirada nas suas preferências e em leitores com gostos parecidos.</div>', unsafe_allow_html=True)
    text, refresh = st.columns([3, 1], vertical_alignment='center')
    with text:
        st.caption('Descubra novos favoritos · Avalie livros para refinar as sugestões')
    with refresh:
        st.button('Atualizar recomendações', key='atualizar_recomendacoes', width='stretch')
    st.divider()
    try:
        recommendations = recommendation_service().recommend(st.session_state.get(TOKEN_KEY), limit=8)
        if not recommendations:
            with st.container(border=True):
                st.subheader('Vamos descobrir o que você gosta?')
                st.write('Ainda não encontramos sugestões para este perfil. Explore o catálogo e avalie livros para ajudar nas próximas recomendações.')
                st.button('Explorar o catálogo →', key='recomendacoes_catalogo', type='primary', on_click=navigate, args=(CATALOG,))
            return
        st.markdown(f'<div class="quantidade-livros">{len(recommendations)} livros selecionados para você</div>', unsafe_allow_html=True)
        with ThreadPoolExecutor(max_workers=6) as pool:
            covers = list(pool.map(lambda item: cover_image(item.book.isbn, item.book.thumbnail), recommendations))
        columns = st.columns(4, gap='medium')
        for index, item in enumerate(recommendations):
            reason = (f'Leitores com gostos semelhantes · {int(item.score)} indicações'
                      if item.reason == 'similar_customers' else 'Combina com suas categorias ou autores favoritos')
            with columns[index % 4]:
                render_book_card(item.book, True, covers[index], prefix='recomendado_', reason=reason)
    except SessionExpiredError as error:
        _expired(error)
    except ServiceError as error:
        show_error(error)
    st.divider()
