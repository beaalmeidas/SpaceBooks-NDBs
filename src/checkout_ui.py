"""Purchase review and confirmation, retaining the attempt after uncertain replies."""

import atexit
from uuid import uuid4

import streamlit as st

from src.domain.contracts import NotFoundError, ServiceError, SessionExpiredError
from src.services.checkout import MongoCheckoutService
from src.session_ui import TOKEN_KEY
from src.navigation_ui import CATALOG, navigate
from src.ui_feedback import clear_session, show_error


@st.cache_resource
def checkout_service():
    service = MongoCheckoutService.from_env()
    atexit.register(service.close)
    return service


def _money(cents):
    reais = f"{cents // 100:,}".replace(",", ".")
    return f"R$ {reais},{cents % 100:02d}"


def render_checkout(cart):
    confirmed_now = None
    st.subheader("Finalizar compra")
    token = st.session_state.get(TOKEN_KEY)
    try:
        if cart and cart.items and st.button("Revisar compra", key="revisar_compra"):
            previous = st.session_state.get("checkout_request_id")
            if previous and st.session_state.get("checkout_review"):
                try:
                    recovered = checkout_service().get_order(token, previous)
                except NotFoundError:
                    pass
                else:
                    st.session_state["checkout_result"] = recovered
                    st.session_state.pop("checkout_review", None)
                    st.rerun()
            # Only an explicit new review generates a new attempt. A unique MongoDB
            # index also prevents buying the same cart revision under another ID.
            request_id = str(uuid4())
            review = checkout_service().prepare(token, request_id, cart.revision)
            st.session_state["checkout_request_id"] = request_id
            st.session_state["checkout_review"] = review
            st.session_state.pop("checkout_result", None)
        review = st.session_state.get("checkout_review")
        if review:
            st.write("**Revisão da compra**")
            for line in review.items:
                st.write(f"{line.book.title} · {line.quantity} × {_money(line.book.price_cents)} = {_money(line.subtotal_cents)}")
            st.write(f"**Valor a confirmar: {_money(review.total_cents)}**")
            request_id = st.session_state["checkout_request_id"]
            st.caption(f"Identificador desta tentativa: {request_id}")
            st.caption("Demonstração acadêmica, sem cobrança ou pagamento externo.")
            if st.button("Confirmar compra", key="confirmar_compra"):
                result = checkout_service().checkout(token, request_id, review.revision)
                confirmed_now = result
                st.session_state["checkout_result"] = result
                st.session_state.pop("checkout_review", None)
                # A pending Redis stage must not hide the confirmation via a rerun
                # which would need to revalidate a now unavailable session store.
                if all(value == "done" for value in (result.graph_status, result.cart_status, result.cache_status)):
                    st.rerun()
        request_id = st.session_state.get("checkout_request_id")
        if request_id and st.button("Consultar esta tentativa", key="consultar_tentativa"):
            st.session_state["checkout_result"] = checkout_service().get_order(token, request_id)
        result = st.session_state.get("checkout_result")
        if result:
            st.success(f"Compra confirmada! Pedido: {result.order.order_id}")
            st.write(f"**Total do pedido: {_money(result.order.total_cents)}**")
            for item in result.order.items:
                st.write(f"{item.title} · {item.quantity} × {_money(item.unit_price_cents)}")
            pending = [name for name, value in (("histórico de compras", result.graph_status),
                                                ("limpeza do carrinho", result.cart_status),
                                                ("atualização do catálogo", result.cache_status)) if value == "pending"]
            if pending:
                st.warning("Compra registrada. Atualizações pendentes: " + ", ".join(pending) + ". Consulte este pedido novamente; não é necessário comprar outra vez.")
            if result.cart_cleanup == "preserved":
                st.info("Seu carrinho recebeu alterações novas e foi preservado. Confira os itens antes da próxima compra.")
    except SessionExpiredError as error:
        clear_session(error, rerun=True)
    except ServiceError as error:
        show_error(error)
        request_id = st.session_state.get("checkout_request_id")
        if request_id:
            st.caption(f"Mantenha o identificador desta tentativa: {request_id}")
    with st.form("consultar_pedido"):
        order_id = st.text_input("Número de um pedido anterior", key="numero_pedido")
        submitted = st.form_submit_button("Consultar pedido")
    if submitted:
        try:
            result = checkout_service().get_order(token, order_id.strip())
            st.session_state["checkout_result"] = result
            st.session_state["checkout_request_id"] = result.order.order_id
            st.session_state.pop("checkout_review", None)
            st.rerun()
        except SessionExpiredError as error:
            clear_session(error, rerun=True)
        except ServiceError as error:
            show_error(error)
    st.button("Voltar ao catálogo", key="voltar_catalogo", on_click=navigate, args=(CATALOG,))
    return confirmed_now
