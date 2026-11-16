"""Ícone vetorial da sacola e contador de unidades no cabeçalho."""
import base64
import streamlit as st
from src.cart_ui import cart_service
from src.domain.contracts import ServiceError
from src.navigation_ui import CART, CHECKOUT, navigate
from src.session_ui import TOKEN_KEY

BAG_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 10a4 4 0 0 1-8 0"/><path d="M3.103 6.034h17.794"/><path d="M3.4 5.467a2 2 0 0 0-.4 1.2V20a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6.667a2 2 0 0 0-.4-1.2l-2-2.667A2 2 0 0 0 17 2H7a2 2 0 0 0-1.6.8z"/></svg>'


def render_bag_icon(customer):
    quantity = 0
    available = True
    if customer is not None:
        try:
            cart = cart_service().get_cart(st.session_state.get(TOKEN_KEY))
            quantity = sum(line.quantity for line in cart.items)
        except ServiceError:
            available = False
    active = st.session_state.get('navegacao') in (CART, CHECKOUT)
    image = base64.b64encode(BAG_SVG.encode()).decode()
    badge = str(quantity) if quantity < 100 else '99+'
    badge_css = f'.st-key-abrir_sacola button::after {{ content:"{badge}"; }}' if quantity else ''
    st.markdown(f'''<style>
.st-key-abrir_sacola button {{ position:relative; width:52px; height:52px; padding:0; border-radius:15px; overflow:visible; color:{'#1b50df' if active else '#19372f'}; border:1px solid {'#a8bdf4' if active else '#dce1da'}; background:{'#eff3ff' if active else '#fff'}; }}
.st-key-abrir_sacola button p {{ font-size:0; margin:0; width:0; height:0; overflow:hidden; }}
.st-key-abrir_sacola button::before {{ position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); content:''; width:21px; height:21px; background:currentColor; mask:url('data:image/svg+xml;base64,{image}') center/contain no-repeat; -webkit-mask:url('data:image/svg+xml;base64,{image}') center/contain no-repeat; }}
.st-key-abrir_sacola button::after {{ position:absolute; right:-5px; top:-6px; display:grid; place-items:center; min-width:19px; height:19px; padding:0 4px; border-radius:999px; background:#ef6b68; color:white; font:700 10px sans-serif; border:2px solid #f8f7f2; }}
{badge_css}
</style>''', unsafe_allow_html=True)
    label = f'Abrir sacola, {quantity} unidades' if available else 'Abrir sacola, quantidade indisponível'
    st.button('Abrir sacola', key='abrir_sacola', help=label, on_click=navigate, args=(CART,))
