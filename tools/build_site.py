#!/usr/bin/env python3
"""Builds the easypdf.surf site in English and Spanish.

Two independent pages are written (``site/index.html`` and
``site/en/index.html``) rather than translating with JavaScript: each language
gets its own URL, its own ``lang`` attribute and its own ``hreflang``, which is
what search engines understand. ``robots.txt`` and ``sitemap.xml`` are
generated too.

Usage:  python tools/build_site.py
"""

from __future__ import annotations

import datetime
import html
import json
import os
import pathlib
from string import Template

import build_tools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
TEMPLATE = os.path.join(ROOT, "tools", "site_template.html")

DOMAIN = "https://easypdf.surf"
REPO = "https://github.com/mefardales/easypdf"


def _read_version() -> str:
    """Read __version__ from src/easypdf/__init__.py without importing the package.

    Importing it would drag in PySide6, which the site build does not need.
    """
    import re

    path = pathlib.Path(__file__).resolve().parent.parent / "src" / "easypdf" / "__init__.py"
    found = re.search(r'__version__\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"))
    if not found:
        raise RuntimeError(f"__version__ not found in {path}")
    return found.group(1)
#: The downloads point at the release files, not at the repository ones:
#: GitHub only counts downloads of releases, and the front page counter comes
#: from that number.
#: The version comes from the package itself, the single source. That way the
#: download links always point at the release just published and the site is
#: never left offering old binaries.
VERSION = _read_version()
DOWNLOADS_URL = f"{REPO}/releases/download/v{VERSION}"

#: Where the numbers shown on the front page come from.
#:
#: * Downloads: GitHub counts them on every file of a release. It is a real
#:   figure from the server, it cannot be faked from the browser.
#: * Visits: a public, cookie-free counter (counterapi.dev). It stores nothing
#:   about who visits: it just adds one. If real analytics are ever preferred,
#:   changing these two constants is enough.
RELEASES_API = "https://api.github.com/repos/mefardales/easypdf/releases"
VISITS_API = "https://api.counterapi.dev/v1/easypdf-surf"

FILES = {
    "setup": f"{DOWNLOADS_URL}/EasyPDF-{VERSION}-Setup.exe",
    "portable": f"{DOWNLOADS_URL}/EasyPDF-{VERSION}-windows-x64-portable.zip",
    "linux": f"{DOWNLOADS_URL}/EasyPDF-{VERSION}-linux-x64.tar.xz",
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
        "nav_features": "Features",
        "nav_tools": "Tools",
        "nav_download": "Downloads",
        "nav_cta": "Get it",
        "nav_how": "How it works",
        "nav_faq": "FAQ",
        "theme": "Switch between light and dark",
        "stat_downloads": "downloads",
        "stat_today": "visits today",
        "stat_total": "visits",
        "h1": "Read, annotate and print your PDFs",
        "h1_html": "Write <em>on top</em> of your PDFs",
        "switch": "Espanol",
        "how_kicker": "In one minute",
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
        "warn_short": "If Windows warns about an unknown publisher, click <b>More info</b> then <b>Run anyway</b>: the app is not signed with a paid certificate.",
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
            ("My antivirus deleted the file. Is it dangerous?",
             "No. It is a false alarm that hits small programs built with Python "
             "and not signed with a paid certificate. You can restore the file "
             "from your antivirus quarantine, and check it arrived intact with "
             "the .sha256 file next to the download. The whole source code is "
             "public, so anyone can inspect it."),
            ("How do I get new versions?",
             "The program checks on its own and tells you when there is one. "
             "From that notice you can download and install it without leaving "
             "the app. You can also turn the check off in the Help menu."),
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
        "nav_features": "Funciones",
        "nav_tools": "Herramientas",
        "nav_download": "Descargas",
        "nav_cta": "Descargar",
        "nav_how": "Como funciona",
        "nav_faq": "Preguntas",
        "theme": "Cambiar entre claro y oscuro",
        "stat_downloads": "descargas",
        "stat_today": "visitas hoy",
        "stat_total": "visitas",
        "h1": "Lee, anota e imprime tus PDF",
        "h1_html": "Escribe <em>encima</em> de tus PDF",
        "switch": "English",
        "how_kicker": "En un minuto",
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
        "warn_short": "Si Windows avisa de un editor desconocido, pulsa <b>Mas informacion</b> y <b>Ejecutar de todas formas</b>: el programa no esta firmado con un certificado de pago.",
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
            ("El antivirus me ha borrado el archivo. Es peligroso?",
             "No. Es una falsa alarma que les pasa a los programas pequenos hechos "
             "con Python y sin un certificado de pago. Puedes recuperar el archivo "
             "desde la cuarentena del antivirus, y comprobar que llego intacto con "
             "el archivo .sha256 que hay junto a la descarga. El codigo es publico, "
             "asi que cualquiera puede revisarlo."),
            ("Como me llegan las versiones nuevas?",
             "El programa lo mira solo y avisa cuando hay una. Desde ese aviso "
             "se descarga y se instala sin salir de la aplicacion. Y si "
             "prefieres que no lo mire, se apaga en el menu Ayuda."),
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

# Line icons, 20x20, for the feature list.
ICONS = {
    "read": '<path d="M3 5.2A1.2 1.2 0 0 1 4.2 4H9a3 3 0 0 1 3 3v11a2.4 2.4 0 0 0-2.4-2H4.2A1.2 1.2 0 0 1 3 14.8Z"/><path d="M21 5.2A1.2 1.2 0 0 0 19.8 4H15a3 3 0 0 0-3 3v11a2.4 2.4 0 0 1 2.4-2h5.4A1.2 1.2 0 0 0 21 14.8Z"/>',
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
    other = TEXTS[t["other_lang"]]
    base = f"{DOMAIN}/{t['path']}"
    prefix = "../" if t["path"] else ""

    features = "\n".join(
        "        <li>\n"
        f'          <svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[key]}</svg>\n'
        f"          <div><b>{esc(title)}</b><span>{esc(text)}</span></div>\n"
        "        </li>"
        for key, title, text in t["features"]
    )

    downloads = "\n".join(
        f'        <a class="dl" href="{FILES[key]}">\n'
        f'          <span class="dl-os">{esc(title)}</span>\n'
        f'          <span class="dl-note">{esc(detail)}</span>\n'
        f'          <span class="dl-size">{esc(size)}</span>\n'
        '          <span class="dl-go" aria-hidden="true">&darr;</span>\n'
        "        </a>"
        for key, title, detail, size in t["downloads"]
    )

    faq = "\n".join(
        "        <details>\n"
        f"          <summary>{esc(question)}</summary>\n"
        f"          <p>{esc(response)}</p>\n"
        "        </details>"
        # All of them, not just the first four: the structured data below
        # declares the whole list, and Google asks that what is declared be
        # visible on the page. As folded <details> they add no length.
        for question, response in t["faq"]
    )

    app_data = {
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
        "image": f"{DOMAIN}/screenshot.png",
        "license": "https://www.gnu.org/licenses/agpl-3.0.html",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
        "inLanguage": ["en", "es"],
    }
    faq_data = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": pregunta,
                "acceptedAnswer": {"@type": "Answer", "text": response},
            }
            for pregunta, response in t["faq"]
        ],
    }

    template = Template(open(TEMPLATE, encoding="utf-8").read())
    return template.safe_substitute(
        lang=t["lang"],
        title=esc(t["title"]),
        OTHER_LANG=other["lang"].upper(),
        url_setup=FILES["setup"],
        description=esc(t["description"]),
        keywords=esc(t["keywords"]),
        base=base,
        domain=DOMAIN,
        prefix=prefix,
        locale="en_US" if lang == "en" else "es_ES",
        json_app=json.dumps(app_data, ensure_ascii=False),
        json_faq=json.dumps(faq_data, ensure_ascii=False),
        skip=esc(t["skip"]),
        home="../" if t["path"] else "./",
        nav_features=esc(t["nav_features"]),
        nav_tools=esc(t["nav_tools"]),
        tools_url=build_tools._url(lang),
        nav_download=esc(t["nav_download"]),
        nav_cta=esc(t["nav_cta"]),
        other_lang=other["lang"],
        other_path=other["path"],
        other_name=esc(other["switch"]),
        theme=esc(t["theme"]),
        version=VERSION,
        h1=t["h1_html"],
        sub=esc(t["sub"]),
        cta=esc(t["cta"]),
        cta_note=esc(t["cta_note"]),
        cta_second=esc(t["cta_second"]),
        stat_downloads=esc(t["stat_downloads"]),
        stat_today=esc(t["stat_today"]),
        alt=esc(t["shot_alt"]),
        features_title=esc(t["features_title"]),
        features=features,
        downloads_title=esc(t["downloads_title"]),
        downloads=downloads,
        mac=esc(t["mac"]),
        warn_short=t["warn_short"],
        faq_title=esc(t["faq_title"]),
        faq=faq,
        repo=REPO,
        footer_free=esc(t["footer_free"]),
        footer_source=esc(t["footer_source"]),
        footer_issues=esc(t["footer_issues_link"]),
        url_linux=json.dumps(FILES["linux"]),
        cta_linux=json.dumps(t["cta_linux"]),
        cta_note_linux=json.dumps(t["cta_note_linux"]),
        mac_json=json.dumps(t["mac"]),
        releases_api=json.dumps(RELEASES_API),
        visits_api=json.dumps(VISITS_API),
    )


