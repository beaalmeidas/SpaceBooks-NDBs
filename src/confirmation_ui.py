"""Tela de confirmação com valores históricos do pedido registrado."""
from html import escape
import streamlit as st
from src.cart_ui import money
from src.domain.contracts import ServiceError
from src.navigation_ui import CATALOG, navigate
from src.services.covers import cover_image

CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="m7.5 12 3 3 6-6"/></svg>'
TRUCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 18V4H3v14h2m4 0h6m-1-10h4l4 5v5h-3"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/></svg>'
BOOK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v16M2 3h6l4 2 4-2h6v16h-6l-4 2-4-2H2z"/></svg>'


def render_confirmation(result):
    order = result.order
    confirmed = order.status == 'confirmed'
    headline = 'Sua próxima história começa agora.' if confirmed else 'Consulte os detalhes do seu pedido.'
    status = 'PEDIDO CONFIRMADO' if confirmed else 'PEDIDO CANCELADO'
    st.markdown(f'''<section class="confirmation-hero"><div class="confirmation-orbit one"></div><div class="confirmation-orbit two"></div><div class="confirmation-dot coral"></div><div class="confirmation-dot yellow"></div><div class="confirmation-check">{CHECK}</div><div class="confirmation-eyebrow">{status}</div><h1>{headline}</h1><p>Obrigado por escolher a SpaceBooks. Os detalhes da sua compra estão reunidos abaixo.</p><div class="confirmation-number"><span>Número do pedido</span><strong>{escape(order.order_id)}</strong></div></section>''', unsafe_allow_html=True)
    left, right = st.columns([1.65, 1], gap='large')
    with left:
        with st.container(border=True, key='confirmation_delivery'):
            st.markdown(f'<div class="confirmation-card-heading"><div class="confirmation-heading-icon">{TRUCK}</div><div><span>STATUS DO PEDIDO</span><h2>{"Compra registrada" if confirmed else "Pedido cancelado"}</h2></div></div>', unsafe_allow_html=True)
            st.markdown('''<div class="confirmation-timeline"><div class="done"><i>✓</i><strong>Pedido registrado</strong><small>Consulte o status abaixo</small></div><b></b><div><i>2</i><strong>Preparação</strong><small>Não iniciada</small></div><b></b><div><i>3</i><strong>Envio</strong><small>Não contratado</small></div><b></b><div><i>4</i><strong>Entrega</strong><small>Sem rastreamento</small></div></div>''', unsafe_allow_html=True)
            st.caption('Demonstração acadêmica: não há envio físico, previsão real de entrega ou e-mail automático.')
        with st.container(border=True, key='confirmation_items'):
            quantity = sum(item.quantity for item in order.items)
            st.markdown(f'<div class="confirmation-card-heading"><div class="confirmation-heading-icon coral">{BOOK}</div><div><span>ITENS DA COMPRA</span><h2>{quantity} {"livro selecionado" if quantity == 1 else "livros selecionados"}</h2></div></div>', unsafe_allow_html=True)
            from src.catalog_ui import obter_catalogo
            for item in order.items:
                book = None
                try:
                    book = obter_catalogo().get_book(item.book_id)
                except ServiceError:
                    pass
                photo, detail, price = st.columns([1, 2.6, 1.1], vertical_alignment='center')
                with photo:
                    source, _ = cover_image(item.book_id, book.thumbnail if book else None)
                    if source:
                        st.markdown(f'<div class="confirmation-cover"><img src="{escape(source, quote=True)}" alt="Capa de {escape(item.title, quote=True)}"></div>', unsafe_allow_html=True)
                    else:
                        st.caption('Capa indisponível')
                with detail:
                    category = ' · '.join(book.categories) if book else 'LIVRO'
                    st.markdown(f'<div class="bag-category">{escape(category)}</div><h3 class="bag-book-title">{escape(item.title)}</h3>', unsafe_allow_html=True)
                    st.caption(f'Quantidade: {item.quantity} · ISBN {item.book_id}')
                with price:
                    st.markdown(f'<div class="bag-price">{money(item.quantity * item.unit_price_cents)}</div><div class="bag-unit">{money(item.unit_price_cents)} cada</div>', unsafe_allow_html=True)
    with right:
        with st.container(border=True, key='confirmation_summary'):
            st.markdown('<div class="confirmation-summary-eyebrow">RESUMO DA COMPRA</div><h2 class="review-total-title">Pedido registrado</h2><div class="confirmation-payment"><span>Forma de pagamento</span><strong>Demonstração · Sem cobrança</strong></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="bag-summary-line"><span>Subtotal</span><strong>{money(order.total_cents)}</strong></div><div class="bag-summary-line"><span>Entrega</span><span>Não contratada</span></div><div class="bag-total"><div>Total do pedido<small>Valor registrado dos livros</small></div><strong>{money(order.total_cents)}</strong></div>', unsafe_allow_html=True)
            st.button('Acompanhar pedido →', key='consultar_tentativa', type='primary', width='stretch', on_click=refresh_order, args=(order.order_id,))
            st.caption('Consulte a confirmação e as atualizações deste pedido.')
        with st.container(border=True, key='confirmation_status'):
            st.markdown('**Atualizações do pedido**')
            pending = [label for label, value in [('Histórico de compras',result.graph_status),('Limpeza da sacola',result.cart_status),('Atualização do catálogo',result.cache_status)] if value == 'pending']
            if pending:
                st.warning('Compra registrada. Atualizações pendentes: ' + ', '.join(pending) + '. Não confirme outra compra para repetir a tentativa.')
            else:
                st.success('Registro e atualizações concluídos.')
            if result.cart_cleanup == 'preserved':
                st.info('Novos itens da sua sacola foram preservados.')
            if order.created_at:
                st.caption('Registrado em ' + order.created_at.strftime('%d/%m/%Y · %H:%M UTC'))
    st.markdown('<div class="confirmation-discover"><span>MAIS HISTÓRIAS ESPERAM POR VOCÊ</span><h2>Que tal descobrir sua próxima leitura?</h2></div>', unsafe_allow_html=True)
    st.button('Voltar ao catálogo →', key='confirmacao_catalogo', type='primary', on_click=navigate, args=(CATALOG,))


def refresh_order(order_id):
    from src.checkout_ui import checkout_service
    from src.session_ui import TOKEN_KEY
    try:
        st.session_state['checkout_result'] = checkout_service().get_order(st.session_state.get(TOKEN_KEY), order_id)
        st.session_state.pop('confirmation_error', None)
    except ServiceError as error:
        st.session_state['confirmation_error'] = str(error)
