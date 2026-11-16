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
.bag-eyebrow { margin-top:28px; color:#df7975; font-size:11px; font-weight:750; letter-spacing:.13em; }
.bag-steps { display:flex; gap:24px; align-items:center; margin:30px 0 42px; font-size:12px; color:#8a958d; flex-wrap:wrap; }
.bag-steps b { color:var(--blue); }
[class*="st-key-bag_item_"], .st-key-bag_summary { background:white; border:1px solid #e9e9e2 !important; border-radius:18px; padding:8px; }
.bag-cover { min-height:175px; padding:12px; border-radius:12px; background:#f0eadb; display:flex; align-items:center; justify-content:center; }
.bag-cover img { width:auto; max-width:100%; max-height:170px; object-fit:contain; border-radius:3px; }
.bag-count { text-align:center; padding-top:8px; font-weight:700; }
.bag-empty { text-align:center; padding:30px 10px 12px; }
.bag-empty p { color:var(--muted); }
.bag-icon { width:100px; height:100px; background:#f4d75f; border-radius:40% 50% 43% 55%; display:grid; place-items:center; margin:0 auto 24px; font-size:50px; color:var(--ink); }
@media(max-width:640px) { .bag-steps { gap:10px; } .bag-steps span:nth-child(even) { display:none; } }
/* Sacola: proporções e tipografia da referência. */
.bag-title { font-size:40px !important; font-weight:750 !important; margin:6px 0 12px; line-height:1.15; }
.bag-progress { display:flex; align-items:center; gap:18px; max-width:660px; margin:28px 0 42px; color:#929c95; font-size:12px; font-weight:600; }
.bag-progress > div { display:flex; align-items:center; gap:9px; white-space:nowrap; }
.bag-progress i { display:grid; place-items:center; font-style:normal; width:26px; height:26px; border:1px solid #e4e7df; background:white; border-radius:50%; box-shadow:0 3px 6px #19372f06; }
.bag-progress .selected { color:var(--blue); }.bag-progress .selected i { color:white; background:var(--blue); border-color:var(--blue); }
.bag-progress hr { flex:1; min-width:12px; margin:0; border:0; border-top:1px solid #dce0d8; }
.bag-section-title { font-size:21px !important; font-weight:700; margin:0 0 18px; line-height:1.3; letter-spacing:-.025em; }
[class*="st-key-bag_item_"] { padding:20px !important; margin-bottom:12px; }
[class*="st-key-bag_item_"] [data-testid="stVerticalBlock"] { gap:7px; }
.bag-cover { min-height:148px; padding:12px; border-radius:12px; background:#f1d483; }
.bag-cover img { max-height:136px; max-width:100%; box-shadow:2px 4px 8px #19372f20; }
.bag-category { font-size:9px; font-weight:750; letter-spacing:.07em; color:var(--blue); text-transform:uppercase; margin-bottom:7px; }
.bag-book-title { font-size:19px !important; line-height:1.3; margin:0 0 6px !important; padding:0 !important; letter-spacing:-.02em; }
.bag-author { font-size:12px; line-height:1.5; color:#7d8981; }.bag-stock { color:#43816a; font-size:11px; margin-top:16px; }
.bag-price { font-size:18px; font-weight:750; text-align:right; }.bag-unit { font-size:10px; color:#88948b; text-align:right; margin-bottom:8px; }
[class*="st-key-bag_quantity_"] { border:1px solid #e0e5dc; border-radius:9px; overflow:hidden; }
[class*="st-key-bag_quantity_"] [data-testid="stButton"] button { border:0; min-height:32px; border-radius:0; padding:0; background:transparent; }
.bag-count { font-size:12px; padding-top:6px; }.st-key-bag_summary { padding:25px !important; border-radius:20px; }
.st-key-bag_summary [data-testid="stVerticalBlock"] { gap:12px; }
.bag-summary-line { display:flex; justify-content:space-between; gap:12px; font-size:13px; color:#78867d; margin:0 0 13px; }.bag-summary-line strong { color:var(--ink); font-weight:650; }
.bag-total { border-top:1px solid #e4e7df; margin-top:9px; padding:22px 0 12px; display:flex; justify-content:space-between; gap:10px; font-size:17px; font-weight:650; align-items:center; }.bag-total strong { font-size:24px; letter-spacing:-.04em; }.bag-total small { display:block; font-size:10px; color:#8a958d; font-weight:400; margin-top:3px; }
.st-key-bag_summary [data-testid="stButton"] button { min-height:48px; font-size:12px; border-radius:10px; }
.bag-summary-note { font-size:12px; color:#5f7669; padding:12px 0; }.bag-summary-note small { display:block; font-size:11px; color:#8a958d; line-height:1.7; }
.bag-benefits { display:flex; justify-content:space-around; gap:24px; background:white; border-top:1px solid #e9ece4; margin-top:60px; padding:32px 20px; }.bag-benefits b { font-size:12px; font-weight:650; }.bag-benefits small { display:block; font-size:11px; color:#8a958d; padding-top:5px; }
@media(max-width:640px) { .bag-progress { gap:8px; font-size:10px; } .bag-benefits { flex-direction:column; } [class*="st-key-bag_quantity_"] [data-testid="stHorizontalBlock"] { flex-wrap:nowrap; } [class*="st-key-bag_quantity_"] [data-testid="stColumn"] { min-width:0; flex:1; width:auto!important; } }
.st-key-bag_shipping { background:white; border:1px solid #e6e9e0!important; border-radius:18px; padding:22px!important; margin-top:18px; }
.st-key-bag_shipping .bag-section-title { font-size:17px!important; margin-bottom:8px; }
.st-key-bag_shipping [data-testid="stForm"] { border:none; padding:0; }
.st-key-bag_shipping [data-testid="stFormSubmitButton"] button { border-radius:9px; min-height:46px; border:1px solid #dfe5db; }
.st-key-bag_summary { margin-top:4px; }
.bag-icon svg { width:44px; height:44px; }
.review-heading { display:flex; align-items:center; gap:12px; margin:10px 0 20px; }.review-heading > span { display:grid; place-items:center; width:36px; height:36px; flex-shrink:0; border-radius:50%; background:#eef3ff; color:#1b50df; font-size:11px; font-weight:700; }.review-heading h2 { font-size:20px!important; margin:0 0 5px; padding:0; letter-spacing:-.025em; }.review-heading p { font-size:11px; color:#8a958d; margin:0; }
[class*="st-key-review_item_"], .st-key-review_customer, .st-key-review_summary { background:white; border:1px solid #e8eae3!important; padding:22px!important; border-radius:20px; margin-bottom:20px; }
[class*="st-key-review_item_"] [data-testid="stVerticalBlock"] { gap:8px; }
.st-key-review_summary { padding:25px!important; }.st-key-review_summary .bag-eyebrow { margin:0 0 12px; font-size:10px; }.review-total-title { font-size:25px!important; margin:0 0 28px; }.st-key-review_summary [data-testid="stButton"] button { min-height:48px; }.review-progress { margin:18px 0 30px; gap:12px; }.bag-progress .complete { color:#43816a; }.bag-progress .complete i { background:#edfaf4; color:#43816a; border-color:#cce7d7; }
.confirmation-hero { position:relative; text-align:center; padding:48px 25px 56px; isolation:isolate; overflow:hidden; }
.confirmation-check { width:78px; height:78px; display:grid; place-items:center; margin:0 auto 25px; border-radius:50%; background:#16875e; color:white; box-shadow:0 0 0 9px #e1f2e8,0 12px 35px #198a5f30; }.confirmation-check svg { width:47px; height:47px; }
.confirmation-eyebrow { color:#2e8965; font-size:10px; font-weight:750; letter-spacing:.15em; margin-bottom:16px; }
.confirmation-hero h1 { max-width:760px; margin:0 auto 20px; font-size:clamp(34px,4vw,48px)!important; font-weight:800; line-height:1.08; letter-spacing:-.05em; }
.confirmation-hero p { color:#7d8980; max-width:650px; margin:0 auto 26px; font-size:14px; line-height:1.8; }
.confirmation-number { background:white; border:1px solid #e3e7df; display:inline-flex; align-items:center; justify-content:center; gap:14px; flex-wrap:wrap; border-radius:12px; padding:14px 18px; box-shadow:0 8px 22px #19372f08; }.confirmation-number span { color:#89958c; font-size:10px; }.confirmation-number strong { font-size:13px; color:#2859b3; overflow-wrap:anywhere; }
.confirmation-orbit { position:absolute; z-index:-1; width:620px; height:260px; border:1px solid #e0e3e7; border-radius:50%; top:35px; left:50%; transform:translateX(-50%) rotate(-14deg); }.confirmation-orbit.two { width:450px; height:220px; top:70px; transform:translateX(-50%) rotate(16deg); }.confirmation-dot { position:absolute; width:12px; height:12px; border-radius:50%; z-index:-1; }.confirmation-dot.coral { background:#ef7772; top:60px; left:38%; }.confirmation-dot.yellow { background:#efd45d; top:245px; right:28%; }
.st-key-confirmation_delivery,.st-key-confirmation_items,.st-key-confirmation_summary,.st-key-confirmation_status { background:white; border:1px solid #e7eae3!important; border-radius:20px; padding:25px!important; margin-bottom:20px; }
.confirmation-card-heading { display:flex; gap:12px; align-items:center; margin-bottom:25px; }.confirmation-heading-icon { display:grid; place-items:center; width:40px; height:40px; background:#eef3ff; color:#386bcb; border-radius:12px; flex-shrink:0; }.confirmation-heading-icon svg { width:21px; height:21px; }.confirmation-heading-icon.coral { background:#fff0ee; color:#e37570; }.confirmation-card-heading span { font-size:9px; letter-spacing:.1em; color:#8d978f; }.confirmation-card-heading h2 { font-size:20px!important; line-height:1.2; margin:5px 0 0; padding:0; }
.confirmation-timeline { display:flex; align-items:flex-start; gap:8px; margin:25px 0; }.confirmation-timeline > div { flex:1; text-align:center; color:#a0aaa2; }.confirmation-timeline i { font-style:normal; display:grid; place-items:center; width:27px; height:27px; border-radius:50%; background:#f5f6f2; border:1px solid #e4e9df; margin:0 auto 10px; font-size:11px; }.confirmation-timeline strong { font-size:10px; display:block; font-weight:650; }.confirmation-timeline small { display:block; font-size:9px; margin-top:5px; }.confirmation-timeline b { height:1px; flex:.5; background:#e5e9e1; margin-top:13px; }.confirmation-timeline .done { color:#278660; }.confirmation-timeline .done i { background:#268b64; color:white; border-color:#268b64; }
.confirmation-cover { background:#efe5cc; border-radius:10px; padding:10px; display:flex; align-items:center; justify-content:center; min-height:110px; }.confirmation-cover img { max-height:110px; max-width:100%; object-fit:contain; border-radius:3px; }.confirmation-summary-eyebrow { font-size:9px; font-weight:700; letter-spacing:.1em; color:#df7b76; margin-bottom:12px; }.confirmation-payment { display:flex; flex-direction:column; gap:4px; padding:15px 0 24px; font-size:12px; }.confirmation-payment span { color:#8e988f; font-size:10px; }.st-key-confirmation_summary [data-testid="stButton"] button { min-height:48px; }
.confirmation-discover { background:#eef1e9; text-align:center; border-radius:18px; padding:30px; margin-top:25px; }.confirmation-discover span { font-size:9px; letter-spacing:.12em; color:#6c8175; }.confirmation-discover h2 { font-size:25px!important; margin:10px 0; }
@media(max-width:640px) { .confirmation-hero { padding:35px 10px; }.confirmation-number { gap:8px; }.confirmation-timeline { flex-wrap:wrap; }.confirmation-orbit { width:360px; }.confirmation-orbit.two { width:280px; } }
.recommendation-reason { min-height:48px; font-size:11px; line-height:1.55; color:#587566; background:#edf4ee; border-radius:8px; padding:10px; margin:4px 0 12px; }
</style>
"""
