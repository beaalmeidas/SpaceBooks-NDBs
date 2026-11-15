"""Visual identity shared by every Streamlit view: CSS, header, hero and small HTML helpers."""

from html import escape

import streamlit as st


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,800&display=swap');

:root {
    --azul: #1749D7;
    --azul-escuro: #0F35A3;
    --azul-claro: #E6ECFC;
    --verde: #176440;
    --verde-claro: #DDEFE1;
    --amarelo: #F4D85D;
    --laranja: #B45309;
    --laranja-claro: #FDF0DC;
    --vermelho: #B42318;
    --vermelho-claro: #FDE7E5;
    --fundo: #F7F8F4;
    --superficie: #FFFFFF;
    --borda: #E3E7E1;
    --texto: #172B27;
    --texto-suave: #4B5A54;
    --cinza: #69746E;
    --sombra: 0 1px 2px rgba(23, 43, 39, .04), 0 6px 20px rgba(23, 43, 39, .05);
    --sombra-alta: 0 4px 10px rgba(23, 43, 39, .06), 0 18px 36px rgba(23, 43, 39, .10);
    --serifa: 'Fraunces', Georgia, 'Times New Roman', serif;
}

/* ---------- Base ---------- */
.stApp { background: var(--fundo); color: var(--texto); }
header[data-testid="stHeader"] { background: transparent; height: 0; }
.block-container { max-width: 1240px; padding-top: 1.4rem; padding-bottom: 3rem; }
h1, h2, h3 { letter-spacing: -.01em; }

