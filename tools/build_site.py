#!/usr/bin/env python3
"""Genera la web de easypdf.surf en espanol e ingles.

Se escriben dos paginas independientes (``site/index.html`` y
``site/en/index.html``) en vez de traducir con JavaScript: cada idioma tiene su
propia URL, su etiqueta ``lang`` y sus ``hreflang``, que es lo que entienden los
buscadores. Tambien se generan ``robots.txt`` y ``sitemap.xml``.

Uso:  python tools/build_site.py
"""

from __future__ import annotations

import datetime
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")

DOMAIN = "https://easypdf.surf"
REPO = "https://github.com/mefardales/easypdf"
RAW = f"{REPO}/raw/main/build"
VERSION = "1.0.0"

FILES = {
    "setup": f"{RAW}/EasyPDF-{VERSION}-Setup.exe",
    "portable": f"{RAW}/EasyPDF-{VERSION}-windows-x64-portable.zip",
    "linux": f"{RAW}/EasyPDF-{VERSION}-linux-x64.tar.xz",
}

TEXTS = {
    "es": {
        "lang": "es",
        "path": "",
        "other_lang": "en",
        "other_path": "en/",
        "title": "easypdf.surf - Lector de PDF gratis con anotaciones y tablas",
        "description": (
            "Abre, lee, anota e imprime PDF. Escribe encima, resalta, dibuja "
            "tablas y coloca imagenes. Gratis, sin cuentas y sin publicidad. "
            "Para Windows y Linux."
        ),
        "keywords": "lector pdf gratis, anotar pdf, editar pdf, rellenar pdf, pdf windows",
        "skip": "Ir al contenido",
        "nav_download": "Descargas",
        "nav_how": "Como funciona",
        "nav_faq": "Preguntas",
        "theme": "Cambiar entre claro y oscuro",
        "eyebrow": "Software libre - sin cuentas, sin anuncios",
        "h1": "Lee, anota e imprime tus PDF",
        "sub": (
            "Escribe encima del documento, resalta lo importante, anade tablas, "
            "flechas e imagenes, y guarda o imprime el resultado. Como Adobe "
            "Reader, pero mucho mas simple."
        ),
        "cta": "Descargar para Windows",
        "cta_note": "Instalador - 42 MB - Windows 10 y 11",
        "cta_second": "Ver todas las descargas",
        "trust": "Gratis de verdad - Funciona sin internet - Tus documentos no salen de tu ordenador",
        "shot_alt": "Ventana de easypdf.surf con un informe anotado: resaltado, recuadro, flecha, nota y tabla",
        "features_title": "Todo lo que necesitas, nada mas",
        "features_sub": "Sin menus interminables ni funciones que nunca usaras.",
        "features": [
            ("read", "Leer comodo",
             "Pasa paginas, acerca la letra pequena y busca cualquier palabra del documento."),
            ("write", "Escribir encima",
             "Recuadra, subraya con marcador, anade flechas, notas de texto o dibuja a mano."),
            ("table", "Tablas e imagenes",
             "Coloca tablas con celdas que se escriben, y anade fotos, firmas o logotipos."),
            ("print", "Imprimir",
             "Con vista previa y seleccion de paginas. Lo que anotas es lo que sale en papel."),
            ("create", "Crear documentos",
             "Empieza con una hoja en blanco, anade las paginas que quieras y guarda el PDF."),
            ("template", "Plantillas",
             "Guarda tu membrete o tu tabla y vuelve a usarlos en otro documento con un clic."),
        ],
        "how_title": "Empezar cuesta un minuto",
        "how": [
            ("Descarga", "Pulsa el boton y guarda el archivo."),
            ("Instala", "Doble clic y siguiente, siguiente. No hace falta ser administrador."),
            ("Abre tu PDF", "Arrastralo a la ventana y empieza a escribir encima."),
        ],
        "warn_title": "Si Windows avisa de que el editor es desconocido",
        "warn": (
            "Pulsa <b>Mas informacion</b> y luego <b>Ejecutar de todas formas</b>. "
            "Ese aviso sale con todos los programas pequenos que no han pagado un "
            "certificado; no significa que el archivo tenga nada malo."
        ),
        "downloads_title": "Descargas",
        "downloads_sub": f"Version {VERSION}. No hace falta instalar nada mas.",
        "downloads": [
            ("setup", "Para Windows", "La opcion normal. Se instala como cualquier programa.", "42 MB"),
            ("portable", "Windows sin instalar", "No instala nada. Puedes llevarlo en un pendrive.", "60 MB"),
            ("linux", "Para Linux", "Se descomprime y se abre. Para 64 bits.", "62 MB"),
        ],
        "download_verb": "Descargar",
        "mac": "Por ahora no hay version para Mac.",
        "faq_title": "Preguntas rapidas",
        "faq": [
            ("Es gratis del todo?", "Si. No hay version de pago, ni suscripcion, ni limite de documentos."),
            ("Tengo que registrarme?", "No. Se abre y se usa, sin cuenta ni correo electronico."),
            ("Lleva publicidad?", "Ninguna. Y tampoco instala cosas raras de propina."),
            ("Funciona sin internet?", "Si. Solo hace falta conexion para descargarlo la primera vez."),
            ("Mis documentos se suben a algun sitio?", "No. Todo ocurre en tu ordenador."),
            ("Y si no me gusta?", "Se desinstala como cualquier otro programa, desde Configuracion."),
        ],
        "footer_free": "gratis y libre para todo el mundo",
        "footer_issues": "Algo no funciona o se te ocurre una mejora?",
        "footer_issues_link": "Cuentanoslo aqui",
        "footer_source": "Ver el codigo y la licencia",
        "footer_warranty": "Se ofrece tal cual, sin garantias.",
    },
    "en": {
        "lang": "en",
        "path": "en/",
        "other_lang": "es",
        "other_path": "",
        "title": "easypdf.surf - Free PDF reader with annotations and tables",
        "description": (
            "Open, read, annotate and print PDFs. Write on top, highlight, draw "
            "tables and drop in images. Free, no account, no ads. For Windows "
            "and Linux."
        ),
        "keywords": "free pdf reader, annotate pdf, edit pdf, fill pdf, pdf windows",
        "skip": "Skip to content",
        "nav_download": "Downloads",
        "nav_how": "How it works",
        "nav_faq": "FAQ",
        "theme": "Switch between light and dark",
        "eyebrow": "Open source - no accounts, no ads",
        "h1": "Read, annotate and print your PDFs",
        "sub": (
            "Write on top of the document, highlight what matters, add tables, "
            "arrows and images, then save or print it. Like Adobe Reader, only "
            "much simpler."
        ),
        "cta": "Download for Windows",
        "cta_note": "Installer - 42 MB - Windows 10 and 11",
        "cta_second": "See all downloads",
        "trust": "Genuinely free - Works offline - Your documents never leave your computer",
        "shot_alt": "easypdf.surf window showing an annotated report: highlight, box, arrow, note and table",
        "features_title": "Everything you need, nothing else",
        "features_sub": "No endless menus, no features you will never open.",
        "features": [
            ("read", "Comfortable reading",
             "Flip through pages, zoom in on small print and search any word in the document."),
            ("write", "Write on top",
             "Box things out, highlight, add arrows, text notes or draw freehand."),
            ("table", "Tables and images",
             "Drop in tables with typeable cells, plus photos, signatures or logos."),
            ("print", "Printing",
             "With preview and page ranges. What you annotate is what comes out on paper."),
            ("create", "Create documents",
             "Start from a blank page, add as many pages as you need and save the PDF."),
            ("template", "Templates",
             "Save your letterhead or table and reuse it in another document in one click."),
        ],
        "how_title": "One minute to get going",
        "how": [
            ("Download", "Hit the button and save the file."),
            ("Install", "Double click, next, next. No administrator rights needed."),
            ("Open your PDF", "Drag it onto the window and start writing on top."),
        ],
        "warn_title": "If Windows says the publisher is unknown",
        "warn": (
            "Click <b>More info</b> and then <b>Run anyway</b>. That warning shows "
            "up for every small program that has not paid for a certificate; it "
            "does not mean there is anything wrong with the file."
        ),
        "downloads_title": "Downloads",
        "downloads_sub": f"Version {VERSION}. Nothing else to install.",
        "downloads": [
            ("setup", "For Windows", "The usual choice. Installs like any other program.", "42 MB"),
            ("portable", "Windows, no install", "Installs nothing. Runs from a USB stick.", "60 MB"),
            ("linux", "For Linux", "Unpack and run. 64-bit.", "62 MB"),
        ],
        "download_verb": "Download",
        "mac": "There is no Mac build yet.",
        "faq_title": "Quick answers",
        "faq": [
            ("Is it really free?", "Yes. No paid version, no subscription, no document limit."),
            ("Do I need an account?", "No. Open it and use it, no sign-up, no email."),
            ("Are there ads?", "None. And it does not sneak in extra software either."),
            ("Does it work offline?", "Yes. You only need a connection to download it once."),
            ("Are my documents uploaded anywhere?", "No. Everything happens on your computer."),
            ("What if I do not like it?", "Uninstall it like any other program, from Settings."),
        ],
        "footer_free": "free and open for everyone",
        "footer_issues": "Something broken or an idea to share?",
        "footer_issues_link": "Tell us here",
        "footer_source": "See the code and the licence",
        "footer_warranty": "Provided as is, without warranty.",
    },
}

