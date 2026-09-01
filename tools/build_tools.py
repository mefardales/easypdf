#!/usr/bin/env python3
"""Builds the browser tools pages of easypdf.surf.

Six small tools that run entirely in the visitor's browser: merging, splitting,
rotating, deleting pages, images to PDF and PDF to image. Nothing is uploaded,
so they need no server - they are plain static pages like the rest of the site.

Each tool gets its own URL in each language (``/tools/merge-pdf/`` and
``/es/tools/merge-pdf/``), which is what search engines want, and the whole
thing is a PWA so it can be installed on a phone and used with no connection.

Called from tools/build_site.py; running this file on its own works too.
"""

from __future__ import annotations

import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
TEMPLATE = os.path.join(ROOT, "tools", "tool_template.html")
DOMAIN = "https://easypdf.surf"
REPO = "https://github.com/mefardales/easypdf"

#: Where each language lives, relative to the site root.
LANGS = {"en": "", "es": "es/"}


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


# ------------------------------------------------------------------- icons
#: One line icon per tool, 22x22, drawn on the same grid as the landing ones.
ICONS = {
    "merge-pdf": '<path d="M8 3H5a2 2 0 0 0-2 2v6"/><path d="M3 13v6a2 2 0 0 0 2 2h3"/>'
                 '<rect x="11" y="7" width="10" height="10" rx="2"/><path d="M8 12h3"/>',
    "split-pdf": '<rect x="3" y="3" width="8" height="8" rx="1.6"/>'
                 '<rect x="3" y="13" width="8" height="8" rx="1.6"/>'
                 '<path d="M14 7h7M14 17h7M18 4v6M18 14v6"/>',
    "organize-pdf": '<rect x="3" y="4" width="7" height="16" rx="1.6"/>'
                    '<rect x="14" y="4" width="7" height="16" rx="1.6"/>'
                    '<path d="m11.4 9 1.6 1.6-1.6 1.6"/>',
    "delete-pages": '<path d="M4 6h16"/><path d="M9 6V4h6v2"/>'
                    '<path d="M6 6l1 14h10l1-14"/><path d="M10 10v7M14 10v7"/>',
    # Two pictures going into a page, and a page coming out as a picture: the
    # arrow is what tells them apart at 22 px.
    "images-to-pdf": '<rect x="2.5" y="5" width="9" height="9" rx="1.6"/>'
                     '<circle cx="5.6" cy="8.2" r="1"/><path d="m3 12.6 2.6-2.6 3 3"/>'
                     '<path d="M14 12h5"/><path d="m16.6 9.4 2.6 2.6-2.6 2.6"/>'
                     '<path d="M13.5 4.5h6a1.5 1.5 0 0 1 1.5 1.5"/>'
                     '<path d="M21 18a1.5 1.5 0 0 1-1.5 1.5h-6"/>',
    "pdf-to-image": '<path d="M9.5 4.5h-5A1.5 1.5 0 0 0 3 6v12a1.5 1.5 0 0 0 1.5 1.5h5"/>'
                    '<path d="M6 8h2M6 11h2"/>'
                    '<path d="M10 12h3.4"/><path d="m11.6 9.4 2.6 2.6-2.6 2.6"/>'
                    '<rect x="14.5" y="5" width="7" height="7" rx="1.4"/>'
                    '<circle cx="16.9" cy="7.6" r=".9"/><path d="m14.9 10.9 2.2-2.2 2.4 2.4"/>',
}


def icon(slug: str, size: int = 22) -> str:
    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
        f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{ICONS[slug]}</svg>'
    )


UPLOAD_ICON = (
    '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" '
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 16V4"/><path d="m7.5 8.5 4.5-4.5 4.5 4.5"/>'
    '<path d="M4 15v3.5A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.5-2.5V15"/></svg>'
)