/* ---------- Barra superior ---------- */
.st-key-topbar {
    background: var(--superficie);
    border: 1px solid var(--borda);
    border-radius: 20px;
    padding: 10px 14px 10px 22px;
    box-shadow: var(--sombra);
    margin-bottom: 4px;
}
.marca { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.marca-nome {
    font-family: var(--serifa);
    color: var(--azul);
    font-size: 30px;
    font-weight: 800;
    letter-spacing: -1px;
    line-height: 1;
}
.marca-ponto { color: var(--verde); }
.marca-frase { color: var(--cinza); font-size: 13px; }

/* Navegação em abas (o rádio continua sendo o widget de estado) */
.st-key-navegacao [role="radiogroup"] {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    background: #EEF2EC;
    padding: 4px;
    border-radius: 999px;
    width: fit-content;
    margin-left: auto;
}
.st-key-navegacao [data-testid="stRadioOption"] {
    margin: 0;
    padding: 7px 16px;
    border-radius: 999px;
    cursor: pointer;
    transition: background .15s ease, color .15s ease;
}
.st-key-navegacao [data-testid="stRadioOption"] > div > div:not([data-testid]) { display: none; }
.st-key-navegacao [data-testid="stRadioOption"] p { font-size: 14px; font-weight: 600; color: var(--texto-suave); }
.st-key-navegacao [data-testid="stRadioOption"]:hover { background: rgba(255, 255, 255, .7); }
.st-key-navegacao [data-testid="stRadioOption"][data-selected="true"] {
    background: var(--superficie);
    box-shadow: 0 1px 3px rgba(23, 43, 39, .12);
}
.st-key-navegacao [data-testid="stRadioOption"][data-selected="true"] p { color: var(--azul); }
.st-key-navegacao [data-testid="stRadioOption"]:has(input:focus-visible) { outline: 2px solid var(--azul); outline-offset: 1px; }

/* ---------- Identificação ---------- */
.st-key-identidade {
    background: var(--superficie);
    border: 1px solid var(--borda);
    border-radius: 16px;
    padding: 12px 18px;
}
.cliente { display: flex; align-items: center; gap: 12px; }
.cliente-avatar {
    width: 40px; height: 40px; flex: 0 0 40px;
    border-radius: 50%;
    display: grid; place-items: center;
    background: var(--azul-claro); color: var(--azul);
    font-weight: 800; font-size: 17px;
}
.cliente-nome { font-weight: 700; font-size: 15px; color: var(--texto); line-height: 1.25; }
.cliente-id { font-size: 12px; color: var(--cinza); font-family: ui-monospace, monospace; }

/* ---------- Hero ---------- */
.hero {
    position: relative;
    overflow: hidden;
    background: var(--amarelo);
    border-radius: 24px;
    padding: 34px 40px;
    margin: 6px 0 8px;
}
.hero::before, .hero::after {
    content: ""; position: absolute; border-radius: 50%; pointer-events: none;
}
.hero::before { width: 240px; height: 240px; right: -60px; top: -90px; border: 28px solid rgba(23, 73, 215, .12); }
.hero::after { width: 120px; height: 120px; right: 150px; bottom: -70px; background: rgba(23, 100, 64, .12); }
.hero-selo {
    display: inline-block; color: #fff; background: var(--azul);
    padding: 6px 12px; border-radius: 999px;
    font-size: 11px; font-weight: 700; letter-spacing: 1.2px; margin-bottom: 14px;
}
.hero-titulo {
    font-family: var(--serifa);
    font-size: clamp(28px, 3.4vw, 42px);
    font-weight: 800; line-height: 1.1; letter-spacing: -.5px;
    color: var(--texto); max-width: 680px; margin-bottom: 10px;
}
.hero-texto { color: #34443E; font-size: 16px; line-height: 1.55; max-width: 600px; }

/* ---------- Cabeçalhos de seção ---------- */
.secao { margin: 18px 0 4px; }
.secao-selo {
    color: var(--verde); font-size: 12px; font-weight: 700;
    letter-spacing: 1.4px; text-transform: uppercase; margin-bottom: 4px;
}
.secao-titulo {
    font-family: var(--serifa);
    font-size: 28px; font-weight: 800; letter-spacing: -.5px;
    color: var(--texto); line-height: 1.15;
}
.secao-descricao { color: var(--cinza); font-size: 14px; margin-top: 4px; }

/* ---------- Botões ---------- */
.stButton > button, .stFormSubmitButton > button {
    border-radius: 12px;
    font-weight: 600;
    min-height: 40px;
    transition: background .15s ease, border-color .15s ease, color .15s ease, transform .1s ease;
}
.stButton > button:active:not(:disabled) { transform: translateY(1px); }
button[data-testid^="stBaseButton-primary"] { background: var(--azul); border: 1px solid var(--azul); color: #fff; }
button[data-testid^="stBaseButton-primary"]:hover:not(:disabled) { background: var(--azul-escuro); border-color: var(--azul-escuro); color: #fff; }
button[data-testid^="stBaseButton-secondary"] { background: var(--superficie); border: 1px solid #D5DCD4; color: var(--texto); }
button[data-testid^="stBaseButton-secondary"]:hover:not(:disabled) { border-color: var(--azul); color: var(--azul); background: var(--superficie); }
button[data-testid^="stBaseButton-tertiary"] { color: var(--azul); font-weight: 600; }
.stButton > button:disabled { background: #EEF0EC; border-color: #EEF0EC; color: #9AA39D; }

/* ---------- Campos ---------- */
div[data-testid="stTextInput"] input { background: var(--superficie); }
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { background: var(--superficie); }
.st-key-filtros {
    background: var(--superficie);
    border: 1px solid var(--borda);
    border-radius: 18px;
    padding: 14px 18px 4px;
    box-shadow: var(--sombra);
}

/* ---------- Pílulas e selos ---------- */
.pilula {
    display: inline-flex; align-items: center; gap: 6px;
    border-radius: 999px; padding: 5px 12px;
    font-size: 13px; font-weight: 600;
}
.pilula-verde { color: var(--verde); background: var(--verde-claro); }
.pilula-azul { color: var(--azul); background: var(--azul-claro); }
.pilula-laranja { color: var(--laranja); background: var(--laranja-claro); }
.pilula-vermelha { color: var(--vermelho); background: var(--vermelho-claro); }

/* ---------- Cartões de livro ---------- */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.livro),
div[data-testid="stVerticalBlock"]:has(> div > div > div > .livro) {
    background: var(--superficie);
    border-color: var(--borda);
    border-radius: 18px;
    box-shadow: var(--sombra);
    transition: transform .2s ease, box-shadow .2s ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.livro):hover {
    transform: translateY(-3px);
    box-shadow: var(--sombra-alta);
}
.capa {
    height: 230px;
    display: flex; justify-content: center; align-items: center;
    border-radius: 12px;
    background: linear-gradient(160deg, #EAF0FD 0%, #F2F5EE 100%);
    margin-bottom: 14px; padding: 14px;
    overflow: hidden;
}
.capa img {
    max-width: 100%; max-height: 100%; object-fit: contain;
    border-radius: 3px;
    box-shadow: 0 6px 14px rgba(23, 43, 39, .22), 0 1px 2px rgba(23, 43, 39, .2);
}
.capa-vazia {
    width: 120px; height: 180px; border-radius: 4px 8px 8px 4px;
    background: linear-gradient(135deg, var(--azul) 0%, #3F6AE6 100%);
    color: #fff; padding: 14px 12px;
    display: flex; flex-direction: column; justify-content: space-between;
    box-shadow: 0 6px 14px rgba(23, 43, 39, .22);
    font-family: var(--serifa); font-size: 14px; font-weight: 600; line-height: 1.2;
    overflow: hidden; text-align: left;
}
.capa-vazia small { font-family: inherit; font-size: 10px; opacity: .8; letter-spacing: 1px; }
.capa-mini { height: 120px; padding: 8px; margin-bottom: 0; }
.capa-mini .capa-vazia { width: 70px; height: 104px; font-size: 10px; padding: 8px; }

.livro-categoria {
    display: inline-block; max-width: 100%;
    overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
    color: var(--verde); background: var(--verde-claro);
    border-radius: 999px; padding: 3px 10px;
    font-size: 11px; font-weight: 700; letter-spacing: .3px; margin-bottom: 8px;
}
.livro-titulo {
    height: 44px; line-height: 22px;
    font-size: 16px; font-weight: 700; color: var(--texto);
    overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.livro-autor {
    height: 22px; margin-top: 2px;
    overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
    color: var(--cinza); font-size: 13px;
}
.livro-avaliacao { display: flex; align-items: center; gap: 6px; height: 26px; font-size: 13px; color: var(--texto-suave); }
.estrelas { position: relative; display: inline-block; font-size: 14px; letter-spacing: 1px; line-height: 1; color: #D9DDD6; }
.estrelas span { position: absolute; left: 0; top: 0; overflow: hidden; white-space: nowrap; color: #E0A800; }
.livro-rodape { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 10px 0 12px; flex-wrap: wrap; }
.livro-preco { color: var(--azul); font-size: 22px; font-weight: 800; letter-spacing: -.3px; }
.livro-estoque { font-size: 12px; }

/* ---------- Carrinho e checkout ---------- */
.item-titulo { font-weight: 700; font-size: 16px; color: var(--texto); line-height: 1.3; }
.item-meta { color: var(--cinza); font-size: 13px; margin-top: 4px; }
.item-subtotal { color: var(--azul); font-weight: 800; font-size: 18px; margin-top: 8px; }
.st-key-resumo_carrinho, .st-key-revisao_compra, .st-key-pedido_confirmado {
    background: var(--superficie);
    border: 1px solid var(--borda);
    border-radius: 18px;
    padding: 18px 20px;
    box-shadow: var(--sombra);
}
.resumo-titulo { font-family: var(--serifa); font-weight: 800; font-size: 20px; margin-bottom: 6px; }
.resumo-linha { display: flex; justify-content: space-between; color: var(--texto-suave); font-size: 14px; padding: 4px 0; }
.st-key-resumo_carrinho [data-testid="stMarkdownContainer"] strong,
.st-key-revisao_compra [data-testid="stMarkdownContainer"] strong,
.st-key-pedido_confirmado [data-testid="stMarkdownContainer"] strong { font-size: 18px; }
.linha-pedido {
    display: flex; justify-content: space-between; gap: 12px;
    padding: 8px 0; border-bottom: 1px dashed var(--borda); font-size: 14px;
}
.linha-pedido span:last-child { font-weight: 700; white-space: nowrap; }

/* ---------- Recomendações ---------- */
.rec-motivo { font-size: 12px; }
.rec-preco { color: var(--azul); font-weight: 700; font-size: 15px; margin: 6px 0 2px; }

/* ---------- Paginação ---------- */
.indicador-pagina { text-align: center; color: var(--texto-suave); font-size: 14px; padding-top: 9px; }
.indicador-pagina b { color: var(--azul); }

/* ---------- Rodapé ---------- */
.rodape {
    display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
    border-top: 1px solid #DCE2DB; padding-top: 22px; margin-top: 48px;
    color: var(--cinza); font-size: 13px;
}
.rodape .marca-nome { font-size: 20px; }

/* ---------- Telas menores ---------- */
@media (max-width: 768px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 1rem; }
    .st-key-topbar { padding: 12px 14px; }
    .st-key-navegacao [role="radiogroup"] { margin-left: 0; width: 100%; justify-content: center; border-radius: 16px; }
    .st-key-navegacao [data-testid="stRadioOption"] { padding: 6px 10px; }
    .hero { padding: 26px 22px; }
    .secao-titulo { font-size: 24px; }
}
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def brand_html(tagline=True):
    frase = '<span class="marca-frase">Histórias para todos os seus universos.</span>' if tagline else ""
    return f'<div class="marca"><span class="marca-nome">spacebooks<span class="marca-ponto">.</span></span>{frase}</div>'


def render_hero():
    st.markdown(
        """
<div class="hero">
    <div class="hero-selo">✦ SUA ESTANTE DIGITAL</div>
    <div class="hero-titulo">Grandes histórias começam com uma escolha.</div>
    <div class="hero-texto">Explore milhares de títulos, monte seu carrinho e receba
        recomendações feitas a partir dos seus gostos.</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title, description=None, eyebrow=None):
    selo = f'<div class="secao-selo">{escape(eyebrow)}</div>' if eyebrow else ""
    texto = f'<div class="secao-descricao">{escape(description)}</div>' if description else ""
    st.markdown(f'<div class="secao">{selo}<div class="secao-titulo">{escape(title)}</div>{texto}</div>',
                unsafe_allow_html=True)


def render_footer():
    st.markdown(
        f'<div class="rodape">{brand_html(tagline=False)}'
        '<span>Um universo inteiro entre páginas · Projeto acadêmico com MongoDB, Redis e Neo4j</span></div>',
        unsafe_allow_html=True,
    )


def money(cents):
    reais = f"{cents // 100:,}".replace(",", ".")
    return f"R$ {reais},{cents % 100:02d}"


def cover_html(book, *, mini=False):
    """Book cover with a typographic placeholder when the image is missing."""
    css = "capa capa-mini" if mini else "capa"
    if book.thumbnail:
        url = book.thumbnail
        if url.startswith("http://books.google.com/"):
            url = "https://" + url[len("http://"):]
        return f'<div class="{css}"><img src="{escape(url, quote=True)}" alt="Capa de {escape(book.title, quote=True)}" loading="lazy"></div>'
    return f'<div class="{css}"><div class="capa-vazia"><span>{escape(book.title[:60])}</span><small>SPACEBOOKS</small></div></div>'


def stars_html(rating):
    if rating is None:
        return '<div class="livro-avaliacao">Sem avaliação</div>'
    percent = max(0.0, min(5.0, rating)) / 5 * 100
    return (f'<div class="livro-avaliacao"><span class="estrelas" aria-label="{rating:.1f} de 5">★★★★★'
            f'<span style="width:{percent:.0f}%">★★★★★</span></span>{rating:.1f}</div>')


def stock_html(stock):
    if stock < 1:
        return '<span class="pilula pilula-vermelha livro-estoque">Esgotado · 0 unidades disponíveis</span>'
    texto = "1 unidade disponível" if stock == 1 else f"{stock} unidades disponíveis"
    if stock <= 5:
        return f'<span class="pilula pilula-laranja livro-estoque">Últimas: {texto}</span>'
    return f'<span class="pilula pilula-verde livro-estoque">{texto}</span>'
