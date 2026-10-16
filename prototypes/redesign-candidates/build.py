#!/usr/bin/env python3
"""Build two offline, comparable DP-441 design candidates. No live projection."""

from html import escape
from pathlib import Path

DEST = Path(__file__).resolve().parent

# A single deliberately fictional record is used in both variants. It is never
# interpreted as an approved, real-world quotation or publication permission.
SAMPLE = {
    "speaker": "Persona di esempio",
    "date": "12 ottobre 2026 (data fittizia)",
    "quote": "Questo testo è un esempio inventato per valutare la leggibilità.",
    "topic": "Servizi pubblici (tema dimostrativo)",
    "source": "Documento di esempio, pagina 2 (non esiste online)",
    "summary": "Esempio di sintesi distinta dalla frase originale.",
    "correction": "Esempio di correzione successiva: versione 2 (non pubblicata).",
}

VIEWS = [
    ("home", "Home · corpus vuoto"),
    ("explore", "Esplora · corpus vuoto"),
    ("statement", "Dichiarazione · fixture"),
    ("intersection", "Persona × Tema · fixture"),
    ("source", "Contenuto · fixture"),
    ("trace", "Traccia · fixture"),
]

BASE = """
* {box-sizing:border-box}
html {scroll-behavior:smooth} body {margin:0;font-family:system-ui,-apple-system,sans-serif;line-height:1.55;background:var(--paper);color:var(--ink)}
button, a {font:inherit} a {color:inherit;text-underline-offset:4px} a:focus-visible {outline:3px solid #b45309;outline-offset:5px}
.skip {position:absolute;left:-10000px;top:1rem;background:#fff;padding:.8rem;z-index:4}.skip:focus {left:1rem}
.flag {background:#201d1b;color:#fff;padding:.5rem max(1rem,calc((100vw - 1200px)/2));font:600 .75rem/1.4 system-ui;letter-spacing:.07em}
.site {max-width:1200px;margin:auto;padding:0 24px 80px}
.masthead {display:flex;align-items:center;justify-content:space-between;gap:20px;padding:24px 0;border-bottom:1px solid var(--rule)}
.brand {font-weight:800;letter-spacing:-.04em;font-size:1.22rem;text-decoration:none}
.masthead small {font-size:.76rem;color:var(--muted)}
.view-nav {display:flex;gap:8px;flex-wrap:wrap;padding:15px 0 0}
.view-nav a {font-size:.78rem;text-decoration:none;border:1px solid var(--rule);padding:10px 12px;border-radius:3px}
.view-nav a[aria-current=page] {background:var(--ink);color:var(--paper);border-color:var(--ink)}
.pane[hidden] {display:none!important}
main {min-height:60vh}
.eyebrow {font-size:.72rem;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:var(--accent)}
h1,h2,h3,p {margin-top:0} h1 {font:600 clamp(2.4rem,6.3vw,5.5rem)/1.07 Georgia,serif;letter-spacing:-.05em}
h2 {font:600 clamp(1.5rem,3vw,2.6rem)/1.18 Georgia,serif;letter-spacing:-.035em}
h3 {font-size:1.06rem;line-height:1.3}
.lead {font-size:clamp(1.08rem,2.2vw,1.37rem);max-width:65ch}
.muted {color:var(--muted)}
.pill {display:inline-block;background:var(--soft);font-size:.78rem;font-weight:700;padding:5px 9px}
.primary {display:inline-flex;align-items:center;min-height:46px;padding:10px 17px;background:var(--ink);color:var(--paper);text-decoration:none;font-weight:700;margin-top:18px}
.secondary {display:inline-flex;align-items:center;min-height:46px;padding:10px 17px;border:1px solid var(--ink);text-decoration:none;font-weight:700;margin-top:18px}
.rule {border-top:1px solid var(--rule);padding-top:22px}
.card {padding:23px;background:var(--surface);border:1px solid var(--rule);min-width:0}
.card p:last-child {margin-bottom:0}
.links {display:flex;flex-wrap:wrap;gap:12px;margin-top:10px}
.meta {font-size:.87rem;color:var(--muted)}
.quote {font:500 clamp(1.6rem,3.7vw,3.2rem)/1.3 Georgia,serif;letter-spacing:-.025em;margin:24px 0}
.quote:before {content:'“';color:var(--accent)} .quote:after {content:'”';color:var(--accent)}
.trail {list-style:none;padding:0;margin:0;counter-reset:steps}.trail li {padding:17px 0 17px 42px;border-top:1px solid var(--rule);position:relative}
.trail li:before {counter-increment:steps;content:counter(steps,decimal-leading-zero);position:absolute;left:0;font-size:.72rem;font-weight:800;color:var(--accent)}
.grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.foot {margin-top:60px;padding-top:20px;border-top:1px solid var(--rule);font-size:.82rem;color:var(--muted)}
@media (max-width:700px) {.site {padding:0 16px 60px}.masthead {align-items:flex-start;flex-direction:column;gap:4px;padding:17px 0}.view-nav {flex-wrap:nowrap;overflow-x:auto;margin-right:-16px;padding-right:16px;scrollbar-width:thin}.view-nav a {flex:none}.grid {grid-template-columns:1fr}.card {padding:17px}.flag {padding:8px 16px}.quote {font-size:1.7rem}}
@media (prefers-reduced-motion:reduce) {html {scroll-behavior:auto}}
"""