# ------------------------------------------------------------------- texts
#: Everything the pages say, in both languages. The ``js`` block is handed to
#: app.js as window.T; the rest fills the template.
TEXTS = {
    "en": {
        "skip": "Skip to the content",
        "nav_tools": "Tools",
        "nav_download": "Download the app",
        "theme": "Light or dark",
        "other_name": "En espanol",
        "other_lang": "es",
        "crumb_home": "Home",
        "crumb_tools": "Tools",
        "privacy": "Your files stay on this device. Nothing is uploaded.",
        "noscript": "These tools work in your browser, so they need JavaScript "
                    "switched on. Nothing is sent anywhere either way.",
        "footer_privacy": "Every one of these tools runs in your browser. Your "
                          "documents are never uploaded, and there is no account "
                          "and no advertising.",
        "footer_home": "easypdf.surf",
        "footer_source": "Source code",
        "footer_libs": 'Built with <a href="/tools/vendor/pdf-lib.LICENSE.md">pdf-lib</a> (MIT) and <a href="/tools/vendor/pdfjs.LICENSE">pdf.js</a> (Apache 2.0), both served from this site.',
        "hub_title": "Free PDF tools that run in your browser - easypdf.surf",
        "hub_description": "Merge, split, rotate, delete pages and convert PDFs and "
                           "images. Free, no account, and your files never leave "
                           "your device.",
        "hub_h1": "PDF tools",
        "hub_lede": "Six things people need most often, done right here in the "
                    "browser. No account, no upload, no waiting.",
        "hub_install": "Add it to your phone's home screen and it works with no "
                       "connection.",
        "hub_more_title": "Need to do more?",
        "hub_more": "The easypdf.surf application writes on top of your PDFs, fills "
                    "in forms, erases what is underneath and prints. It is free too.",
        "hub_more_cta": "Download the application",
        "next_title": "Something else with your PDF",
        "js": {
            "page": "Page",
            "download": "Download",
            "again": "Do another one",
            "drag": "Drag to reorder",
            "reading": "Reading the file...",
            "working": "Working...",
            "rendering": "Page {0} of {1}...",
            "done": "Done",
            "done_title": "Ready",
            "done_merge": "Your PDFs, one after another in the order above.",
            "done_split": "The pages you asked for, in one PDF.",
            "done_split_many": "{0} PDFs, one per page, together in a zip.",
            "done_organize": "The pages in the new order, with the turns applied.",
            "done_delete": "{0} pages removed.",
            "done_images": "Your images, one per page.",
            "done_image_one": "The page as an image.",
            "done_image_many": "{0} images, together in a zip.",
            "need_two": "Add at least two PDFs.",
            "n_files": "{0} files",
            "n_images": "{0} images",
            "n_pages": "{0} pages will be kept",
            "n_pages_doc": "{0} pages",
            "remove": "Remove",
            "rotate": "Turn",
            "move_left": "Move back",
            "move_right": "Move forward",
            "move_up": "Move up",
            "move_down": "Move down",
            "err_read": "The file could not be read.",
            "err_lib": "Something did not load. Check your connection and try again.",
            "err_pdf": "That does not look like a readable PDF.",
            "err_locked": "That PDF has a password. Open it in the application first.",
            "err_not_pdf": "Only PDF files, please.",
            "err_not_image": "Only JPG or PNG images, please.",
            "err_range": "'{0}' is not a page range.",
            "err_no_pages": "That range leaves no pages.",
            "err_all_gone": "Keep at least one page.",
        },
        "tools": {
            "merge-pdf": {
                "name": "Merge PDF",
                "card": "Several PDFs into one, in the order you choose.",
                "title": "Merge PDF files free, in your browser - easypdf.surf",
                "description": "Join several PDFs into one. Free, no account, and "
                               "your files never leave your device.",
                "h1": "Merge PDF",
                "lede": "Put several PDFs together into a single file. Drag them "
                        "into the order you want first.",
                "drop_b": "Choose your PDFs",
                "drop_s": "or drop them here",
                "go": "Merge",
            },
            "split-pdf": {
                "name": "Split PDF",
                "card": "Pull out the pages you need, or one file per page.",
                "title": "Split a PDF or extract pages free - easypdf.surf",
                "description": "Take the pages you need out of a PDF, or break it "
                               "into one file per page. Nothing is uploaded.",
                "h1": "Split PDF",
                "lede": "Take out the pages you need, or break the document into "
                        "one file per page.",
                "drop_b": "Choose a PDF",
                "drop_s": "or drop it here",
                "go": "Split",
                "mode": "What do you want",
                "mode_range": "These pages",
                "mode_each": "One file per page",
                "range_label": "Pages",
                "range_hint": "Like 1-3, 8, 12- . Leave it empty for all of them.",
            },
            "organize-pdf": {
                "name": "Rotate and reorder",
                "card": "Turn pages the right way up and put them in order.",
                "title": "Rotate and reorder PDF pages free - easypdf.surf",
                "description": "Turn pages the right way up and move them into "
                               "order. Free, in your browser, nothing uploaded.",
                "h1": "Rotate and reorder pages",
                "lede": "Turn a page that came out sideways, and move pages into "
                        "the order you want.",
                "drop_b": "Choose a PDF",
                "drop_s": "or drop it here",
                "go": "Save the PDF",
                "rot_all": "Turn every page",
                "ctl_hint": "Use the arrows to move a page and the round arrow to "
                            "turn it.",
            },
            "delete-pages": {
                "name": "Delete pages",
                "card": "Drop the pages you do not want to keep.",
                "title": "Delete pages from a PDF free - easypdf.surf",
                "description": "Remove the pages you do not want from a PDF. Free, "
                               "in your browser, nothing uploaded.",
                "h1": "Delete pages",
                "lede": "Tap the pages you want gone and save what is left.",
                "drop_b": "Choose a PDF",
                "drop_s": "or drop it here",
                "go": "Save the PDF",
                "ctl_hint": "A page marked with a cross is dropped. Tap it again to "
                            "keep it.",
            },
            "images-to-pdf": {
                "name": "Images to PDF",
                "card": "Photos or scans into one PDF, one per page.",
                "title": "Turn JPG or PNG images into a PDF free - easypdf.surf",
                "description": "Make a PDF out of your photos or scans, one per "
                               "page. Free, in your browser, nothing uploaded.",
                "h1": "Images to PDF",
                "lede": "Photos from your phone or scans, turned into one PDF with "
                        "one image per page.",
                "drop_b": "Choose your images",
                "drop_s": "JPG or PNG, or drop them here",
                "go": "Make the PDF",
                "fit": "Page size",
                "fit_a4": "A4 with a margin",
                "fit_image": "As big as the image",
            },
            "pdf-to-image": {
                "name": "PDF to JPG",
                "card": "Every page as a picture you can share.",
                "title": "Turn a PDF into JPG or PNG images free - easypdf.surf",
                "description": "Save the pages of a PDF as JPG or PNG images. Free, "
                               "in your browser, nothing uploaded.",
                "h1": "PDF to image",
                "lede": "Save each page as a picture, ready to send or paste "
                        "anywhere.",
                "drop_b": "Choose a PDF",
                "drop_s": "or drop it here",
                "go": "Make the images",
                "fmt": "Format",
                "fmt_jpg": "JPG",
                "fmt_png": "PNG",
                "dpi": "Quality",
                "dpi_72": "Screen (72 dpi)",
                "dpi_150": "Good (150 dpi)",
                "dpi_300": "Print (300 dpi)",
                "ctl_hint": "Mark with a cross any page you do not want.",
            },
        },
    },
}

