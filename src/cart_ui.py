"""Streamlit cart controls; all authorization and calculations live in the service."""

import atexit
from html import escape

import streamlit as st

from src.domain.contracts import ServiceError, SessionExpiredError
from src.services.cart import MAX_QUANTITY, RedisCartService
from src.session_ui import TOKEN_KEY
from src.navigation_ui import CART, CHECKOUT, OVERVIEW, navigate
from src.theme import cover_html, money, section_header
from src.ui_feedback import clear_session, show_error, show_message


@st.cache_resource
def cart_service():
    service = RedisCartService.from_env()
    atexit.register(service.close)
    return service


def _action(operation, isbn=None):
    try:
        token = st.session_state.get(TOKEN_KEY)
        if not token:
            raise SessionExpiredError("Identifique-se para utilizar o carrinho.")
        service = cart_service()
        if operation == "add":
            service.add_item(token, isbn)
        elif operation == "set":
            service.set_quantity(token, isbn, st.session_state[f"carrinho_quantidade_{isbn}"])
        else:
            isbn = isbn or st.session_state.get("remover_isbn", "").strip()
            service.remove_item(token, isbn)
        st.session_state.pop(f"carrinho_quantidade_{isbn}", None)
        st.session_state["carrinho_aviso"] = ("success", "Carrinho atualizado.")
    except SessionExpiredError as error:
        clear_session(error)
        return
    except ServiceError as error:
        st.session_state["carrinho_aviso"] = ("error", str(error))
    st.session_state["carrinho_aberto"] = True
    if operation == "add" and st.session_state.get("navegacao", OVERVIEW) != OVERVIEW:
        navigate(CART)


def add_button(book, identified, *, key_prefix="adicionar"):
    st.button("Adicionar ao carrinho", key=f"{key_prefix}_{book.isbn}",
              disabled=not identified or book.stock < 1,
              on_click=_action, args=("add", book.isbn), width="stretch",
              type="primary", icon=":material/add_shopping_cart:")


def _cart_line(line, checkout_only):
    isbn = line.book.isbn
    with st.container(border=True):
        widths = [0.8, 3.2] if checkout_only else [0.8, 2.6, 1.6]
        cover, info, *controls = st.columns(widths, vertical_alignment="center")
        cover.markdown(cover_html(line.book, mini=True), unsafe_allow_html=True)
        with info:
            st.markdown(
                f'<div class="item-titulo">{escape(line.book.title)}</div>'
                f'<div class="item-meta">ISBN {escape(isbn)} · {line.quantity} × {money(line.book.price_cents)}</div>'
                f'<div class="item-subtotal">Subtotal: {money(line.subtotal_cents)}</div>',
                unsafe_allow_html=True,
            )
            if line.quantity > line.book.stock:
                st.warning(f"Estoque atual: {line.book.stock}. Ajuste a quantidade antes de finalizar a compra.")
        if controls:
            with controls[0]:
                st.number_input("Quantidade", min_value=1, max_value=MAX_QUANTITY, value=line.quantity,
                                step=1, key=f"carrinho_quantidade_{isbn}")
                with st.container(horizontal=True):
                    st.button("Salvar quantidade", key=f"salvar_{isbn}", on_click=_action, args=("set", isbn))
                    st.button("Remover", key=f"remover_{isbn}", on_click=_action, args=("remove", isbn),
                              type="tertiary", icon=":material/delete:")


def render_cart(customer, *, force_open=False, include_checkout=True, checkout_only=False):
    if customer is None:
        st.caption("Identifique um cliente para adicionar livros e consultar seu carrinho.")
        return
    if not force_open and not st.checkbox("Meu carrinho", key="carrinho_aberto"):
        return
    head, refresh = st.columns([4, 1], vertical_alignment="bottom")
    with head:
        section_header("Revisar e confirmar" if checkout_only else "Meu carrinho",
                       "Preços atuais do catálogo. Itens não reservam estoque. "
                       "Validade de 24 horas após a última alteração.",
                       eyebrow="Checkout" if checkout_only else "Carrinho")
    with refresh.container(horizontal=True, horizontal_alignment="right"):
        st.button("Atualizar carrinho", key="atualizar_carrinho", icon=":material/refresh:")
    notice = st.session_state.pop("carrinho_aviso", None)
    if notice:
        show_message(*notice)
    show_checkout_button = not include_checkout and not checkout_only
    cart = None
    summary = st.empty()
    try:
        token = st.session_state.get(TOKEN_KEY)
        cart = cart_service().get_cart(token)
        with summary.container():
            items, totals = st.columns([2.3, 1], gap="large")
            with items:
                if not cart.items:
                    st.info("Seu carrinho está vazio.")
                for line in cart.items:
                    _cart_line(line, checkout_only)
            with totals, st.container(key="resumo_carrinho"):
                quantity = sum(line.quantity for line in cart.items)
                st.markdown(
                    '<div class="resumo-titulo">Resumo</div>'
                    f'<div class="resumo-linha"><span>Itens</span><span>{quantity}</span></div>'
                    f'<div class="resumo-linha"><span>Frete</span><span>Grátis</span></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Total: {money(cart.total_cents)}**")
                if show_checkout_button:
                    st.button("Ir para checkout", key="ir_checkout", on_click=navigate, args=(CHECKOUT,),
                              type="primary", width="stretch", icon=":material/shopping_cart_checkout:")
                    show_checkout_button = False
    except SessionExpiredError as error:
        clear_session(error, rerun=True)
    except ServiceError as error:
        show_error(error)
    if include_checkout:
        from src.checkout_ui import render_checkout
        confirmed = render_checkout(cart)
        if confirmed is not None:
            summary.empty()
            with summary.container():
                if confirmed.cart_status == "done" and confirmed.cart_cleanup != "preserved":
                    st.info("Seu carrinho est\u00e1 vazio.")
                    st.write("**Total: R$ 0,00**")
                else:
                    st.info("Confira o estado do pedido e atualize o carrinho antes de iniciar outra compra.")
    elif show_checkout_button:
        st.button("Ir para checkout", key="ir_checkout", on_click=navigate, args=(CHECKOUT,), type="primary")
    if checkout_only:
        st.button("Editar carrinho", key="editar_carrinho", on_click=navigate, args=(CART,),
                  icon=":material/edit:")
        return
    # A deleted MongoDB book must remain removable without loading its metadata.
    with st.form("remover_por_isbn", border=False):
        field, submit = st.columns([3, 1], vertical_alignment="bottom")
        field.text_input("Remover por ISBN (inclusive livros excluídos do catálogo)", max_chars=13,
                         key="remover_isbn", placeholder="Ex.: 9780002005883")
        submit.form_submit_button("Remover por ISBN", on_click=_action, args=("remove",), width="stretch")
    st.divider()
