"""Shared Streamlit identity helpers. Never authorize from a customer ID in UI state."""

import atexit
from html import escape

import streamlit as st

from src.domain.contracts import ServiceError
from src.services.sessions import RedisSessionService
from src.ui_feedback import clear_session, show_error


TOKEN_KEY = "_spacebooks_session_token"


@st.cache_resource
def session_service():
    # Connections are shared; tokens and identities are not stored in this resource.
    service = RedisSessionService.from_env()
    atexit.register(service.close)
    return service


def current_customer():
    """Return a freshly resolved Customer or None; protected services still receive the token."""
    token = st.session_state.get(TOKEN_KEY)
    return session_service().resolve(token) if token else None


def _enter(customer_id):
    try:
        service = session_service()
        previous = st.session_state.get(TOKEN_KEY)
        if previous:
            service.logout(previous)
        session = service.create_demo_session(customer_id)
    except ServiceError as error:
        st.session_state.clear()
        st.session_state["identificacao_aberta"] = True
        st.session_state["identificacao_aviso"] = str(error)
        return
    st.session_state.clear()
    st.session_state[TOKEN_KEY] = session.token


def _leave(switch=False):
    error_message = None
    token = st.session_state.get(TOKEN_KEY)
    try:
        if token:
            session_service().logout(token)
    except ServiceError as error:
        error_message = str(error)
    # Callbacks run before widgets: clear all per-browser state, including future
    # cart snapshots, checkout request IDs and cached recommendations.
    st.session_state.clear()
    if error_message:
        st.session_state["identificacao_aviso"] = error_message
    # A switch requires confirmed revocation; an outage leaves the browser signed out.
    st.session_state["identificacao_aberta"] = switch and error_message is None


def render_identity():
    customer = None
    try:
        customer = current_customer()
    except ServiceError as error:
        clear_session(error)

    message = st.session_state.pop("identificacao_aviso", None)
    if message:
        st.warning(message)
    if customer is not None:
        info, actions = st.columns([3, 2], vertical_alignment="center")
        initial = escape((customer.name.strip() or "?")[0].upper())
        info.markdown(
            f'<div class="cliente"><div class="cliente-avatar">{initial}</div><div>'
            f'<div class="cliente-nome">Olá, {escape(customer.name)}</div>'
            f'<div class="cliente-id">{escape(customer.customer_id)}</div></div></div>',
            unsafe_allow_html=True,
        )
        with actions.container(horizontal=True, horizontal_alignment="right"):
            st.button("Trocar cliente", key="trocar_cliente", on_click=_leave, args=(True,))
            st.button("Sair", key="sair_cliente", on_click=_leave)
        st.caption("Identificação demonstrativa, sem senha. Sessão válida por até 8 horas, sem renovação automática.")
        return customer

    if not st.checkbox("Identificação demonstrativa", key="identificacao_aberta",
                       help="Escolha um cliente cadastrado para usar carrinho, checkout e recomendações."):
        return None
    st.caption("Demonstração acadêmica: selecionar um cliente cadastrado não comprova sua identidade. Não há senha.")
    with st.form("buscar_clientes", border=False):
        field, submit = st.columns([4, 1], vertical_alignment="bottom")
        search = field.text_input("Nome ou ID do cliente", max_chars=200, key="pesquisa_cliente",
                                  placeholder="Ex.: DEMO, Maria ou o ID do cliente")
        submitted = submit.form_submit_button("Buscar clientes", width="stretch")
    if submitted:
        # Discard old candidates even when the new lookup fails.
        st.session_state.pop("clientes_encontrados", None)
        try:
            st.session_state["clientes_encontrados"] = session_service().list_customers(search)
        except ServiceError as error:
            show_error(error)
    candidates = st.session_state.get("clientes_encontrados")
    if candidates is not None:
        if not candidates:
            st.info("Nenhum cliente encontrado. Tente outro nome ou ID.")
        else:
            labels = {item.customer_id: f"{item.name} ({item.customer_id})" for item in candidates}
            choice, enter = st.columns([4, 1], vertical_alignment="bottom")
            selected = choice.selectbox("Cliente cadastrado", options=list(labels),
                                        format_func=labels.get, key="cliente_selecionado")
            enter.button("Entrar na demonstração", key="entrar_cliente", on_click=_enter, args=(selected,),
                         type="primary", width="stretch")
            st.caption("Até 50 resultados por busca. Refine pelo nome ou ID se necessário.")
    return None