TEXTS["es"] = {
    "skip": "Saltar al contenido",
    "nav_tools": "Herramientas",
    "nav_download": "Descargar el programa",
    "theme": "Claro u oscuro",
    "other_name": "In English",
    "other_lang": "en",
    "crumb_home": "Inicio",
    "crumb_tools": "Herramientas",
    "privacy": "Tus archivos no salen de este dispositivo. No se sube nada.",
    "noscript": "Estas herramientas funcionan en tu navegador, asi que necesitan "
                "JavaScript activado. En cualquier caso no se envia nada a ningun sitio.",
    "footer_privacy": "Todas estas herramientas funcionan en tu navegador. Tus "
                      "documentos no se suben a ningun sitio, y no hay cuentas ni "
                      "publicidad.",
    "footer_home": "easypdf.surf",
    "footer_source": "Codigo fuente",
    "footer_libs": 'Hecho con <a href="/tools/vendor/pdf-lib.LICENSE.md">pdf-lib</a> (MIT) y <a href="/tools/vendor/pdfjs.LICENSE">pdf.js</a> (Apache 2.0), servidos desde este mismo sitio.',
    "hub_title": "Herramientas PDF gratis, en tu navegador - easypdf.surf",
    "hub_description": "Unir, dividir, girar, borrar paginas y convertir PDF e "
                       "imagenes. Gratis, sin cuentas y sin que tus archivos salgan "
                       "de tu dispositivo.",
    "hub_h1": "Herramientas PDF",
    "hub_lede": "Las seis cosas que mas falta hacen, hechas aqui mismo en el "
                "navegador. Sin cuentas, sin subir nada y sin esperas.",
    "hub_install": "Anadelas a la pantalla de inicio del movil y funcionan sin conexion.",
    "hub_more_title": "Necesitas algo mas?",
    "hub_more": "El programa easypdf.surf escribe encima de tus PDF, rellena "
                "formularios, borra lo que hay debajo e imprime. Tambien es gratis.",
    "hub_more_cta": "Descargar el programa",
    "next_title": "Otra cosa con tu PDF",
    "js": {
        "page": "Pagina",
        "download": "Descargar",
        "again": "Hacer otro",
        "drag": "Arrastra para reordenar",
        "reading": "Leyendo el archivo...",
        "working": "Trabajando...",
        "rendering": "Pagina {0} de {1}...",
        "done": "Listo",
        "done_title": "Listo",
        "done_merge": "Tus PDF, uno detras de otro en el orden de arriba.",
        "done_split": "Las paginas que pediste, en un solo PDF.",
        "done_split_many": "{0} PDF, uno por pagina, juntos en un zip.",
        "done_organize": "Las paginas en el orden nuevo, ya giradas.",
        "done_delete": "{0} paginas fuera.",
        "done_images": "Tus imagenes, una por pagina.",
        "done_image_one": "La pagina como imagen.",
        "done_image_many": "{0} imagenes, juntas en un zip.",
        "need_two": "Anade al menos dos PDF.",
        "n_files": "{0} archivos",
        "n_images": "{0} imagenes",
        "n_pages": "se quedan {0} paginas",
        "n_pages_doc": "{0} paginas",
        "remove": "Quitar",
        "rotate": "Girar",
        "move_left": "Mover antes",
        "move_right": "Mover despues",
        "move_up": "Subir",
        "move_down": "Bajar",
        "err_read": "No se ha podido leer el archivo.",
        "err_lib": "Algo no ha cargado. Comprueba la conexion y vuelve a intentarlo.",
        "err_pdf": "Esto no parece un PDF que se pueda leer.",
        "err_locked": "Ese PDF tiene contrasena. Abrelo antes con el programa.",
        "err_not_pdf": "Solo archivos PDF, por favor.",
        "err_not_image": "Solo imagenes JPG o PNG, por favor.",
        "err_range": "'{0}' no es un rango de paginas.",
        "err_no_pages": "Ese rango no deja ninguna pagina.",
        "err_all_gone": "Deja al menos una pagina.",
    },
    "tools": {
        "merge-pdf": {
            "name": "Unir PDF",
            "card": "Varios PDF en uno, en el orden que elijas.",
            "title": "Unir PDF gratis, en tu navegador - easypdf.surf",
            "description": "Junta varios PDF en uno solo. Gratis, sin cuentas y sin "
                           "que tus archivos salgan de tu dispositivo.",
            "h1": "Unir PDF",
            "lede": "Junta varios PDF en un solo archivo. Primero ponlos en el orden "
                    "que quieras.",
            "drop_b": "Elige tus PDF",
            "drop_s": "o sueltalos aqui",
            "go": "Unir",
        },
        "split-pdf": {
            "name": "Dividir PDF",
            "card": "Saca las paginas que necesitas, o un archivo por pagina.",
            "title": "Dividir un PDF o extraer paginas gratis - easypdf.surf",
            "description": "Saca de un PDF las paginas que necesitas, o partelo en un "
                           "archivo por pagina. No se sube nada.",
            "h1": "Dividir PDF",
            "lede": "Saca las paginas que necesitas, o parte el documento en un "
                    "archivo por pagina.",
            "drop_b": "Elige un PDF",
            "drop_s": "o sueltalo aqui",
            "go": "Dividir",
            "mode": "Que quieres",
            "mode_range": "Estas paginas",
            "mode_each": "Un archivo por pagina",
            "range_label": "Paginas",
            "range_hint": "Por ejemplo 1-3, 8, 12- . Dejalo vacio para todas.",
        },
        "organize-pdf": {
            "name": "Girar y reordenar",
            "card": "Endereza las paginas y ponlas en orden.",
            "title": "Girar y reordenar las paginas de un PDF gratis - easypdf.surf",
            "description": "Endereza las paginas y muevelas al orden que quieras. "
                           "Gratis, en tu navegador, sin subir nada.",
            "h1": "Girar y reordenar paginas",
            "lede": "Endereza una pagina que salio tumbada y mueve las paginas al "
                    "orden que quieras.",
            "drop_b": "Elige un PDF",
            "drop_s": "o sueltalo aqui",
            "go": "Guardar el PDF",
            "rot_all": "Girar todas",
            "ctl_hint": "Con las flechas mueves una pagina y con la flecha redonda "
                        "la giras.",
        },
        "delete-pages": {
            "name": "Borrar paginas",
            "card": "Quita las paginas que no quieres.",
            "title": "Borrar paginas de un PDF gratis - easypdf.surf",
            "description": "Quita de un PDF las paginas que no quieres. Gratis, en tu "
                           "navegador, sin subir nada.",
            "h1": "Borrar paginas",
            "lede": "Toca las paginas que sobran y guarda lo que queda.",
            "drop_b": "Elige un PDF",
            "drop_s": "o sueltalo aqui",
            "go": "Guardar el PDF",
            "ctl_hint": "Una pagina marcada con la cruz se va. Tocala otra vez para "
                        "quedartela.",
        },
        "images-to-pdf": {
            "name": "Imagenes a PDF",
            "card": "Fotos o escaneos en un PDF, una por pagina.",
            "title": "Convertir imagenes JPG o PNG a PDF gratis - easypdf.surf",
            "description": "Haz un PDF con tus fotos o escaneos, uno por pagina. "
                           "Gratis, en tu navegador, sin subir nada.",
            "h1": "Imagenes a PDF",
            "lede": "Fotos del movil o escaneos, convertidos en un PDF con una "
                    "imagen por pagina.",
            "drop_b": "Elige tus imagenes",
            "drop_s": "JPG o PNG, o sueltalas aqui",
            "go": "Hacer el PDF",
            "fit": "Tamano de pagina",
            "fit_a4": "A4 con margen",
            "fit_image": "El de la imagen",
        },
        "pdf-to-image": {
            "name": "PDF a JPG",
            "card": "Cada pagina como una imagen que puedes compartir.",
            "title": "Convertir un PDF a imagenes JPG o PNG gratis - easypdf.surf",
            "description": "Guarda las paginas de un PDF como imagenes JPG o PNG. "
                           "Gratis, en tu navegador, sin subir nada.",
            "h1": "PDF a imagen",
            "lede": "Guarda cada pagina como una imagen, lista para enviar o pegar "
                    "donde quieras.",
            "drop_b": "Elige un PDF",
            "drop_s": "o sueltalo aqui",
            "go": "Hacer las imagenes",
            "fmt": "Formato",
            "fmt_jpg": "JPG",
            "fmt_png": "PNG",
            "dpi": "Calidad",
            "dpi_72": "Pantalla (72 ppp)",
            "dpi_150": "Buena (150 ppp)",
            "dpi_300": "Impresion (300 ppp)",
            "ctl_hint": "Marca con la cruz las paginas que no quieras.",
        },
    },
}