ATLAS = """
:root {--paper:#f7f4ed;--ink:#142c37;--muted:#51646a;--rule:#b7c9c7;--accent:#155a75;--surface:#ffffff;--soft:#dcebed}
.pane {padding-top:50px} .hero-atlas {display:grid;grid-template-columns:1.28fr .72fr;gap:52px;align-items:start}
.hero-atlas h1 {max-width:12ch}.reading-path {border-left:3px solid var(--accent);padding:12px 0 15px 24px}
.atlas-index {margin-top:55px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:0;border-top:1px solid var(--rule)}
.atlas-index > div {padding:25px 20px 0 0}
.atlas-index b {display:block;font:500 2.2rem Georgia,serif;margin-bottom:8px}
.atlas-statement {max-width:820px;margin:0 auto}.atlas-statement .quote {font-size:clamp(2rem,5vw,4rem)}
.atlas-detail {display:grid;grid-template-columns:1.35fr .65fr;gap:26px;margin-top:35px}
@media(max-width:700px){.pane {padding-top:28px}.hero-atlas,.atlas-detail {grid-template-columns:1fr;gap:20px}.atlas-index {grid-template-columns:1fr;gap:0}.atlas-index > div {padding:14px 0;border-bottom:1px solid var(--rule)}.reading-path {padding-left:14px}}
"""

LIBRARY = """
:root {--paper:#f4f0e7;--ink:#392b26;--muted:#685a53;--rule:#cebfb1;--accent:#925333;--surface:#fffcf7;--soft:#eadbd0}
.site {max-width:1300px}.pane {padding-top:28px}
.shelf-label {font:700 .7rem system-ui;letter-spacing:.17em;text-transform:uppercase;color:var(--accent)}
.library-grid {display:grid;grid-template-columns:minmax(245px,.68fr) minmax(0,1.8fr);gap:0;border:1px solid var(--rule);margin-top:24px;background:var(--surface)}
.catalog {background:#e9e1d4;border-right:1px solid var(--rule);padding:24px}.catalog a {display:block;padding:14px 0;border-bottom:1px solid var(--rule);font-weight:600}
.reading {padding:clamp(22px,4vw,60px)}.reading h1 {max-width:17ch;font-size:clamp(2.3rem,5vw,4.7rem)}
.source-slip {background:var(--soft);padding:20px 24px;border-left:5px solid var(--accent);margin:25px 0}
.library-record {border:1px solid var(--rule);display:grid;grid-template-columns:.8fr 1.7fr;background:var(--surface);margin:20px 0 36px}
.library-record aside {padding:22px;background:#e9e1d4;border-right:1px solid var(--rule)}.library-record article {padding:36px}
.library-record .quote {font-size:clamp(1.5rem,3.2vw,2.7rem)}
@media(max-width:700px){.pane {padding-top:18px}.library-grid,.library-record {grid-template-columns:1fr}.catalog {border-right:0;border-bottom:1px solid var(--rule);padding:17px}.catalog a {display:inline-block;margin-right:12px}.reading,.library-record article,.library-record aside {padding:20px}.library-record aside {border-bottom:1px solid var(--rule);border-right:0}}
"""


def card(title: str, body: str, link: str | None = None) -> str:
    action = f'<a href="?view={link}">Apri il percorso →</a>' if link else ""
    return f'<div class="card"><h3>{title}</h3><p>{body}</p>{action}</div>'


