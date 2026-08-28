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

#: De donde salen los numeros que se ensenan en la portada.
#:
#: * Descargas: las cuenta GitHub en cada archivo de una release. Es un numero
#:   real del servidor, no se puede falsear desde el navegador.
#: * Visitas: contador publico y sin cookies (counterapi.dev). No guarda nada
#:   de quien visita: solo suma uno. Si algun dia se prefiere una analitica de
#:   verdad, basta con cambiar estas dos constantes.
RELEASES_API = "https://api.github.com/repos/mefardales/easypdf/releases"
VISITS_API = "https://api.counterapi.dev/v1/easypdf-surf"

FILES = {
    "setup": f"{RAW}/EasyPDF-{VERSION}-Setup.exe",
    "portable": f"{RAW}/EasyPDF-{VERSION}-windows-x64-portable.zip",
    "linux": f"{RAW}/EasyPDF-{VERSION}-linux-x64.tar.xz",
}

TEXTS = {
    "en": {
        "lang": "en",
        "path": "",
        "other_lang": "es",
        "other_path": "es/",
        "title": "easypdf.surf - Free PDF reader with annotations and tables",
        "description": (
            "Open, read, annotate and print PDFs. Write on top, highlight, draw "
            "tables and drop in images. Free, no account, no ads. For Windows "
            "and Linux."
        ),
        "keywords": "free pdf reader, annotate pdf, edit pdf, fill pdf, pdf windows",
        "skip": "Skip to content",
        "nav_download": "Downloads",
        "nav_cta": "Get it",
        "nav_how": "How it works",
        "nav_faq": "FAQ",
        "theme": "Switch between light and dark",
        "badge": "for Windows and Linux",
        "stat_downloads": "downloads",
        "stat_today": "visits today",
        "stat_total": "visits",
        "h1": "Read, annotate and print your PDFs",
        "h1_html": "Write <em>on top</em> of your PDFs",
        "switch": "Espanol",
        "features_kicker": "Features",
        "how_kicker": "In one minute",
        "downloads_kicker": "Downloads",
        "cta_linux": "Download for Linux",
        "cta_note_linux": "Portable - 62 MB - Linux 64-bit",
        "sub": (
            "Write on top of the document, highlight what matters, add tables, "
            "arrows and images, then save or print it. Like Adobe Reader, only "
            "much simpler."
        ),
        "cta": "Download for Windows",
        "cta_note": "42 MB installer - Windows 10 and 11 - no admin rights needed",
        "cta_second": "Other downloads",
        "trust": "Genuinely free - Works offline - Your documents never leave your computer",
        "shot_alt": "easypdf.surf window showing an annotated report: highlight, box, arrow, note and table",
        "features_title": "What you actually need",
        "features_sub": "Six things done well, instead of two hundred buried in menus.",
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
    "es": {
        "lang": "es",
        "path": "es/",
        "other_lang": "en",
        "other_path": "",
        "title": "easypdf.surf - Lector de PDF gratis con anotaciones y tablas",
        "description": (
            "Abre, lee, anota e imprime PDF. Escribe encima, resalta, dibuja "
            "tablas y coloca imagenes. Gratis, sin cuentas y sin publicidad. "
            "Para Windows y Linux."
        ),
        "keywords": "lector pdf gratis, anotar pdf, editar pdf, rellenar pdf, pdf windows",
        "skip": "Ir al contenido",
        "nav_download": "Descargas",
        "nav_cta": "Descargar",
        "nav_how": "Como funciona",
        "nav_faq": "Preguntas",
        "theme": "Cambiar entre claro y oscuro",
        "badge": "para Windows y Linux",
        "stat_downloads": "descargas",
        "stat_today": "visitas hoy",
        "stat_total": "visitas",
        "h1": "Lee, anota e imprime tus PDF",
        "h1_html": "Escribe <em>encima</em> de tus PDF",
        "switch": "English",
        "features_kicker": "Funciones",
        "how_kicker": "En un minuto",
        "downloads_kicker": "Descargas",
        "cta_linux": "Descargar para Linux",
        "cta_note_linux": "Portable - 62 MB - Linux 64 bits",
        "sub": (
            "Escribe encima del documento, resalta lo importante, anade tablas, "
            "flechas e imagenes, y guarda o imprime el resultado. Como Adobe "
            "Reader, pero mucho mas simple."
        ),
        "cta": "Descargar para Windows",
        "cta_note": "Instalador de 42 MB - Windows 10 y 11 - sin permisos de administrador",
        "cta_second": "Otras descargas",
        "trust": "Gratis de verdad - Funciona sin internet - Tus documentos no salen de tu ordenador",
        "shot_alt": "Ventana de easypdf.surf con un informe anotado: resaltado, recuadro, flecha, nota y tabla",
        "features_title": "Lo que de verdad hace falta",
        "features_sub": "Seis cosas bien hechas, en vez de doscientas escondidas en menus.",
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
}

# Visuales pequenos que van dentro de las tarjetas: dibujados con SVG para que
# la pagina siga pesando unos pocos kB y se vea nitida en cualquier pantalla.
VISUALS = {
    "annotate": """
<svg viewBox="0 0 260 130" class="v" aria-hidden="true">
  <rect x="8" y="8" width="244" height="114" rx="8" class="v-paper"/>
  <rect x="26" y="30" width="120" height="9" rx="4" class="v-mark"/>
  <rect x="26" y="50" width="170" height="7" rx="3" class="v-line"/>
  <rect x="26" y="66" width="140" height="7" rx="3" class="v-line"/>
  <rect x="22" y="84" width="130" height="26" rx="5" class="v-box"/>
  <path d="M232 44 L176 92" class="v-arrow"/>
  <path d="M172 96 l16 -3 -4 -12 z" class="v-arrow-head"/>
</svg>""",
    "table": """
<svg viewBox="0 0 260 130" class="v" aria-hidden="true">
  <rect x="18" y="18" width="224" height="94" rx="6" class="v-grid"/>
  <path d="M18 48h224M18 80h224M92 18v94M166 18v94" class="v-grid-line"/>
  <rect x="30" y="28" width="44" height="8" rx="4" class="v-mark"/>
  <rect x="104" y="28" width="40" height="8" rx="4" class="v-mark"/>
  <rect x="178" y="28" width="34" height="8" rx="4" class="v-mark"/>
  <rect x="30" y="60" width="38" height="7" rx="3" class="v-line"/>
  <rect x="104" y="60" width="22" height="7" rx="3" class="v-line"/>
  <rect x="178" y="60" width="30" height="7" rx="3" class="v-line"/>
  <rect x="30" y="92" width="30" height="7" rx="3" class="v-line"/>
  <rect x="104" y="92" width="26" height="7" rx="3" class="v-line"/>
  <rect x="178" y="92" width="24" height="7" rx="3" class="v-line"/>
</svg>""",
    "template": """
<svg viewBox="0 0 260 130" class="v" aria-hidden="true">
  <rect x="46" y="10" width="150" height="106" rx="8" class="v-ghost"/>
  <rect x="58" y="16" width="150" height="106" rx="8" class="v-ghost2"/>
  <rect x="70" y="22" width="150" height="106" rx="8" class="v-paper"/>
  <rect x="86" y="40" width="72" height="9" rx="4" class="v-mark"/>
  <rect x="86" y="60" width="110" height="7" rx="3" class="v-line"/>
  <rect x="86" y="76" width="92" height="7" rx="3" class="v-line"/>
</svg>""",
    "pages": """
<svg viewBox="0 0 260 130" class="v" aria-hidden="true">
  <rect x="24" y="20" width="66" height="90" rx="6" class="v-paper"/>
  <rect x="98" y="20" width="66" height="90" rx="6" class="v-paper"/>
  <rect x="172" y="20" width="66" height="90" rx="6" class="v-ghost" stroke-dasharray="5 4"/>
  <path d="M205 52v26M192 65h26" class="v-plus"/>
</svg>""",
    "read": """
<svg viewBox="0 0 260 130" class="v" aria-hidden="true">
  <rect x="18" y="14" width="46" height="102" rx="5" class="v-ghost2"/>
  <rect x="26" y="22" width="30" height="26" rx="3" class="v-paper"/>
  <rect x="26" y="54" width="30" height="26" rx="3" class="v-paper"/>
  <rect x="26" y="86" width="30" height="26" rx="3" class="v-paper"/>
  <rect x="78" y="14" width="164" height="102" rx="6" class="v-paper"/>
  <rect x="94" y="34" width="86" height="9" rx="4" class="v-mark"/>
  <rect x="94" y="54" width="128" height="7" rx="3" class="v-line"/>
  <rect x="94" y="70" width="112" height="7" rx="3" class="v-line"/>
  <circle cx="196" cy="92" r="13" class="v-grid-line"/>
  <path d="M206 102l12 12" class="v-arrow"/>
</svg>""",
    "print": """
<svg viewBox="0 0 260 130" class="v" aria-hidden="true">
  <rect x="88" y="12" width="84" height="30" rx="4" class="v-paper"/>
  <rect x="66" y="42" width="128" height="42" rx="6" class="v-grid"/>
  <circle cx="176" cy="56" r="4" class="v-dot"/>
  <rect x="88" y="76" width="84" height="42" rx="4" class="v-paper"/>
  <rect x="100" y="88" width="52" height="6" rx="3" class="v-line"/>
  <rect x="100" y="100" width="40" height="6" rx="3" class="v-mark"/>
</svg>""",
    "private": """
<svg viewBox="0 0 260 130" class="v" aria-hidden="true">
  <rect x="94" y="52" width="72" height="52" rx="8" class="v-grid"/>
  <path d="M110 52V40a20 20 0 0 1 40 0v12" class="v-grid-line"/>
  <circle cx="130" cy="76" r="7" class="v-dot"/>
  <path d="M42 78h34M184 78h34" class="v-line-stroke"/>
</svg>""",
}


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def build_page(lang: str) -> str:
    t = TEXTS[lang]
    otro = TEXTS[t["other_lang"]]
    base = f"{DOMAIN}/{t['path']}"
    prefijo = "../" if t["path"] else ""

    visual_de = {
        "read": "read", "write": "annotate", "table": "table",
        "print": "print", "create": "pages", "template": "template",
    }
    grandes = {"write", "table"}
    tarjetas = "\n".join(
        f'''      <article class="card{' wide' if clave in grandes else ''}">
        <div class="card-txt">
          <h3>{esc(titulo)}</h3>
          <p>{esc(texto)}</p>
        </div>
        <div class="card-vis">{VISUALS[visual_de.get(clave, "annotate")]}</div>
      </article>'''
        for clave, titulo, texto in t["features"]
    )

    pasos = "\n".join(
        f'''      <li>
        <span class="num">{i:02d}</span>
        <b>{esc(titulo)}</b>
        <p>{esc(texto)}</p>
      </li>'''
        for i, (titulo, texto) in enumerate(t["how"], start=1)
    )

    descargas = "\n".join(
        f'''      <a class="dl" href="{FILES[clave]}">
        <span class="dl-os">{esc(titulo)}</span>
        <span class="dl-note">{esc(detalle)}</span>
        <span class="dl-size">{esc(peso)}</span>
        <span class="dl-go" aria-hidden="true">&darr;</span>
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

    trust = "".join(
        f'<span>{esc(x)}</span>' for x in t["trust"].split(" - ")
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
<meta name="theme-color" content="#0a0a0b">
<link rel="canonical" href="{base}">
<link rel="alternate" hreflang="en" href="{DOMAIN}/">
<link rel="alternate" hreflang="es" href="{DOMAIN}/es/">
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
    --bg:#08090b; --panel:#0f1116; --panel-2:#12151b; --line:#1e222b;
    --fg:#f4f6f8; --muted:#8b93a1; --accent:#ff3b30; --accent-2:#ff8a3d;
    --accent-fg:#0b0c0e; --paper:#e9edf3; --radius:16px;
  }}
  html[data-theme="light"]{{
    --bg:#ffffff; --panel:#fbfbfd; --panel-2:#f4f5f8; --line:#e6e8ee;
    --fg:#0b0d12; --muted:#61697a; --accent:#e5121a; --accent-2:#ff6a1a;
    --accent-fg:#ffffff; --paper:#ffffff;
  }}
  *{{box-sizing:border-box}}
  html{{scroll-behavior:smooth;-webkit-text-size-adjust:100%}}
  body{{
    margin:0;background:var(--bg);color:var(--fg);overflow-x:hidden;
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
    -webkit-font-smoothing:antialiased;
  }}
  a{{color:inherit;text-decoration:none}}
  .wrap{{max-width:1080px;margin:0 auto;padding:0 24px}}
  .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}}
  .skip{{position:absolute;left:-9999px}}
  .skip:focus{{left:14px;top:14px;background:var(--accent);color:var(--accent-fg);padding:9px 14px;border-radius:8px;z-index:9}}

  /* ---------- fondo ---------- */
  .glow{{position:fixed;inset:0;pointer-events:none;z-index:0;
    background:
      radial-gradient(680px 420px at 50% -80px, color-mix(in srgb,var(--accent) 26%,transparent), transparent 70%),
      radial-gradient(520px 380px at 88% 8%, color-mix(in srgb,var(--accent-2) 14%,transparent), transparent 70%);
    opacity:.55}}
  .grid-bg{{position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.35;
    background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);
    background-size:64px 64px;
    -webkit-mask-image:radial-gradient(760px 460px at 50% 0,#000,transparent 75%);
    mask-image:radial-gradient(760px 460px at 50% 0,#000,transparent 75%)}}
  header,main,footer{{position:relative;z-index:1}}

  /* ---------- cabecera ---------- */
  header{{position:sticky;top:0;z-index:6;border-bottom:1px solid transparent;transition:.2s}}
  header.stuck{{border-color:var(--line);background:color-mix(in srgb,var(--bg) 82%,transparent);
    backdrop-filter:saturate(180%) blur(12px)}}
  .bar{{display:flex;align-items:center;gap:10px;height:62px}}
  .brand{{display:flex;align-items:center;gap:9px;font-weight:650;letter-spacing:-.3px}}
  .brand img{{width:24px;height:24px}}
  nav{{margin-left:auto;display:flex;align-items:center;gap:4px}}
  nav .nl{{color:var(--muted);font-size:14.5px;padding:8px 11px;border-radius:9px}}
  nav .nl:hover{{color:var(--fg);background:var(--panel-2)}}
  .icon-btn{{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;
    border:1px solid var(--line);background:var(--panel);color:var(--fg);cursor:pointer;
    font-size:13px;font-weight:600;letter-spacing:.02em;opacity:.75}}
  .icon-btn:hover{{opacity:1;border-color:var(--muted)}}
  .nav-cta{{background:var(--fg);color:var(--bg);font-weight:600;font-size:14px;
    padding:9px 15px;border-radius:10px;margin-left:6px}}
  .nav-cta:hover{{opacity:.88}}
  @media (max-width:760px){{ nav .nl{{display:none}} }}

  /* ---------- portada ---------- */
  .hero{{padding:76px 0 0;text-align:center}}
  .badge{{display:inline-flex;align-items:center;gap:9px;border:1px solid var(--line);
    background:var(--panel);padding:6px 14px 6px 8px;border-radius:999px;font-size:13px;color:var(--muted)}}
  .badge b{{color:var(--fg);background:color-mix(in srgb,var(--accent) 16%,transparent);
    border:1px solid color-mix(in srgb,var(--accent) 34%,transparent);
    padding:2px 8px;border-radius:999px;font-size:11.5px;font-weight:600}}
  h1{{font-size:clamp(38px,7.2vw,74px);line-height:1.02;letter-spacing:-2.6px;
    font-weight:760;margin:26px auto 20px;max-width:15ch}}
  h1 em{{font-style:normal;background:linear-gradient(100deg,var(--accent),var(--accent-2));
    -webkit-background-clip:text;background-clip:text;color:transparent}}
  .sub{{font-size:clamp(16.5px,2.1vw,19px);color:var(--muted);max-width:600px;margin:0 auto 34px}}
  .actions{{display:flex;gap:12px;justify-content:center;align-items:center;flex-wrap:wrap}}
  .btn{{display:inline-flex;align-items:center;gap:10px;background:var(--accent);color:var(--accent-fg);
    font-weight:680;font-size:16.5px;padding:15px 26px;border-radius:12px;
    box-shadow:0 8px 30px color-mix(in srgb,var(--accent) 34%,transparent);
    transition:transform .16s,filter .16s}}
  .btn:hover{{transform:translateY(-2px);filter:brightness(1.07)}}
  .btn-2{{background:var(--panel);color:var(--fg);border:1px solid var(--line);
    font-weight:560;font-size:15.5px;padding:14px 20px;border-radius:12px}}
  .btn-2:hover{{border-color:var(--muted)}}
  .hint{{margin:16px 0 0;font-size:13.5px;color:var(--muted)}}
  .trust{{display:flex;gap:22px;justify-content:center;flex-wrap:wrap;margin:34px 0 0}}
  .trust span{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}}
  .trust span+span::before{{content:"/";margin-right:22px;opacity:.45}}

  .stats{{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin:26px 0 0}}
  .stat{{border:1px solid var(--line);background:var(--panel);border-radius:12px;
    padding:10px 18px;min-width:110px}}
  .stat dt{{font-size:22px;font-weight:700;letter-spacing:-.6px;
    font-variant-numeric:tabular-nums;line-height:1.15}}
  .stat dd{{margin:2px 0 0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}}

  /* ---------- captura ---------- */
  .shot{{margin:58px auto 0;max-width:1000px;border:1px solid var(--line);border-radius:14px;
    background:var(--panel);overflow:hidden;
    box-shadow:0 40px 90px -30px rgba(0,0,0,.7),0 0 0 1px color-mix(in srgb,var(--fg) 5%,transparent)}}
  .chrome{{display:flex;align-items:center;gap:7px;padding:11px 14px;border-bottom:1px solid var(--line);
    background:var(--panel-2)}}
  .chrome i{{width:10px;height:10px;border-radius:50%;background:var(--line);display:block}}
  .chrome b{{margin-left:10px;font-weight:500;font-size:12.5px;color:var(--muted)}}
  .shot img{{display:block;width:100%}}

  /* ---------- secciones ---------- */
  section{{padding:96px 0}}
  .head{{max-width:640px;margin-bottom:38px}}
  h2{{font-size:clamp(26px,3.6vw,38px);letter-spacing:-1.2px;line-height:1.12;margin:12px 0 10px;font-weight:720}}
  .lead{{color:var(--muted);margin:0;font-size:16.5px}}

  .bento{{display:grid;grid-template-columns:repeat(6,1fr);gap:16px}}
  .card{{grid-column:span 2;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
    padding:24px 24px 0;overflow:hidden;display:flex;flex-direction:column;min-height:250px;
    transition:border-color .18s,transform .18s}}
  .card:hover{{border-color:color-mix(in srgb,var(--accent) 45%,var(--line));transform:translateY(-2px)}}
  .card.wide{{grid-column:span 3}}
  .card h3{{margin:0 0 8px;font-size:17.5px;letter-spacing:-.3px}}
  .card p{{margin:0;color:var(--muted);font-size:14.8px}}
  .card-vis{{margin-top:auto;padding-top:20px}}
  .v{{width:100%;height:auto;display:block;border-radius:10px 10px 0 0}}
  .v-paper{{fill:var(--paper);stroke:var(--line)}}
  .v-ghost{{fill:none;stroke:var(--line);stroke-width:1.5}}
  .v-ghost2{{fill:var(--panel-2);stroke:var(--line)}}
  .v-grid{{fill:none;stroke:var(--line);stroke-width:1.5}}
  .v-grid-line{{fill:none;stroke:var(--line);stroke-width:1.2}}
  .v-line{{fill:var(--muted);opacity:.45}}
  .v-line-stroke{{stroke:var(--muted);opacity:.35;stroke-width:2;stroke-linecap:round}}
  .v-mark{{fill:var(--accent);opacity:.85}}
  .v-box{{fill:none;stroke:var(--accent);stroke-width:2}}
  .v-arrow{{stroke:var(--accent-2);stroke-width:2.4;fill:none;stroke-linecap:round}}
  .v-arrow-head{{fill:var(--accent-2)}}
  .v-plus{{stroke:var(--accent);stroke-width:2.4;stroke-linecap:round}}
  .v-dot{{fill:var(--accent)}}
  @media (max-width:900px){{
    .bento{{grid-template-columns:repeat(2,1fr)}}
    .card,.card.wide{{grid-column:span 2}}
  }}
  @media (max-width:560px){{
    .bento{{grid-template-columns:1fr}}
    .card,.card.wide{{grid-column:span 1}}
  }}

  ol.steps{{list-style:none;padding:0;margin:0;display:grid;gap:14px;
    grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}}
  ol.steps li{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px}}
  .num{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;
    color:var(--accent);letter-spacing:.1em}}
  ol.steps b{{display:block;margin:10px 0 6px;font-size:16.5px}}
  ol.steps p{{margin:0;color:var(--muted);font-size:14.8px}}
  .note{{margin-top:22px;border:1px solid var(--line);border-left:2px solid var(--accent-2);
    background:var(--panel);border-radius:12px;padding:16px 18px;font-size:14.6px;color:var(--muted)}}
  .note b{{color:var(--fg)}}

  .dl{{display:grid;grid-template-columns:1.1fr 2fr auto auto;align-items:center;gap:16px;
    background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:18px 20px;
    margin-bottom:10px;transition:border-color .16s,transform .16s}}
  .dl:hover{{border-color:color-mix(in srgb,var(--accent) 55%,var(--line));transform:translateY(-1px)}}
  .dl-os{{font-weight:640;font-size:16px}}
  .dl-note{{color:var(--muted);font-size:14.4px}}
  .dl-size{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px;color:var(--muted)}}
  .dl-go{{width:30px;height:30px;display:grid;place-items:center;border-radius:9px;
    border:1px solid var(--line);color:var(--accent);font-size:14px}}
  @media (max-width:640px){{
    .dl{{grid-template-columns:1fr auto}}
    .dl-note{{grid-column:1/-1;order:3}}
  }}

  details{{border-bottom:1px solid var(--line);padding:18px 2px}}
  details summary{{cursor:pointer;font-weight:600;font-size:16px;list-style:none;display:flex;justify-content:space-between;gap:16px}}
  details summary::-webkit-details-marker{{display:none}}
  details summary::after{{content:"+";color:var(--muted);font-weight:400}}
  details[open] summary::after{{content:"\2013"}}
  details p{{margin:12px 0 0;color:var(--muted);font-size:15.2px;max-width:70ch}}

  footer{{border-top:1px solid var(--line);padding:40px 0 60px;color:var(--muted);font-size:14.2px}}
  .foot{{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}}
  footer a:hover{{color:var(--fg)}}

  .reveal{{opacity:0;transform:translateY(14px)}}
  .reveal.in{{opacity:1;transform:none;transition:opacity .5s ease,transform .5s ease}}
  @media (prefers-reduced-motion:reduce){{.reveal{{opacity:1;transform:none}}}}
</style>
</head>
<body>
<div class="glow"></div><div class="grid-bg"></div>
<a class="skip" href="#main">{esc(t['skip'])}</a>

<header id="top">
  <div class="wrap bar">
    <a class="brand" href="{'../' if t['path'] else './'}">
      <img src="{prefijo}easypdf.png" alt="" width="24" height="24"> easypdf.surf
    </a>
    <nav>
      <a class="nl" href="#features">{esc(t['nav_how'])}</a>
      <a class="nl" href="#downloads">{esc(t['nav_download'])}</a>
      <a class="nl" href="#faq">{esc(t['nav_faq'])}</a>
      <a class="icon-btn" href="{DOMAIN}/{otro['path']}" hreflang="{otro['lang']}"
         lang="{otro['lang']}" title="{otro['lang'].upper()}">{otro['lang'].upper()}</a>
      <button class="icon-btn" id="theme" type="button"
              aria-label="{esc(t['theme'])}" title="{esc(t['theme'])}">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
             stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <g id="i-sun"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.6M12 19.4V22M2 12h2.6M19.4 12H22M4.9 4.9l1.9 1.9M17.2 17.2l1.9 1.9M19.1 4.9l-1.9 1.9M6.8 17.2l-1.9 1.9"/></g>
          <g id="i-moon" style="display:none"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></g>
        </svg>
      </button>
      <a class="nav-cta" href="#downloads">{esc(t['nav_cta'])}</a>
    </nav>
  </div>
</header>

<main id="main">
<div class="wrap hero">
  <span class="badge"><b>v{VERSION}</b> {esc(t['badge'])}</span>
  <h1>{t['h1_html']}</h1>
  <p class="sub">{esc(t['sub'])}</p>
  <div class="actions">
    <a class="btn" id="cta" href="{FILES['setup']}">
      <span aria-hidden="true">&#8595;</span><span id="cta-text">{esc(t['cta'])}</span>
    </a>
    <a class="btn-2" href="#downloads">{esc(t['cta_second'])}</a>
  </div>
  <p class="hint" id="cta-note">{esc(t['cta_note'])}</p>
  <div class="trust">{trust}</div>

  <dl class="stats" id="stats" hidden>
    <div class="stat" id="stat-dl" hidden><dt id="n-dl">-</dt><dd>{esc(t['stat_downloads'])}</dd></div>
    <div class="stat" id="stat-today" hidden><dt id="n-today">-</dt><dd>{esc(t['stat_today'])}</dd></div>
    <div class="stat" id="stat-total" hidden><dt id="n-total">-</dt><dd>{esc(t['stat_total'])}</dd></div>
  </dl>

  <figure class="shot reveal" style="margin-bottom:0">
    <div class="chrome"><i></i><i></i><i></i><b>easypdf.surf</b></div>
    <img src="{prefijo}captura.png" width="1280" height="860" alt="{esc(t['shot_alt'])}">
  </figure>
</div>

<section class="wrap" id="features">
  <div class="head reveal">
    <span class="mono">{esc(t['features_kicker'])}</span>
    <h2>{esc(t['features_title'])}</h2>
    <p class="lead">{esc(t['features_sub'])}</p>
  </div>
  <div class="bento reveal">
{tarjetas}
  </div>
</section>

<section class="wrap" id="how">
  <div class="head reveal">
    <span class="mono">{esc(t['how_kicker'])}</span>
    <h2>{esc(t['how_title'])}</h2>
  </div>
  <ol class="steps reveal">
{pasos}
  </ol>
  <div class="note reveal"><b>{esc(t['warn_title'])}</b>. {t['warn']}</div>
</section>

<section class="wrap" id="downloads">
  <div class="head reveal">
    <span class="mono">{esc(t['downloads_kicker'])}</span>
    <h2>{esc(t['downloads_title'])}</h2>
    <p class="lead">{esc(t['downloads_sub'])}</p>
  </div>
  <div class="reveal">
{descargas}
  </div>
  <p class="lead" style="margin-top:16px;font-size:14.5px">{esc(t['mac'])}</p>
</section>

<section class="wrap" id="faq">
  <div class="head reveal">
    <span class="mono">FAQ</span>
    <h2>{esc(t['faq_title'])}</h2>
  </div>
  <div class="reveal">
{faq}
  </div>
</section>
</main>

<footer>
  <div class="wrap foot">
    <div>
      <p><b style="color:var(--fg)">easypdf.surf {VERSION}</b> &middot; {esc(t['footer_free'])}.</p>
      <p>{esc(t['footer_warranty'])}</p>
    </div>
    <div>
      <p><a href="{REPO}">{esc(t['footer_source'])}</a></p>
      <p><a href="{REPO}/issues">{esc(t['footer_issues_link'])}</a></p>
      <p><a href="{DOMAIN}/{otro['path']}" hreflang="{otro['lang']}">{esc(otro['switch'])}</a></p>
    </div>
  </div>
</footer>

<script>
(function () {{
  var raiz = document.documentElement, boton = document.getElementById("theme");
  function pintar(modo) {{
    raiz.setAttribute("data-theme", modo);
    boton.innerHTML = modo === "dark" ? "\u263C" : "\u263D";
  }}
  var guardado = null;
  try {{ guardado = localStorage.getItem("tema"); }} catch (e) {{}}
  pintar(guardado || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
  boton.addEventListener("click", function () {{
    var nuevo = raiz.getAttribute("data-theme") === "dark" ? "light" : "dark";
    pintar(nuevo);
    try {{ localStorage.setItem("tema", nuevo); }} catch (e) {{}}
  }});

  var cabecera = document.getElementById("top");
  addEventListener("scroll", function () {{
    cabecera.classList.toggle("stuck", scrollY > 8);
  }}, {{passive:true}});

  var ua = navigator.userAgent || "", plat =
      (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
  var texto = document.getElementById("cta-text"), nota = document.getElementById("cta-note");
  if (/Linux/i.test(plat + ua) && !/Android/i.test(ua)) {{
    document.getElementById("cta").href = {json.dumps(FILES['linux'])};
    texto.textContent = {json.dumps(t['cta_linux'])};
    nota.textContent = {json.dumps(t['cta_note_linux'])};
  }} else if (/Mac/i.test(plat + ua)) {{
    nota.textContent = {json.dumps(t['mac'])};
  }}

  // ---- numeros de la portada -------------------------------------------
  // Si alguna peticion falla, el numero simplemente no aparece: nunca se
  // ensena una cifra inventada ni se rompe la pagina.
  var tira = document.getElementById("stats");
  function poner(caja, valor, texto) {{
    if (valor === null || valor === undefined || isNaN(valor)) return;
    document.getElementById(texto).textContent = Number(valor).toLocaleString();
    document.getElementById(caja).hidden = false;
    tira.hidden = false;
  }}
  function leerCache(clave) {{
    try {{
      var crudo = localStorage.getItem(clave);
      if (!crudo) return null;
      var dato = JSON.parse(crudo);
      return (Date.now() - dato.t) < 3600000 ? dato.v : null;
    }} catch (e) {{ return null; }}
  }}
  function recordar(clave, valor) {{
    try {{ localStorage.setItem(clave, JSON.stringify({{v: valor, t: Date.now()}})); }} catch (e) {{}}
  }}

  // Descargas: las cuenta GitHub en los archivos de cada release.
  var cacheDl = leerCache("dl");
  if (cacheDl !== null) {{
    poner("stat-dl", cacheDl, "n-dl");
  }} else {{
    fetch({json.dumps(RELEASES_API)}, {{headers: {{Accept: "application/vnd.github+json"}}}})
      .then(function (r) {{ return r.ok ? r.json() : null; }})
      .then(function (releases) {{
        if (!Array.isArray(releases)) return;
        var total = 0;
        releases.forEach(function (rel) {{
          (rel.assets || []).forEach(function (a) {{
            if (a.name && a.name.slice(-7) !== ".sha256") total += a.download_count || 0;
          }});
        }});
        recordar("dl", total);
        poner("stat-dl", total, "n-dl");
      }})
      .catch(function () {{}});
  }}

  // Visitas: contador publico sin cookies. Se suma una vez por dia y navegador.
  var hoy = new Date().toISOString().slice(0, 10);
  var yaContado = false;
  try {{ yaContado = localStorage.getItem("visita") === hoy; }} catch (e) {{}}
  var verbo = yaContado ? "" : "/up";
  function numero(dato) {{
    if (dato === null || typeof dato !== "object") return null;
    if (typeof dato.count === "number") return dato.count;
    if (typeof dato.value === "number") return dato.value;
    if (dato.data && typeof dato.data.up_count === "number") return dato.data.up_count;
    if (dato.data && typeof dato.data.count === "number") return dato.data.count;
    return null;
  }}
  function contar(clave, caja, texto) {{
    return fetch({json.dumps(VISITS_API)} + "/" + clave + (verbo || "/"))
      .then(function (r) {{ return r.ok ? r.json() : null; }})
      .then(function (d) {{ poner(caja, numero(d), texto); }})
      .catch(function () {{}});
  }}
  contar("visitas-" + hoy, "stat-today", "n-today");
  contar("visitas", "stat-total", "n-total");
  if (!yaContado) {{
    try {{ localStorage.setItem("visita", hoy); }} catch (e) {{}}
  }}

  if ("IntersectionObserver" in window) {{
    var obs = new IntersectionObserver(function (entradas) {{
      entradas.forEach(function (e) {{
        if (e.isIntersecting) {{ e.target.classList.add("in"); obs.unobserve(e.target); }}
      }});
    }}, {{rootMargin:"0px 0px -8% 0px"}});
    document.querySelectorAll(".reveal").forEach(function (el) {{ obs.observe(el); }});
  }} else {{
    document.querySelectorAll(".reveal").forEach(function (el) {{ el.classList.add("in"); }});
  }}
}})();
</script>
</body>
</html>
"""


def main() -> int:
    hoy = datetime.date.today().isoformat()
    for carpeta in ("es",):
        os.makedirs(os.path.join(SITE, carpeta), exist_ok=True)

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
    <priority>{'1.0' if lang == 'en' else '0.9'}</priority>
    <xhtml:link rel="alternate" hreflang="en" href="{DOMAIN}/"/>
    <xhtml:link rel="alternate" hreflang="es" href="{DOMAIN}/es/"/>
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