#: The order they appear in the hub and in the sitemap.
ORDER = ["merge-pdf", "split-pdf", "organize-pdf", "delete-pages",
         "images-to-pdf", "pdf-to-image"]


# -------------------------------------------------------------------- bodies
def _drop(t: dict, accept: str, multiple: bool) -> str:
    """The drop zone, which is deliberately the biggest thing on the page.

    The button inside it is not a real control: the whole box is the target,
    so a thumb landing anywhere on it opens the file picker.
    """
    more = " multiple" if multiple else ""
    return f"""  <div class="drop" id="drop" tabindex="0" role="button"
       aria-label="{esc(t['drop_b'])}">
    {UPLOAD_ICON}
    <span class="pick-btn">{esc(t['drop_b'])}</span>
    <span>{esc(t['drop_s'])}</span>
    <input type="file" id="file" accept="{accept}"{more}>
  </div>"""


def _actions(t: dict) -> str:
    return f"""  <div class="actbar" hidden>
    <div class="in">
      <span class="st" id="status" role="status" aria-live="polite"></span>
      <button class="go" id="go" type="button" disabled>
        <span class="sp" aria-hidden="true"></span><span>{esc(t['go'])}</span>
      </button>
    </div>
  </div>"""


def _grid() -> str:
    return '  <ul class="grid" id="grid" hidden></ul>'