def home(variant: str) -> str:
    if variant == "atlante":
        return f"""<div class="hero-atlas"><div><p class="eyebrow">01 / Atlante delle parole</p>
<h1>La parola lascia una traccia.</h1><p class="lead">Un archivio consultabile delle dichiarazioni pubbliche, con parole esatte, data e fonte.</p>
<span class="pill">Archivio pubblico: nessuna dichiarazione disponibile</span><div><a class="primary" href="?view=explore">Apri Esplora →</a></div></div>
<aside class="reading-path"><p class="eyebrow">Il percorso di lettura</p><ol class="trail"><li>Trova una dichiarazione</li><li>Leggi le parole originali</li><li>Apri la fonte</li><li>Controlla verifiche e correzioni</li></ol></aside></div>
<div class="atlas-index"><div><b>Parole</b><p>Citazioni originali in primo piano.</p></div><div><b>Fonti</b><p>Un percorso verificabile all’origine.</p></div><div><b>Tempo</b><p>Cambiamenti e correzioni datate.</p></div></div>"""
    return """<p class="shelf-label">02 / Biblioteca delle fonti</p><div class="library-grid"><aside class="catalog">
<p class="shelf-label">Consulta l'archivio</p><a href="?view=explore">Indice delle dichiarazioni ↗</a>
<a href="?view=source">Scheda di una fonte (esempio) ↗</a><a href="?view=intersection">Persone e temi (esempio) ↗</a>
<p class="meta">Solo schede autorizzate entrano nell'archivio pubblico.</p></aside><div class="reading">
<p class="shelf-label">Archivio documentale / stato attuale</p><h1>Ogni dichiarazione ha una fonte.</h1>
<p class="lead">Esplora il documento, il contesto e le parole esatte. Le correzioni restano consultabili.</p>
<div class="source-slip"><strong>Catalogo pubblico vuoto</strong><p>Non ci sono dichiarazioni autorizzate da mostrare in questo momento.</p></div>
<a class="primary" href="?view=explore">Consulta l'indice →</a></div></div>"""


def explore(variant: str) -> str:
    title = "Cerca parole e persone" if variant == "atlante" else "Indice consultabile"
    intro = "Una ricerca unificata per persona, tema, data e fonte." if variant == "atlante" else "Dichiarazioni, persone, temi e documenti disponibili, ordinati per tipo."
    if variant == "atlante":
        return f"""<p class="eyebrow">Esplora / stato reale vuoto</p><h1>{title}</h1><p class="lead">{intro}</p>
<div class="card" role="status"><h2>Il corpus pubblico è ancora vuoto.</h2><p>La ricerca diventerà utilizzabile quando saranno pubblicate dichiarazioni con fonti autorizzate.</p>
<a class="secondary" href="?view=statement">Vedi solo un esempio etichettato →</a></div>"""
    return f"""<p class="shelf-label">Catalogo / Esplora</p><div class="library-grid"><aside class="catalog"><p class="shelf-label">Indice per tipologia</p>
<p>Dichiarazioni</p><p>Persone</p><p>Temi</p><p>Contenuti</p></aside><div class="reading"><h1>{title}</h1><p class="lead">{intro}</p>
<div class="source-slip" role="status"><h2>Nessuna scheda pubblica</h2><p>I filtri sono inattivi perché non ci sono record autorizzati.</p></div>
<a class="secondary" href="?view=statement">Apri una scheda di esempio →</a></div></div>"""


