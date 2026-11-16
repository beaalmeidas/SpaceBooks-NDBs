"""Composição da revisão de pedido baseada na referência do Figma."""
from html import escape
import streamlit as st
from src.cart_ui import cart_service, money
from src.domain.contracts import ServiceError, SessionExpiredError
from src.navigation_ui import CART, navigate
from src.services.covers import cover_image
from src.services.shipping import estimate_shipping
from src.session_ui import TOKEN_KEY
from src.ui_feedback import clear_session, show_error


def render_review_page(customer):
    if st.session_state.get('checkout_result'):
        from src.checkout_ui import render_checkout
        render_checkout(None, customer=customer, modern=True)
        return
    st.button('← Voltar para a sacola', key='review_voltar', type='tertiary', on_click=navigate, args=(CART,))
    st.markdown('<div class="bag-eyebrow">CONFIRA ANTES DE FINALIZAR</div>', unsafe_allow_html=True)
    title, progress = st.columns([1.5, 1], vertical_alignment='center')
    with title:
        st.markdown('<h1 class="bag-title">Revisar e confirmar</h1>', unsafe_allow_html=True)
        st.caption('Verifique os itens e os valores do seu pedido antes de continuar.')
    with progress:
        st.markdown('<div class="bag-progress review-progress"><div class="complete"><i>✓</i>Sacola</div><hr><div class="selected"><i>2</i>Revisão</div><hr><div><i>3</i>Confirmação</div></div>', unsafe_allow_html=True)
    cart = None
    if customer is not None:
        try:
            cart = cart_service().get_cart(st.session_state.get(TOKEN_KEY))
        except SessionExpiredError as error:
            clear_session(error, rerun=True)
            return
        except ServiceError as error:
            show_error(error)
    from src.checkout_ui import render_checkout
    render_checkout(cart, customer=customer, modern=True)


def render_order_review(review, customer, *, current_cart=None):
    items, summary = st.columns([1.65, 1], gap='large')
    with items:
        st.markdown('<div class="review-heading"><span>01</span><div><h2>Itens do pedido</h2><p>Confira os livros e as quantidades antes de confirmar.</p></div></div>', unsafe_allow_html=True)
        for line in review.items:
            book = line.book
            with st.container(border=True, key=f'review_item_{book.isbn}'):
                cover, detail, price = st.columns([1, 2.3, 1.1], gap='small', vertical_alignment='center')
                with cover:
                    source, _ = cover_image(book.isbn, book.thumbnail)
                    if source:
                        st.markdown(f'<div class="bag-cover"><img src="{escape(source, quote=True)}" alt="Capa de {escape(book.title, quote=True)}"></div>', unsafe_allow_html=True)
                with detail:
                    st.markdown(f'<div class="bag-category">{escape(" · ".join(book.categories))}</div><h3 class="bag-book-title">{escape(book.title)}</h3><div class="bag-author">{escape("; ".join(book.authors))}</div>', unsafe_allow_html=True)
                    st.caption(f'ISBN {book.isbn} · Quantidade: {line.quantity}')
                with price:
                    st.markdown(f'<div class="bag-unit">{money(book.price_cents)} cada</div><div class="bag-price">{money(line.subtotal_cents)}</div>', unsafe_allow_html=True)
        st.markdown('<div class="review-heading"><span>02</span><div><h2>Dados do pedido</h2><p>Confira sua identificação e a forma de recebimento.</p></div></div>', unsafe_allow_html=True)
        with st.container(border=True, key='review_customer'):
            who, delivery = st.columns(2)
            with who:
                st.caption('Cliente')
                st.write(customer.name if customer else 'Cliente demonstrativo')
            with delivery:
                st.caption('Recebimento')
                st.write('Entrega simulada · 3 a 5 dias úteis' if st.session_state.get('frete_cep_calculado') else 'Entrega não simulada')
                if st.session_state.get('frete_cep_calculado'):
                    st.caption('CEP ' + st.session_state['frete_cep_calculado'])
            st.button('Editar itens da sacola', key='review_editar', type='tertiary', on_click=navigate, args=(CART,))
    with summary:
        quote = estimate_shipping(st.session_state['frete_cep_calculado'], review.total_cents) if st.session_state.get('frete_cep_calculado') else None
        quantity = sum(line.quantity for line in review.items)
        with st.container(border=True, key='review_summary'):
            st.markdown('<div class="bag-eyebrow">RESUMO DO PEDIDO</div><h2 class="review-total-title">Seu total</h2>', unsafe_allow_html=True)
            st.markdown(f'<div class="bag-summary-line"><span>Subtotal ({quantity} itens)</span><strong>{money(review.total_cents)}</strong></div><div class="bag-summary-line"><span>Entrega simulada</span><strong>{("Grátis" if quote.cost_cents == 0 else money(quote.cost_cents)) if quote else "Não calculada"}</strong></div>', unsafe_allow_html=True)
            if quote:
                st.markdown(f'<div class="bag-summary-line"><span>Estimativa com entrega</span><strong>{money(review.total_cents + quote.cost_cents)}</strong></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="bag-total"><div>Total a confirmar<small>Valor dos livros</small></div><strong>{money(review.total_cents)}</strong></div>', unsafe_allow_html=True)
            stale = current_cart is None or current_cart.revision != review.revision
            if stale:
                st.warning('A sacola mudou ou não pôde ser verificada. Atualize a revisão antes de confirmar.')
            clicked = st.button('Confirmar compra →', type='primary', key='confirmar_compra', width='stretch', disabled=stale)
            st.markdown('<div class="bag-summary-note">✓ Confirmação com validação de estoque<small>Frete apenas ilustrativo. O pedido registra somente os livros. Sem cobrança financeira.</small></div>', unsafe_allow_html=True)
        st.caption('Você poderá consultar o pedido pelo número após a confirmação.')
    st.markdown('<div class="bag-benefits"><div><b>✓ Estoque validado</b><small>Conferência antes da confirmação</small></div><div><b>↗ Acompanhe seu pedido</b><small>Status disponível após a compra</small></div></div>', unsafe_allow_html=True)
    return clicked