def _done() -> str:
    return '  <div class="done" id="done" hidden></div>'


def _seg(seg_id: str, attr: str, options: list[tuple[str, str, bool]]) -> str:
    buttons = "".join(
        f'<button type="button" data-{attr}="{value}" '
        f'aria-pressed="{"true" if on else "false"}">{esc(label)}</button>'
        for value, label, on in options
    )
    return f'<div class="seg" id="{seg_id}" role="group">{buttons}</div>'


def _other_tools(lang: str, slug: str, texts: dict) -> str:
    """The other five tools, so finishing one leads somewhere.

    Someone who has just split a PDF very often wants to merge the pieces
    back, and hunting for the menu again is friction nobody needs.
    """
    rows = []
    for other in ORDER:
        if other == slug:
            continue
        rows.append(
            f'      <li><a href="{_url(lang, other)}">{icon(other, 19)}'
            f'{esc(texts["tools"][other]["name"])}</a></li>'
        )
    return f"""  <section class="next">
    <h2>{esc(texts['next_title'])}</h2>
    <ul>
{chr(10).join(rows)}
    </ul>
  </section>"""


def body(slug: str, t: dict) -> str:
    """The part of the page that changes from one tool to the next."""
    if slug == "merge-pdf":
        return "\n".join([
            _drop(t, "application/pdf,.pdf", True),
            '  <ul class="files" id="files" hidden></ul>',
            _done(),
            _actions(t),
        ])

    if slug == "split-pdf":
        controls = f"""  <div class="ctl" id="ctl" hidden>
    <h2>{esc(t['mode'])}</h2>
    <div class="row">
      {_seg("mode", "mode", [("range", t["mode_range"], True),
                             ("each", t["mode_each"], False)])}
    </div>
    <div class="row" id="range-row">
      <label for="range">{esc(t['range_label'])}</label>
      <input type="text" id="range" inputmode="numeric" autocomplete="off">
    </div>
    <p class="hint">{esc(t['range_hint'])}</p>
  </div>"""
        return "\n".join([
            _drop(t, "application/pdf,.pdf", False), controls, _grid(), _done(), _actions(t),
        ])

    if slug == "organize-pdf":
        controls = f"""  <div class="ctl" id="ctl" hidden>
    <div class="row">
      <button class="ib" id="rot-all" type="button">{esc(t['rot_all'])}</button>
    </div>
    <p class="hint">{esc(t['ctl_hint'])}</p>
  </div>"""
        return "\n".join([
            _drop(t, "application/pdf,.pdf", False), controls, _grid(), _done(), _actions(t),
        ])

    if slug == "delete-pages":
        controls = f"""  <div class="ctl" id="ctl" hidden>
    <p class="hint">{esc(t['ctl_hint'])}</p>
  </div>"""
        return "\n".join([
            _drop(t, "application/pdf,.pdf", False), controls, _grid(), _done(), _actions(t),
        ])

    if slug == "images-to-pdf":
        controls = f"""  <div class="ctl" id="ctl" hidden>
    <h2>{esc(t['fit'])}</h2>
    <div class="row">
      {_seg("fit", "fit", [("fit", t["fit_a4"], True), ("image", t["fit_image"], False)])}
    </div>
  </div>"""
        return "\n".join([
            _drop(t, "image/jpeg,image/png,.jpg,.jpeg,.png", True),
            controls, _grid(), _done(), _actions(t),
        ])

    if slug == "pdf-to-image":
        controls = f"""  <div class="ctl" id="ctl" hidden>
    <h2>{esc(t['fmt'])}</h2>
    <div class="row">
      {_seg("fmt", "fmt", [("jpeg", t["fmt_jpg"], True), ("png", t["fmt_png"], False)])}
    </div>
    <div class="row">
      <label for="dpi">{esc(t['dpi'])}</label>
      <select id="dpi">
        <option value="72">{esc(t['dpi_72'])}</option>
        <option value="150" selected>{esc(t['dpi_150'])}</option>
        <option value="300">{esc(t['dpi_300'])}</option>
      </select>
    </div>
    <p class="hint">{esc(t['ctl_hint'])}</p>
  </div>"""
        return "\n".join([
            _drop(t, "application/pdf,.pdf", False), controls, _grid(), _done(), _actions(t),
        ])

    raise KeyError(slug)                      # pragma: no cover - every slug is above


