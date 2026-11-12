"""Streamlit recommendations and per-book editable ratings."""

import atexit

import streamlit as st

from src.cart_ui import add_button, money
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
    st.subheader("Recomendações para você")
    st.caption("Sugestões por gostos semelhantes, complementadas por suas categorias e autores favoritos.")
    st.button("Atualizar recomendações", key="atualizar_recomendacoes")
    try:
        recommendations = recommendation_service().recommend(st.session_state.get(TOKEN_KEY), limit=6)
        if not recommendations:
            st.info("Ainda não encontramos sugestões disponíveis para este perfil. Avalie livros ou ajuste suas preferências cadastradas.")
        columns = st.columns(3)
        for index, item in enumerate(recommendations):
            with columns[index % 3]:
                with st.container(border=True):
                    st.write(item.book.title)
                    st.caption("; ".join(item.book.authors))
                    st.write(f"{money(item.book.price_cents)} · Estoque: {item.book.stock}")
                    if item.reason == "similar_customers":
                        st.caption(f"Indicado por {int(item.score)} cliente(s) com gostos semelhantes.")
                    else:
                        st.caption("Combina com suas categorias ou autores favoritos.")
                    add_button(item.book, True, key_prefix="recomendado_adicionar")
    except SessionExpiredError as error:
        _expired(error)
    except ServiceError as error:
        show_error(error)
    st.divider()
