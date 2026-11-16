"""Visual compartilhado inspirado na referência SpaceBooks do Figma."""

CSS = """
<style>
html, [data-testid="stMain"] { scroll-behavior:smooth; overflow-anchor:none; }
@media(prefers-reduced-motion:reduce) { html, [data-testid="stMain"] { scroll-behavior:auto; } }
:root { --ink:#19372f; --blue:#1b50df; --muted:#78817b; --paper:#f8f7f2; }
.stApp { background:var(--paper); color:var(--ink); }
.block-container { max-width:1240px; padding:2rem 2.5rem 3rem; }
h1,h2,h3 { color:var(--ink); letter-spacing:-.045em; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stToolbar"] { opacity:.4; }
.logo { font-size:27px; font-weight:850; letter-spacing:-1.5px; color:var(--ink); }
.logo span { display:inline-block; font-size:24px; margin-left:8px; letter-spacing:0; }
.eyebrow { font-size:11px; letter-spacing:.14em; font-weight:800; color:var(--blue); margin-bottom:20px; }
.hero-title { font-size:clamp(36px,4.8vw,60px); font-weight:800; line-height:1.06; letter-spacing:-.055em; margin:0 0 24px; color:var(--ink); }
.hero-title em { color:var(--blue); font-style:normal; position:relative; white-space:nowrap; }
.hero-title em:after { content:''; position:absolute; height:4px; background:#efd35e; bottom:-3px; left:0; width:100%; border-radius:100%; }
.hero-copy { font-size:16px; color:var(--muted); line-height:1.8; max-width:520px; margin-bottom:24px; }
.hero-art { height:410px; position:relative; display:flex; align-items:center; justify-content:center; }
.hero-art:before { content:''; width:295px; height:340px; border-radius:50%; background:#f0d765; position:absolute; transform:rotate(20deg) translate(18px,8px); }
.hero-art:after { content:''; width:370px; height:160px; border:1px solid #ccd5de; border-radius:50%; position:absolute; transform:rotate(-30deg); pointer-events:none; }
.hero-art img { width:285px; height:365px; object-fit:cover; border:7px solid white; border-radius:50%; transform:rotate(12deg); box-shadow:0 18px 35px #19372f16; z-index:1; }
.hero-note { position:absolute; bottom:5px; right:0; background:white; box-shadow:0 10px 35px #19372f18; border:1px solid #edece7; padding:17px 20px; border-radius:17px; z-index:2; font-size:13px; font-weight:700; }
.hero-note small { display:block; font-size:9px; letter-spacing:.1em; color:var(--blue); margin-bottom:4px; }
.hero-facts { font-size:11px; color:var(--muted); margin:10px 0 30px; }
.hero-facts b { color:var(--ink); }
.section-title { font-size:32px; font-weight:750; letter-spacing:-1.2px; line-height:1.2; margin:0 0 10px; }
.section-copy { font-size:14px; color:var(--muted); margin-bottom:20px; }
[data-testid="stButton"] button, [data-testid="stPopover"] button { border:1px solid #dedfd9; border-radius:11px; min-height:42px; font-weight:600; background:white; color:var(--ink); }
[data-testid="stButton"] button:hover, [data-testid="stPopover"] button:hover { color:var(--blue); border-color:var(--blue); }
[data-testid="stButton"] button[kind="primary"] { background:var(--blue); color:white; border-color:var(--blue); }
[data-testid="stTextInput"] input { color:var(--ink) !important; background:white !important; }
[data-testid="stWidgetLabel"], [data-testid="stRadio"] label, [data-testid="stSelectbox"] { color:var(--ink) !important; }
[data-testid="stTextInput"] [data-baseweb="input"], [data-testid="stSelectbox"] [data-baseweb="select"] > div { background:white; border:1px solid #e0e3dc; border-radius:11px; min-height:46px; }
[data-testid="stRadio"] [role="radiogroup"] { gap:22px; padding:10px 0; }
[data-testid="stRadio"] label { font-size:12px; }
[class*="st-key-book_card_"] { background:white; border:1px solid #e6e8e1 !important; border-radius:17px; overflow:hidden; box-shadow:0 3px 14px #19372f04; transition:box-shadow .2s; }
[class*="st-key-book_card_"]:hover { box-shadow:0 8px 24px #19372f12; }
.capa-area { height:235px; display:flex; align-items:center; justify-content:center; border-radius:11px; background:#f0eadc; padding:18px; margin-bottom:16px; color:#61736a; }
[data-testid="stColumn"]:nth-child(4n+2) .capa-area { background:#e4eee7; }
[data-testid="stColumn"]:nth-child(4n+3) .capa-area { background:#f3e3dc; }
[data-testid="stColumn"]:nth-child(4n+4) .capa-area { background:#e5e9ef; }
.capa-area img { max-height:197px; max-width:88%; object-fit:contain; border-radius:2px 4px 4px 2px; box-shadow:5px 9px 15px #19372f2b; }
.livro-categoria { color:var(--blue); font-size:9px; letter-spacing:.08em; font-weight:750; text-transform:uppercase; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-bottom:7px; }
.livro-titulo { color:var(--ink); font-size:18px; font-weight:750; line-height:1.35; height:48px; overflow:hidden; }
.livro-autor { color:var(--muted); font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:5px; }
.livro-avaliacao { color:#98772f; font-size:11px; margin:13px 0 7px; }
.livro-preco { font-size:22px; font-weight:750; color:var(--ink); }
.livro-preco small { font-size:10px; font-weight:400; display:block; color:var(--muted); }
.livro-estoque { color:var(--muted); font-size:10px; margin:3px 0 12px; }
[class*="st-key-book_card_"] [data-testid="stButton"] button { background:var(--ink); color:white; border:0; }
[class*="st-key-book_card_"] [data-testid="stButton"] button:disabled { background:#e9ece6; color:#8d968d; }
.quantidade-livros { color:var(--muted); font-size:12px; margin:8px 0 18px; }
.indicador-pagina { text-align:center; color:var(--muted); font-size:12px; padding-top:10px; }
.recommend-banner { background:#e9eee5; border-radius:18px; padding:28px 32px; margin-top:24px; }
.recommend-banner h2 { font-size:28px; margin:5px 0 10px; }
.footer { border-top:1px solid #e1e4db; margin-top:40px; padding-top:24px; font-size:12px; color:var(--muted); }
@media(max-width:768px) { .block-container { padding:1.4rem 1rem; } .hero-art { height:320px; } .hero-art img { width:220px; height:280px; } .hero-art:before { width:230px; height:260px; } .hero-art:after { width:280px; } .section-title { font-size:26px; } .capa-area { height:200px; } .capa-area img { max-height:165px; } }
.st-key-header_nav [data-testid="stButton"] button { background:transparent !important; border:0 !important; border-radius:0; box-shadow:none; padding:14px 0; min-height:52px; color:#586e68; }
.st-key-header_nav [data-testid="stButton"] button p { font-size:16px; font-weight:650; white-space:nowrap; }
.st-key-header_nav button[kind="primary"] { color:var(--ink); }
.st-key-header_nav button[kind="primary"]:after { content:''; position:absolute; height:3px; background:#1b50df; width:calc(100% - 20px); max-width:46px; left:50%; transform:translateX(-50%); bottom:0; border-radius:2px; }
.st-key-header_nav [data-testid="stButton"] button { position:relative; }
.st-key-header_nav [data-testid="stButton"] button:hover { color:#1b50df; }
@media(max-width:1100px) { .st-key-header_nav [data-testid="stButton"] button p { font-size:13px; } .logo { font-size:23px; } .logo span { font-size:20px; } }
@media(max-width:640px) { .st-key-header_nav [data-testid="stHorizontalBlock"] { flex-wrap:nowrap; gap:10px; overflow-x:auto; } .st-key-header_nav [data-testid="stColumn"] { min-width:max-content; flex:1 0 auto; width:auto !important; } }
.produto-capa { min-height:480px; background:#eeece3; border-radius:20px; display:flex; align-items:center; justify-content:center; padding:38px; text-align:center; color:#6b7c70; } .produto-capa img { width:320px; height:auto; max-width:90%; max-height:520px; object-fit:contain; box-shadow:8px 15px 28px #19372f30; border-radius:4px; } .produto-preco { font-size:36px; font-weight:750; color:var(--ink); margin-bottom:8px; } @media(max-width:640px) { .produto-capa { min-height:320px; } .produto-capa img { max-height:300px; } }
</style>
"""