def hub_body(lang: str, texts: dict) -> str:
    """The list of tools, which is also the start page of the installed app."""
    home = "/" if lang == "en" else "/es/"
    cards = []
    for slug in ORDER:
        t = texts["tools"][slug]
        cards.append(
            f'    <li><a href="{_url(lang, slug)}">{icon(slug)}'
            f'<span><b>{esc(t["name"])}</b><span>{esc(t["card"])}</span></span></a></li>'
        )
    return f"""  <ul class="tools">
{chr(10).join(cards)}
  </ul>
  <p class="hint">{esc(texts['hub_install'])}</p>

  <div class="ctl">
    <h2>{esc(texts['hub_more_title'])}</h2>
    <p class="hint">{esc(texts['hub_more'])}</p>
    <p class="row"><a class="dl" href="{home}#downloads">{esc(texts['hub_more_cta'])}</a></p>
  </div>"""


def _url(lang: str, slug: str | None = None) -> str:
    """Absolute path of a tool page (or of the hub when slug is None)."""
    root = "/tools/" if lang == "en" else "/es/tools/"
    return root if slug is None else root + slug + "/"


# --------------------------------------------------------------------- pages
def _crumb(lang: str, texts: dict, slug: str | None) -> str:
    home = "/" if lang == "en" else "/es/"
    parts = [f'<a href="{home}">{esc(texts["crumb_home"])}</a>']
    if slug is None:
        parts.append(esc(texts["crumb_tools"]))
    else:
        parts.append(f'<a href="{_url(lang)}">{esc(texts["crumb_tools"])}</a>')
        parts.append(esc(texts["tools"][slug]["name"]))
    return '<p class="crumb">' + " / ".join(parts) + "</p>"