def statement(variant: str) -> str:
    q = escape(SAMPLE["quote"])
    details = f"""<p class="eyebrow">Parole originali / fixture, non pubblicato</p><blockquote class="quote">{q}</blockquote>
<p><strong>{escape(SAMPLE['speaker'])}</strong> · {escape(SAMPLE['date'])}</p>
<p class="meta">Tema: {escape(SAMPLE['topic'])}</p>"""
    source = f"""<div class="card"><p class="eyebrow">Provenienza · simulata</p><h3>{escape(SAMPLE['source'])}</h3>
<p>Questa fonte è inventata e non possiede un URL esterno. Nessun dato è stato pubblicato.</p>
<a href="?view=source">Apri il contenuto dimostrativo →</a></div>"""
    summary = f"""<div class="card"><p class="eyebrow">Sintesi distinta dall'originale</p><p>{escape(SAMPLE['summary'])}</p>
<p class="meta">Verifica fattuale: non eseguita. Nessun verdetto attribuito.</p></div>"""
    correction = f'<div class="card"><p class="eyebrow">Cronologia / esempio</p><p>{escape(SAMPLE["correction"])}</p><a href="?view=trace">Vedi la traccia →</a></div>'
    if variant == "atlante":
        return f"""<div class="atlas-statement"><p class="eyebrow">Dichiarazione / esempio inventato</p><h1>Le parole, poi le prove.</h1>{details}
<div class="atlas-detail"><div>{source}</div><div>{summary}</div></div><div class="rule">{correction}</div></div>"""
    return f"""<p class="shelf-label">Scheda 001 / esercitazione senza contenuti reali</p><h1>Dichiarazione e documento</h1>
<div class="library-record"><aside><p class="shelf-label">Catalogazione</p><p><strong>Autore:</strong> {escape(SAMPLE['speaker'])}</p>
<p><strong>Data:</strong> {escape(SAMPLE['date'])}</p><p><strong>Fonte:</strong> {escape(SAMPLE['source'])}</p>
<a href="?view=source">Consulta la scheda della fonte →</a></aside><article>{details}<div class="source-slip"><strong>Sintesi (non citazione)</strong><p>{escape(SAMPLE['summary'])}</p>
<p class="meta">Verifica fattuale: non eseguita.</p></div>{correction}</article></div>"""


def intersection(variant: str) -> str:
    content = card("Incrocio dimostrativo", f"{escape(SAMPLE['speaker'])} × {escape(SAMPLE['topic'])}. Una sola citazione inventata e datata, senza giudizi sulla persona.", "statement")
    return f"""<p class="eyebrow">Persona × Tema / fixture</p><h1>{'Una persona. Un tema. Le parole.' if variant == 'atlante' else 'Registro per persona e argomento'}</h1>
<p class="lead">{escape(SAMPLE['speaker'])} · {escape(SAMPLE['topic'])}</p>{content}<p class="meta">Nessuna sintesi sulla posizione reale di persone esistenti.</p>"""


def source(variant: str) -> str:
    return f"""<p class="eyebrow">Contenuto / fixture</p><h1>{'La fonte al centro' if variant == 'biblioteca' else 'Risali alla fonte'}</h1>
<p class="lead">{escape(SAMPLE['source'])}</p><div class="grid">{card('Documento inventato', 'Localizzatore: pagina 2. Nessun PDF o filmato reale viene distribuito.')}
{card('Dichiarazione associata', escape(SAMPLE['quote']), 'statement')}</div>
<p class="meta">Nel prodotto reale questa pagina collegherà il testo esatto al documento/versione con permesso verificato.</p>"""


def trace(variant: str) -> str:
    return f"""<p class="eyebrow">Traccia e correzione / fixture</p><h1>{'Le parole cambiano, la storia resta.' if variant == 'atlante' else 'Registro delle versioni'}</h1>
<ol class="trail"><li>12 ottobre 2026: esempio originale, mai pubblicato</li><li>13 ottobre 2026: correzione dimostrativa, mai pubblicata</li></ol>
<div class="card"><p>{escape(SAMPLE['correction'])}</p><a href="?view=statement">Torna alla dichiarazione →</a></div>"""


