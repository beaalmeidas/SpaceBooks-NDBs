"""Sacola com itens à esquerda e resumo do pedido à direita."""
from html import escape
import streamlit as st
from src.cart_ui import cart_service, money, _action
from src.bag_icon import BAG_SVG
from src.domain.contracts import ServiceError, SessionExpiredError
from src.navigation_ui import CATALOG, CHECKOUT, navigate, open_product
from src.services.cart import MAX_QUANTITY
from src.services.covers import cover_image
from src.services.shipping import estimate_shipping
from src.session_ui import TOKEN_KEY
from src.ui_feedback import clear_session, show_error, show_message


def change_quantity(isbn, quantity):
    st.session_state[f'carrinho_quantidade_{isbn}'] = quantity
    _action('set', isbn)


def clear_bag():
    try:
        token = st.session_state.get(TOKEN_KEY)
        service = cart_service()
        for line in service.get_cart(token).items:
            service.remove_item(token, line.book.isbn)
        st.session_state.pop('frete_cep_calculado', None)
        st.session_state['carrinho_aviso'] = ('success', 'Sacola esvaziada.')
    except SessionExpiredError as error:
        clear_session(error)
    except ServiceError as error:
        st.session_state['carrinho_aviso'] = ('error', str(error))


def render_bag(customer):
    st.button('← Continuar comprando', key='continuar_comprando', on_click=navigate, args=(CATALOG,))
    st.markdown('<div class="bag-eyebrow">SUA ESTANTE ESTÁ QUASE COMPLETA</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="bag-title">Minha sacola</h1>', unsafe_allow_html=True)
    notice = st.session_state.pop('carrinho_aviso', None)
    if notice:
        st.toast(notice[1]) if notice[0] == 'success' else show_message(*notice)
    cart = None
    if customer is not None:
        try:
            cart = cart_service().get_cart(st.session_state.get(TOKEN_KEY))
        except SessionExpiredError as error:
            clear_session(error, rerun=True)
            return
        except ServiceError as error:
            show_error(error)
            st.button('Atualizar carrinho', key='atualizar_carrinho')
            with st.expander('Remover livro indisponível pelo ISBN'):
                with st.form('remover_por_isbn'):
                    st.text_input('ISBN do livro', max_chars=13, key='remover_isbn')
                    st.form_submit_button('Remover por ISBN', on_click=_action, args=('remove',))
            return
    quantity = sum(line.quantity for line in cart.items) if cart else 0
    st.caption(f'{quantity} livro(s) selecionado(s) para sua próxima jornada.' if quantity else 'Sua próxima grande leitura pode começar por aqui.')
    st.markdown('<div class="bag-progress"><div class="selected"><i>1</i>Sacola</div><hr><div><i>2</i>Revisão</div><hr><div><i>3</i>Confirmação</div></div>', unsafe_allow_html=True)
    if not cart or not cart.items:
        st.session_state.pop('frete_cep_calculado', None)
        st.markdown(f'<div class="bag-empty"><div class="bag-icon">{BAG_SVG}</div><h2>Sua sacola está esperando por histórias</h2><p>Explore nosso catálogo e encontre livros que merecem um lugar na sua estante.</p></div>', unsafe_allow_html=True)
        if customer is None:
            st.info('Use “Identificar-se” no cabeçalho para acessar sua sacola.')
        center = st.columns([1, 1, 1])[1]
        with center:
            st.button('Explorar o catálogo →', type='primary', width='stretch', key='explorar_catalogo', on_click=navigate, args=(CATALOG,))
        return
    items, summary = st.columns([2.05, 1], gap='large')
    with items:
        title, refresh = st.columns([2, 1], vertical_alignment='center')
        title.markdown('<h2 class="bag-section-title">Seus livros</h2>', unsafe_allow_html=True)
        refresh.button('Limpar sacola', icon=':material/delete:', key='limpar_sacola', width='stretch', type='tertiary', on_click=clear_bag)
        for line in cart.items:
            book = line.book
            with st.container(border=True, key=f'bag_item_{book.isbn}'):
                photo, detail, actions = st.columns([1, 2.25, 1.25], gap='small', vertical_alignment='center')
                with photo:
                    source, _ = cover_image(book.isbn, book.thumbnail)
                    if source:
                        st.markdown(f'<div class="bag-cover"><img src="{escape(source, quote=True)}" alt="Capa de {escape(book.title, quote=True)}"></div>', unsafe_allow_html=True)
                    else:
                        st.caption('Capa pendente')
                with detail:
                    st.markdown(f'<div class="bag-category">{escape(" · ".join(book.categories))}</div><h3 class="bag-book-title">{escape(book.title)}</h3><div class="bag-author">{escape("; ".join(book.authors))}</div>', unsafe_allow_html=True)
                    st.caption('✓ Em estoque' if book.stock else 'Indisponível')
                    st.button('Ver detalhes', key=f'sacola_detalhes_{book.isbn}',
                              type='tertiary', width=140, on_click=open_product, args=(book.isbn,))
                with actions:
                    st.markdown(f'<div class="bag-price">{money(line.subtotal_cents)}</div><div class="bag-unit">{money(book.price_cents)} cada</div>', unsafe_allow_html=True)
                    with st.container(key=f'bag_quantity_{book.isbn}'):
                        minus, count, plus = st.columns(3, gap=None)
                        minus.button('−', key=f'diminuir_{book.isbn}', disabled=line.quantity <= 1,
                                     on_click=change_quantity, args=(book.isbn, line.quantity-1), width='stretch')
                        count.markdown(f'<div class="bag-count">{line.quantity}</div>', unsafe_allow_html=True)
                        plus.button('+', key=f'aumentar_{book.isbn}', disabled=line.quantity >= min(book.stock, MAX_QUANTITY),
                                    on_click=change_quantity, args=(book.isbn, line.quantity+1), width='stretch')
                    st.button('Remover', icon=':material/delete:', type='tertiary', key=f'remover_{book.isbn}', on_click=_action, args=('remove',book.isbn), width='stretch')
            if line.quantity > book.stock:
                st.warning(f'Estoque atual de {book.title}: {book.stock}. Ajuste a quantidade para continuar.')
        st.caption('Itens não reservam estoque. Sua sacola fica disponível por 24 horas após a última alteração.')
        with st.container(border=True, key='bag_shipping'):
            st.markdown('<h3 class="bag-section-title">Calcule seu prazo de entrega</h3>', unsafe_allow_html=True)
            st.caption('Informe seu CEP para consultar a estimativa de entrega.')
            with st.form('calcular_frete'):
                postal, calculate = st.columns([3, 1], vertical_alignment='bottom')
                postal.text_input('CEP', placeholder='00000-000', max_chars=9, key='frete_cep')
                submitted = calculate.form_submit_button('Calcular', width='stretch')
            if submitted:
                try:
                    quote = estimate_shipping(st.session_state.get('frete_cep', ''), cart.total_cents)
                    st.session_state['frete_cep_calculado'] = quote.postal_code
                except ValueError as error:
                    st.session_state.pop('frete_cep_calculado', None)
                    st.error(str(error))
            if st.session_state.get('frete_cep_calculado'):
                quote = estimate_shipping(st.session_state['frete_cep_calculado'], cart.total_cents)
                st.success(f'Entrega estimada em {quote.minimum_days} a {quote.maximum_days} dias úteis · CEP {quote.postal_code}')
            st.caption('Simulação: não verifica a existência do CEP nem consulta transportadoras.')
    quote = estimate_shipping(st.session_state['frete_cep_calculado'], cart.total_cents) if st.session_state.get('frete_cep_calculado') else None
    delivery_label = ('Grátis' if quote.cost_cents == 0 else money(quote.cost_cents)) if quote else 'Calcule pelo CEP'
    estimated_total = cart.total_cents + (quote.cost_cents if quote else 0)
    with summary:
        with st.container(border=True, key='bag_summary'):
            st.markdown(f'<h2 class="bag-section-title">Resumo do pedido</h2><div class="bag-summary-line"><span>Subtotal ({quantity} itens)</span><strong>{money(cart.total_cents)}</strong></div><div class="bag-summary-line"><span>Entrega estimada</span><strong>{delivery_label}</strong></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="bag-total"><div>Total estimado<small>{"Livros + entrega simulada" if quote else "Frete ainda não calculado"}</small></div><strong>{money(estimated_total)}</strong></div>', unsafe_allow_html=True)
            st.button('Continuar para revisão →', type='primary', width='stretch', key='ir_checkout',
                      disabled=any(line.quantity > line.book.stock for line in cart.items), on_click=navigate, args=(CHECKOUT,))
            st.markdown('<div class="bag-summary-note">✓ Revise antes de confirmar<br><small>Confira os livros e as quantidades na próxima etapa.</small></div>', unsafe_allow_html=True)
        st.markdown('<div class="bag-summary-note">Ambiente demonstrativo<br><small>Frete é apenas uma simulação; o pedido registra somente o valor dos livros. Sem cobrança financeira.</small></div>', unsafe_allow_html=True)
    st.markdown('<div class="bag-benefits"><div><b>♧ Frete grátis</b><small>Simulado para pedidos acima de R$ 99</small></div><div><b>✓ Estoque atualizado</b><small>Validado na confirmação</small></div><div><b>♡ Sua próxima leitura</b><small>Escolhida por você</small></div></div>', unsafe_allow_html=True)