def _breadcrumbs(lang: str, texts: dict, slug: str | None) -> dict:
    home = DOMAIN + ("/" if lang == "en" else "/es/")
    trail = [(texts["crumb_home"], home), (texts["crumb_tools"], DOMAIN + _url(lang))]
    if slug is not None:
        trail.append((texts["tools"][slug]["name"], DOMAIN + _url(lang, slug)))
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": url}
            for i, (name, url) in enumerate(trail, start=1)
        ],
    }


def _json_ld(lang: str, texts: dict, slug: str | None) -> str:
    if slug is None:
        data = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": texts["hub_h1"],
            "description": texts["hub_description"],
            "url": DOMAIN + _url(lang),
            "inLanguage": lang,
            "mainEntity": {
                "@type": "ItemList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i,
                        "name": texts["tools"][item]["name"],
                        "url": DOMAIN + _url(lang, item),
                    }
                    for i, item in enumerate(ORDER, start=1)
                ],
            },
        }
    else:
        t = texts["tools"][slug]
        data = {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": t["name"],
            "description": t["description"],
            "url": DOMAIN + _url(lang, slug),
            "applicationCategory": "UtilitiesApplication",
            "browserRequirements": "Requires JavaScript",
            "operatingSystem": "Any",
            "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
            "inLanguage": lang,
        }
    return json.dumps([data, _breadcrumbs(lang, texts, slug)], ensure_ascii=False)