def render(variant: str) -> str:
    assert variant in ("atlante", "biblioteca")
    nav = "".join(f'<a href="?view={v}" data-view-link="{v}">{escape(label)}</a>' for v, label in VIEWS)
    pages = {
        "home": home(variant), "explore": explore(variant),
        "statement": statement(variant), "intersection": intersection(variant),
        "source": source(variant), "trace": trace(variant),
    }
    panels = "".join(f'<section class="pane" id="{key}" data-panel="{key}" hidden aria-label="{escape(dict(VIEWS)[key])}">{page}</section>' for key, page in pages.items())
    # Do not let a no-JS screenshot misrepresent these as real records.
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>DP-441 · {variant} · anteprima non pubblicabile</title>
<style>{BASE}\n{ATLAS if variant == 'atlante' else LIBRARY}</style></head><body>
<a class="skip" href="#main">Vai al contenuto</a><div class="flag">PROTOTIPO NON PUBBLICABILE · CORPUS ZERO · DATI INVENTATI NELLE SCHEDE DI ESEMPIO</div>
<div class="site"><header class="masthead"><a class="brand" href="?view=home">Dichiarazioni Pubbliche</a><small>Scelta visiva in attesa · {variant.capitalize()}</small></header>
<nav class="view-nav" aria-label="Schermate comparabili">{nav}</nav><main id="main">{panels}</main>
<footer class="foot">Prototipo offline DP-441. Nessuna registrazione, verifica o autorizzazione a pubblicare. <a href="{'biblioteca' if variant == 'atlante' else 'atlante'}.html?view=home">Confronta l'altra versione</a>.</footer></div>
<script>
const known = new Set({['home','explore','statement','intersection','source','trace']!r});
const query = new URLSearchParams(location.search);
const view = known.has(query.get('view')) ? query.get('view') : 'home';
document.querySelectorAll('[data-panel]').forEach(node => node.hidden = node.dataset.panel !== view);
document.querySelectorAll('[data-view-link]').forEach(node => {{if(node.dataset.viewLink === view) node.setAttribute('aria-current','page');}});
</script></body></html>""".replace("['home', 'explore', 'statement', 'intersection', 'source', 'trace']", "['home','explore','statement','intersection','source','trace']")


def comparison() -> str:
    """Present equivalent route states side by side, without choosing for the owner."""
    tabs = "".join(
        f'<button type="button" data-view="{view}" aria-pressed="{str(view == "home").lower()}">{escape(label)}</button>'
        for view, label in VIEWS
    )
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>DP-441 · confronto tra design candidati</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;font:16px/1.5 system-ui,sans-serif;background:#e9e8e4;color:#182d36}}
header{{background:#fff;padding:20px 24px;border-bottom:1px solid #bac3c5}}h1{{font:600 clamp(1.5rem,3vw,2.7rem)/1.15 Georgia,serif;margin:0 0 8px}}p{{margin:0}}
nav{{display:flex;gap:8px;flex-wrap:wrap;padding:16px 24px}}button{{padding:12px;border:1px solid #5a7077;background:#fff;color:#18323c;cursor:pointer;min-height:44px}}button[aria-pressed=true]{{background:#163a4b;color:#fff}}
button:focus-visible,a:focus-visible{{outline:3px solid #ad4d11;outline-offset:3px}}
.compare{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 16px 24px}}
.variant{{min-width:0;background:white;border:1px solid #bac3c5}}.variant h2{{font-size:1rem;margin:0;padding:12px 16px}}
.variant iframe{{display:block;width:100%;height:780px;border:0;border-top:1px solid #bac3c5}}
.tip{{padding:0 24px 22px;font-size:.88rem}}
@media(max-width:800px){{.compare{{grid-template-columns:1fr}}.variant iframe{{height:650px}}}}
</style></head><body><header><h1>Due percorsi, gli stessi dati.</h1>
<p>DP-441 · confronto visivo offline · contenuti reali assenti, esempi inventati e marcati.</p></header>
<nav aria-label="Confronta la stessa schermata">{tabs}</nav><div class="compare"><div class="variant"><h2>A · Atlante delle parole</h2>
<iframe id="a" title="Proposta A — Atlante" src="atlante.html?view=home"></iframe></div>
<div class="variant"><h2>B · Biblioteca delle fonti</h2>
<iframe id="b" title="Proposta B — Biblioteca" src="biblioteca.html?view=home"></iframe></div></div>
<p class="tip">Per controllare la vista mobile apri <a href="atlante.html">Atlante</a> o <a href="biblioteca.html">Biblioteca</a> in una scheda a 320/390 px. Nessuna delle alternative è stata scelta.</p>
<script>
document.querySelectorAll('button[data-view]').forEach(button=>button.addEventListener('click',()=>{{
 const view=button.dataset.view;
 document.querySelectorAll('button[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 document.getElementById('a').src='atlante.html?view='+view;
 document.getElementById('b').src='biblioteca.html?view='+view;
}}));
</script></body></html>"""


if __name__ == "__main__":
    for kind in ("atlante", "biblioteca"):
        page = render(kind)
        (DEST / f"{kind}.html").write_text(page, encoding="utf-8")
        print(f"{kind}.html: {len(page.encode('utf-8'))} bytes")
    page = comparison()
    (DEST / "compare.html").write_text(page, encoding="utf-8")
    print(f"compare.html: {len(page.encode('utf-8'))} bytes")