ICONS = {
    "read": '<path d="M3 5.5A1.5 1.5 0 0 1 4.5 4H9a3 3 0 0 1 3 3v11a2.5 2.5 0 0 0-2.5-2H4.5A1.5 1.5 0 0 1 3 14.5Z"/><path d="M21 5.5A1.5 1.5 0 0 0 19.5 4H15a3 3 0 0 0-3 3v11a2.5 2.5 0 0 1 2.5-2h5A1.5 1.5 0 0 0 21 14.5Z"/>',
    "write": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16M15 4v16"/>',
    "print": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M6 14h12v7H6z"/>',
    "create": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/><path d="M12 11v6M9 14h6"/>',
    "template": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',
}


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def build_page(lang: str) -> str:
    t = TEXTS[lang]
    otro = TEXTS[t["other_lang"]]
    base = f"{DOMAIN}/{t['path']}"
    prefijo = "../" if t["path"] else ""      # rutas a los archivos comunes

    tarjetas = "\n".join(
        f'''      <article class="card">
        <svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[clave]}</svg>
        <h3>{esc(titulo)}</h3>
        <p>{esc(texto)}</p>
      </article>'''
        for clave, titulo, texto in t["features"]
    )

    pasos = "\n".join(
        f'''      <li>
        <span class="step">{i}</span>
        <div><b>{esc(titulo)}</b><p>{esc(texto)}</p></div>
      </li>'''
        for i, (titulo, texto) in enumerate(t["how"], start=1)
    )

    descargas = "\n".join(
        f'''      <a class="row" href="{FILES[clave]}">
        <span class="row-main"><b>{esc(titulo)}</b><span>{esc(detalle)}</span></span>
        <span class="row-size">{esc(peso)}</span>
        <span class="row-cta">{esc(t["download_verb"])} &rarr;</span>
      </a>'''
        for clave, titulo, detalle, peso in t["downloads"]
    )

    faq = "\n".join(
        f'''      <details>
        <summary>{esc(pregunta)}</summary>
        <p>{esc(respuesta)}</p>
      </details>'''
        for pregunta, respuesta in t["faq"]
    )

    datos_app = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "easypdf.surf",
        "applicationCategory": "BusinessApplication",
        "applicationSubCategory": "PDF reader and annotator",
        "operatingSystem": "Windows 10, Windows 11, Linux",
        "softwareVersion": VERSION,
        "description": t["description"],
        "url": base,
        "downloadUrl": FILES["setup"],
        "image": f"{DOMAIN}/captura.png",
        "license": "https://www.gnu.org/licenses/agpl-3.0.html",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
        "inLanguage": ["es", "en"],
    }
    datos_faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": pregunta,
                "acceptedAnswer": {"@type": "Answer", "text": respuesta},
            }
            for pregunta, respuesta in t["faq"]
        ],
    }

    return f"""<!doctype html>
<html lang="{t['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t['title'])}</title>
<meta name="description" content="{esc(t['description'])}">
<meta name="keywords" content="{esc(t['keywords'])}">
<meta name="theme-color" content="#e5121a">
<link rel="canonical" href="{base}">
<link rel="alternate" hreflang="es" href="{DOMAIN}/">
<link rel="alternate" hreflang="en" href="{DOMAIN}/en/">
<link rel="alternate" hreflang="x-default" href="{DOMAIN}/">
<link rel="icon" href="{prefijo}easypdf.png" type="image/png">
<link rel="apple-touch-icon" href="{prefijo}easypdf.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="easypdf.surf">
<meta property="og:locale" content="{'es_ES' if lang == 'es' else 'en_US'}">
<meta property="og:url" content="{base}">
<meta property="og:title" content="{esc(t['title'])}">
<meta property="og:description" content="{esc(t['description'])}">
<meta property="og:image" content="{DOMAIN}/captura.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(t['title'])}">
<meta name="twitter:description" content="{esc(t['description'])}">
<meta name="twitter:image" content="{DOMAIN}/captura.png">
<script type="application/ld+json">{json.dumps(datos_app, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(datos_faq, ensure_ascii=False)}</script>
<style>
  :root{{
    --bg:#ffffff; --bg-soft:#f7f8fa; --line:#e5e8ec; --card:#ffffff;
    --fg:#0f1419; --muted:#5d6773; --accent:#e5121a; --accent-fg:#ffffff;
    --shadow:0 1px 2px rgba(15,20,25,.06), 0 12px 32px rgba(15,20,25,.07);
    --radius:14px;
  }}
  html[data-theme="dark"]{{
    --bg:#0d1117; --bg-soft:#131923; --line:#242c38; --card:#141b25;
    --fg:#e9eef5; --muted:#98a3b3; --accent:#ff4d4d; --accent-fg:#12161c;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 12px 32px rgba(0,0,0,.35);
  }}
  *{{box-sizing:border-box}}
  html{{scroll-behavior:smooth}}
  body{{
    margin:0; background:var(--bg); color:var(--fg);
    font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
    -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  }}
  a{{color:inherit}}
  .wrap{{max-width:1020px;margin:0 auto;padding:0 22px}}
  .skip{{position:absolute;left:-9999px}}
  .skip:focus{{left:12px;top:12px;background:var(--accent);color:var(--accent-fg);padding:8px 14px;border-radius:8px;z-index:9}}

  header{{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 88%,transparent);
    backdrop-filter:saturate(180%) blur(10px);border-bottom:1px solid var(--line)}}
  .bar{{display:flex;align-items:center;gap:14px;height:60px}}
  .brand{{display:flex;align-items:center;gap:9px;text-decoration:none;font-weight:700;letter-spacing:-.3px}}
  .brand img{{width:26px;height:26px}}
  nav{{margin-left:auto;display:flex;align-items:center;gap:6px}}
  nav a.link{{color:var(--muted);text-decoration:none;font-size:14.5px;padding:8px 10px;border-radius:8px}}
  nav a.link:hover{{color:var(--fg);background:var(--bg-soft)}}
  .chip{{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--card);
    color:var(--muted);font-size:13px;padding:6px 10px;border-radius:999px;text-decoration:none;cursor:pointer}}
  .chip:hover{{color:var(--fg);border-color:var(--muted)}}
  @media (max-width:640px){{ nav a.link{{display:none}} }}

  .hero{{padding:70px 0 10px;text-align:center}}
  .eyebrow{{display:inline-block;font-size:13px;color:var(--muted);border:1px solid var(--line);
    background:var(--bg-soft);padding:5px 12px;border-radius:999px;margin-bottom:22px}}
  h1{{font-size:clamp(34px,5.6vw,54px);line-height:1.08;letter-spacing:-1.6px;margin:0 0 16px}}
  .sub{{font-size:clamp(17px,2.2vw,19.5px);color:var(--muted);max-width:660px;margin:0 auto 32px}}
  .btn{{display:inline-flex;flex-direction:column;align-items:center;gap:2px;background:var(--accent);
    color:var(--accent-fg);text-decoration:none;font-weight:700;font-size:17.5px;padding:15px 30px;
    border-radius:12px;box-shadow:0 6px 18px color-mix(in srgb,var(--accent) 35%,transparent);
    transition:transform .15s ease, filter .15s ease}}
  .btn:hover{{transform:translateY(-1px);filter:brightness(1.06)}}
  .btn small{{font-weight:500;font-size:12.5px;opacity:.92}}
  .second{{display:block;margin-top:14px;font-size:14.5px;color:var(--muted)}}
  .trust{{margin-top:26px;font-size:13.5px;color:var(--muted)}}

  .shot{{margin:46px 0 10px}}
  .shot img{{width:100%;display:block;border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow)}}

  section{{padding:64px 0}}
  h2{{font-size:clamp(24px,3.2vw,30px);letter-spacing:-.7px;margin:0 0 8px}}
  .lead{{color:var(--muted);margin:0 0 30px}}
  .soft{{background:var(--bg-soft);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}

  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:16px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px}}
  .card svg{{width:22px;height:22px;fill:none;stroke:var(--accent);stroke-width:1.8;
    stroke-linecap:round;stroke-linejoin:round;margin-bottom:12px}}
  .card h3{{margin:0 0 6px;font-size:16.5px}}
  .card p{{margin:0;color:var(--muted);font-size:14.8px}}

  ol.steps{{list-style:none;padding:0;margin:0;display:grid;gap:14px}}
  ol.steps li{{display:flex;gap:14px;align-items:flex-start}}
  .step{{flex:none;width:28px;height:28px;border-radius:50%;background:var(--accent);color:var(--accent-fg);
    display:grid;place-items:center;font-size:14px;font-weight:700}}
  ol.steps p{{margin:2px 0 0;color:var(--muted);font-size:15px}}

  .note{{margin-top:26px;border:1px solid var(--line);border-left:3px solid #f0a500;background:var(--card);
    border-radius:10px;padding:16px 18px;font-size:14.8px;color:var(--muted)}}
  .note b{{color:var(--fg)}}

  .row{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;background:var(--card);
    border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:10px;
    text-decoration:none;transition:border-color .15s ease, transform .15s ease}}
  .row:hover{{border-color:var(--accent);transform:translateY(-1px)}}
  .row-main{{flex:1;min-width:220px;display:flex;flex-direction:column}}
  .row-main span{{color:var(--muted);font-size:14.3px}}
  .row-size{{color:var(--muted);font-size:14px;white-space:nowrap}}
  .row-cta{{color:var(--accent);font-weight:600;font-size:14.5px;white-space:nowrap}}

  details{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-bottom:10px}}
  details summary{{cursor:pointer;font-weight:600;list-style:none}}
  details summary::-webkit-details-marker{{display:none}}
  details summary::after{{content:"+";float:right;color:var(--muted)}}
  details[open] summary::after{{content:"\\2212"}}
  details p{{margin:10px 0 0;color:var(--muted);font-size:15px}}

  footer{{border-top:1px solid var(--line);padding:34px 0 54px;color:var(--muted);font-size:14.3px}}
  footer p{{margin:6px 0}}
  footer a{{color:var(--muted)}}
</style>
</head>
<body>
<a class="skip" href="#main">{esc(t['skip'])}</a>

<header>
  <div class="wrap bar">
    <a class="brand" href="{'../' if t['path'] else './'}">
      <img src="{prefijo}easypdf.png" alt="" width="26" height="26">
      easypdf.surf
    </a>
    <nav>
      <a class="link" href="#downloads">{esc(t['nav_download'])}</a>
      <a class="link" href="#how">{esc(t['nav_how'])}</a>
      <a class="link" href="#faq">{esc(t['nav_faq'])}</a>
      <a class="chip" href="{DOMAIN}/{otro['path']}" hreflang="{otro['lang']}"
         lang="{otro['lang']}">{otro['lang'].upper()}</a>
      <button class="chip" id="theme" type="button" aria-label="{esc(t['theme'])}"
              title="{esc(t['theme'])}"><span id="theme-icon">&#9788;</span></button>
    </nav>
  </div>
</header>

<main id="main">
<div class="wrap hero">
  <span class="eyebrow">{esc(t['eyebrow'])}</span>
  <h1>{esc(t['h1'])}</h1>
  <p class="sub">{esc(t['sub'])}</p>
  <a class="btn" id="cta" href="{FILES['setup']}">
    <span id="cta-text">{esc(t['cta'])}</span>
    <small id="cta-note">{esc(t['cta_note'])}</small>
  </a>
  <a class="second" href="#downloads">{esc(t['cta_second'])}</a>
  <p class="trust">{esc(t['trust'])}</p>
  <div class="shot">
    <img src="{prefijo}captura.png" width="1280" height="860" alt="{esc(t['shot_alt'])}">
  </div>
</div>

<section class="wrap">
  <h2>{esc(t['features_title'])}</h2>
  <p class="lead">{esc(t['features_sub'])}</p>
  <div class="grid">
{tarjetas}
  </div>
</section>

<section class="soft" id="how">
  <div class="wrap">
    <h2>{esc(t['how_title'])}</h2>
    <p class="lead"></p>
    <ol class="steps">
{pasos}
    </ol>
    <div class="note"><b>{esc(t['warn_title'])}</b>. {t['warn']}</div>
  </div>
</section>

<section class="wrap" id="downloads">
  <h2>{esc(t['downloads_title'])}</h2>
  <p class="lead">{esc(t['downloads_sub'])}</p>
{descargas}
  <p class="lead" style="margin-top:18px">{esc(t['mac'])}</p>
</section>

<section class="soft" id="faq">
  <div class="wrap">
    <h2>{esc(t['faq_title'])}</h2>
    <p class="lead"></p>
{faq}
  </div>
</section>
</main>

<footer>
  <div class="wrap">
    <p><b>easypdf.surf {VERSION}</b> - {esc(t['footer_free'])}.</p>
    <p>{esc(t['footer_issues'])} <a href="{REPO}/issues">{esc(t['footer_issues_link'])}</a>.</p>
    <p><a href="{REPO}">{esc(t['footer_source'])}</a> - {esc(t['footer_warranty'])}</p>
  </div>
</footer>

<script>
(function () {{
  // Tema: el del sistema por defecto, y se recuerda si se cambia a mano.
  var raiz = document.documentElement, icono = document.getElementById("theme-icon");
  function pintar(modo) {{
    raiz.setAttribute("data-theme", modo);
    icono.innerHTML = modo === "dark" ? "&#9789;" : "&#9788;";
  }}
  var guardado = null;
  try {{ guardado = localStorage.getItem("tema"); }} catch (e) {{}}
  pintar(guardado || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  document.getElementById("theme").addEventListener("click", function () {{
    var nuevo = raiz.getAttribute("data-theme") === "dark" ? "light" : "dark";
    pintar(nuevo);
    try {{ localStorage.setItem("tema", nuevo); }} catch (e) {{}}
  }});

  // El boton principal se adapta al sistema de quien visita la pagina.
  var ua = navigator.userAgent || "", plataforma =
      (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
  var boton = document.getElementById("cta"),
      texto = document.getElementById("cta-text"),
      nota = document.getElementById("cta-note");
  if (/Linux/i.test(plataforma + ua) && !/Android/i.test(ua)) {{
    boton.href = {json.dumps(FILES['linux'])};
    texto.textContent = {json.dumps(t['cta'].replace('Windows', 'Linux'))};
    nota.textContent = {json.dumps('62 MB - x86-64')};
  }} else if (/Mac/i.test(plataforma + ua)) {{
    nota.textContent = {json.dumps(t['mac'])};
  }}
}})();
</script>
</body>
</html>
"""


def main() -> int:
    hoy = datetime.date.today().isoformat()
    os.makedirs(os.path.join(SITE, "en"), exist_ok=True)

    for lang, t in TEXTS.items():
        destino = os.path.join(SITE, t["path"], "index.html")
        with open(destino, "w", encoding="utf-8") as fh:
            fh.write(build_page(lang))
        print(f"Escrito {destino}")

    robots = f"""User-agent: *
Allow: /

Sitemap: {DOMAIN}/sitemap.xml
"""
    with open(os.path.join(SITE, "robots.txt"), "w", encoding="utf-8") as fh:
        fh.write(robots)

    urls = "\n".join(
        f"""  <url>
    <loc>{DOMAIN}/{t['path']}</loc>
    <lastmod>{hoy}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{'1.0' if lang == 'es' else '0.9'}</priority>
    <xhtml:link rel="alternate" hreflang="es" href="{DOMAIN}/"/>
    <xhtml:link rel="alternate" hreflang="en" href="{DOMAIN}/en/"/>
  </url>"""
        for lang, t in TEXTS.items()
    )
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
{urls}
</urlset>
"""
    with open(os.path.join(SITE, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write(sitemap)
    print("Escritos robots.txt y sitemap.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