def page(template, lang: str, slug: str | None) -> str:
    texts = TEXTS[lang]
    other = "es" if lang == "en" else "en"
    here = _url(lang, slug)
    if slug is None:
        title, description = texts["hub_title"], texts["hub_description"]
        h1, lede = texts["hub_h1"], texts["hub_lede"]
        page_body = hub_body(lang, texts)
        tool_id = "hub"
        sw = "/sw.js"
    else:
        t = texts["tools"][slug]
        title, description = t["title"], t["description"]
        h1, lede = t["h1"], t["lede"]
        page_body = body(slug, t) + "\n\n" + _other_tools(lang, slug, texts)
        tool_id = slug
        sw = "/sw.js"

    return template.safe_substitute(
        lang=lang,
        locale="en_US" if lang == "en" else "es_ES",
        title=esc(title),
        description=esc(description),
        canonical=DOMAIN + here,
        alt_en=DOMAIN + _url("en", slug),
        alt_es=DOMAIN + _url("es", slug),
        domain=DOMAIN,
        repo=REPO,
        manifest="/manifest.webmanifest",
        sw=sw,
        tool=tool_id,
        skip=esc(texts["skip"]),
        home="/" if lang == "en" else "/es/",
        tools_home=_url(lang),
        nav_tools=esc(texts["nav_tools"]),
        nav_download=esc(texts["nav_download"]),
        other_url=DOMAIN + _url(other, slug),
        other_lang=other,
        other_name=esc(texts["other_name"]),
        OTHER_LANG=other.upper(),
        theme=esc(texts["theme"]),
        crumb=_crumb(lang, texts, slug),
        h1=esc(h1),
        lede=esc(lede),
        privacy=esc(texts["privacy"]),
        body=page_body,
        noscript=esc(texts["noscript"]),
        footer_privacy=esc(texts["footer_privacy"]),
        footer_home=esc(texts["footer_home"]),
        footer_source=esc(texts["footer_source"]),
        footer_libs=texts["footer_libs"],
        json_ld=_json_ld(lang, texts, slug),
        i18n=json.dumps(texts["js"], ensure_ascii=False),
    )


def urls() -> list[str]:
    """Every tools URL, for the sitemap."""
    out = []
    for lang in ("en", "es"):
        out.append(_url(lang))
        out.extend(_url(lang, slug) for slug in ORDER)
    return out


def build() -> None:
    from string import Template

    template = Template(open(TEMPLATE, encoding="utf-8").read())
    written = 0
    for lang in ("en", "es"):
        for slug in [None] + ORDER:
            folder = os.path.join(SITE, _url(lang, slug).strip("/"))
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as fh:
                fh.write(page(template, lang, slug))
            written += 1

        # Nothing per language any more: one worker and one manifest at the
        # root cover the whole site, /es/ and /tools/ included.
    print(f"Wrote {written} tools pages")


if __name__ == "__main__":                     # pragma: no cover - run by hand
    build()