def main() -> int:
    hoy = datetime.date.today().isoformat()
    for folder in ("es",):
        os.makedirs(os.path.join(SITE, folder), exist_ok=True)

    for lang, t in TEXTS.items():
        target = os.path.join(SITE, t["path"], "index.html")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(build_page(lang))
        print(f"Wrote {target}")

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
    # The tools pages: one URL per tool and language, each pointing at its
    # twin in the other language.
    for path in build_tools.urls():
        other = path.replace("/es/tools/", "/tools/") if path.startswith("/es/") \
            else path.replace("/tools/", "/es/tools/", 1)
        english, spanish = (other, path) if path.startswith("/es/") else (path, other)
        urls += f"""
  <url>
    <loc>{DOMAIN}{path}</loc>
    <lastmod>{hoy}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="en" href="{DOMAIN}{english}"/>
    <xhtml:link rel="alternate" hreflang="es" href="{DOMAIN}{spanish}"/>
  </url>"""

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
{urls}
</urlset>
"""
    with open(os.path.join(SITE, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write(sitemap)
    # The file the installed program reads to learn whether there is a new
    # version. It comes from the same source as the download links, so there is
    # nothing to update by hand.
    last_tick = {
        "version": VERSION,
        "url": DOMAIN,
        "setup": FILES["setup"],
        "portable": FILES["portable"],
        "linux": FILES["linux"],
    }
    with open(os.path.join(SITE, "latest.json"), "w", encoding="utf-8") as fh:
        json.dump(last_tick, fh, ensure_ascii=False, indent=2)
    print(f"Wrote latest.json (version {VERSION})")

    print("Wrote robots.txt and sitemap.xml")
    build_tools.build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
