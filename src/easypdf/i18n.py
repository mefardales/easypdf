"""Textos de la interfaz en espanol e ingles.

No se usan los archivos .ts de Qt a proposito: con un diccionario el proyecto
no necesita compilar traducciones ni herramientas aparte, y anadir un idioma es
copiar un bloque y traducirlo.

    from .i18n import tr
    boton.setText(tr("open"))
"""

from __future__ import annotations

from typing import Callable

#: Idiomas disponibles: codigo -> nombre en su propio idioma.
LANGUAGES = {"es": "Espanol", "en": "English"}
DEFAULT_LANGUAGE = "en"

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "about_title": "About {app}",
        "about_tagline": "Simple PDF reader and annotator",
        "about_html": (
            "<p>Free software released under the <b>GNU AGPL v3 or later</b> licence. "
            "You may use, copy, modify and redistribute it under that licence. "
            "The source code is available from the website.</p>"
            "<p><a href='{url}'>easypdf.surf</a></p>"
        ),
        "about_licences": "Licences",
        "licences_title": "Licences",
        "licences_html": (
            "<p><b>easypdf.surf</b> is released under the "
            "<a href='https://www.gnu.org/licenses/agpl-3.0.html'>GNU AGPL v3 or later</a>. "
            "It comes with no warranty, to the extent permitted by law.</p>"
            "<p>It is built with these libraries, each under its own licence:</p><ul>"
            "<li><a href='https://pymupdf.readthedocs.io'>PyMuPDF</a> - GNU AGPL v3</li>"
            "<li><a href='https://doc.qt.io/qtforpython/'>PySide6</a> (Qt for Python) - "
            "GNU LGPL v3. You may replace it with your own build of the library.</li>"
            "</ul>"
        ),
        "help_title": "Quick guide",
        "help_html": (
            "<h2>Quick guide</h2>"
            "<h3>Open, create and print</h3><ul>"
            "<li><b>Ctrl+O</b> opens a PDF. You can also drag one onto the window.</li>"
            "<li><b>Ctrl+N</b> creates a blank document. From the <b>Document</b> menu you "
            "can add, duplicate, move and delete pages, and choose their size.</li>"
            "<li><b>Ctrl+P</b> prints. The preview shows the document with the annotations "
            "exactly as they will come out on paper.</li>"
            "<li><b>Ctrl+S</b> saves the annotations into the PDF.</li></ul>"
            "<h3>Annotate</h3><ul>"
            "<li>Pick a tool in the bar: box, highlight, line, arrow, text, freehand, table "
            "or image.</li>"
            "<li>Drag on the page to create the annotation.</li>"
            "<li>Hold <b>Shift</b> for perfect squares or 45 degree lines.</li>"
            "<li>With the <b>Select</b> tool you can move, resize (blue handles) and delete "
            "with <b>Del</b>.</li>"
            "<li>Double click a text box to type inside it.</li>"
            "<li>In tables, double click a cell to type and <b>Tab</b> to move to the next "
            "one. Rows and columns are chosen in the bar before drawing it.</li>"
            "<li>Text supports a typeface (sans, serif or monospace), <b>bold</b> (Ctrl+B), "
            "<i>italic</i> (Ctrl+I) and alignment.</li>"
            "<li>With the <b>Image</b> tool, or by dropping an image file onto the window, "
            "you can place photos, signatures or logos on top of the PDF.</li>"
            "<li>The <b>Eraser</b> really erases: it removes the annotations it "
            "passes over, and when you save the file it also takes out the original "
            "text or image underneath, so it cannot be selected or copied any more. "
            "Until you save, <b>Ctrl+Z</b> brings everything back; once saved it is "
            "gone for good. <b>Ctrl+</b> and <b>Ctrl-</b> change its size and you can "
            "pick its colour.</li>"
            "<li><b>Ctrl+C</b>, <b>Ctrl+X</b> and <b>Ctrl+V</b> copy, cut and paste "
            "whatever is selected. What you paste lands slightly offset on the page "
            "you are on, already selected so you can drag it into place.</li>"
            "<li><b>Ctrl+Z</b> and <b>Ctrl+Y</b> undo and redo.</li></ul>"
            "<h3>Moving around</h3><ul>"
            "<li><b>Ctrl+wheel</b> zooms; <b>Ctrl+0</b> goes back to 100%.</li>"
            "<li><b>Ctrl+F</b> searches; <b>F3</b> jumps to the next result. <b>Esc</b> or "
            "the close button clears the yellow highlight.</li>"
            "<li>The thumbnails sidebar jumps between pages.</li>"
            "<li><b>Esc</b> finishes what you are doing and goes back to the Select tool, leaving what you made selected so you can copy it, move it or delete it right away. To deselect, click on an empty part of the page.</li></ul>"
            "<h3>Guides</h3>"
            "<p>Drag from the top or side ruler to drop a guide. Guides belong to the whole document: the same line shows on every page, so a margin or a column lines up the same everywhere. Drag one off the page to remove it, and use <b>View -&gt; Clear guides</b> to remove them all.</p>"
            "<h3>Form pieces</h3>"
            "<p>The <b>Elements</b> tab in the side panel has ready-made pieces for "
            "building forms: fields with a line to write on, tick boxes, signature "
            "lines, headings and tables. Double click one and it drops on the page you "
            "are on. They are ordinary annotations, so you edit and move them like "
            "anything else, and once the sheet is done you can save it as a template.</p>"
            "<h3>Templates</h3>"
            "<p>Under <b>Document -&gt; Templates</b> you can save what you have built "
            "(letterheads, tables, stamps, logos) and reuse it: create a new document from a "
            "template or apply it on top of the PDF you have open, starting at the page you "
            "are on. One <b>Ctrl+Z</b> undoes the whole thing.</p>"
            "<h3>How annotations are stored</h3>"
            "<p>The program writes standard PDF annotations (square, line, free text, "
            "highlight, ink and polygon), so they look the same in Adobe Reader, Edge or "
            "Firefox. Tables are stored as their grid plus the text of each cell, and images "
            "are embedded in the page itself so they always print.</p>"
            "<h3>New versions</h3>"
            "<p>The program checks the official site now and then and tells you when a "
            "newer version is out. From that notice you can <b>download and install</b> it "
            "without leaving the app: it picks the right package for your system, checks "
            "the download against the published checksum, and on Windows runs the "
            "installer. Under <b>Help</b> you can check by hand or turn the check off.</p>"
        ),
        # --- nombres cortos ---
        "font_sans": "Sans",
        "font_serif": "Serif",
        "font_mono": "Monospace",
        "act_align_left": "Align left",
        "act_align_center": "Centre",
        "act_align_right": "Align right",
        "kind_rect": "box",
        "kind_highlight": "highlight",
        "kind_line": "line",
        "kind_arrow": "arrow",
        "kind_text": "text",
        "kind_ink": "drawing",
        "kind_table": "table",
        "kind_image": "image",
        "cmd_add": "Add {kind}",
        "cmd_delete_one": "Delete annotation",
        "cmd_delete_many": "Delete {count} annotations",
        "cmd_change": "Change annotation",
        "cmd_style": "Change style",
        "cmd_page_add": "Add page",
        "cmd_page_duplicate": "Duplicate page",
        "cmd_page_delete": "Delete page {page}",
        "cmd_page_move": "Move page {page}",
        "cmd_page_rotate": "Rotate page {page}",
        "cmd_erase": "Erase",
        "cmd_template": "Apply template ({count} annotations)",
        "cmd_paste": "Paste ({count})",
        # --- archivo ---
        "new": "&New blank document",
        "new_tip": "Create an empty PDF to start from scratch",
        "open": "&Open...",
        "open_tip": "Open a PDF document",
        "save": "&Save",
        "save_tip": "Save the annotations into the PDF",
        "save_as": "Save &as...",
        "save_as_tip": "Save a copy of the PDF",
        "print": "&Print...",
        "print_tip": "Print the document",
        "preview": "Print pre&view...",
        "preview_tip": "See how it will look on paper",
        "close_doc": "&Close document",
        "quit": "&Quit",
        "menu_file": "&File",
        "recent": "Open &recent",
        "recent_clear": "Clear the list",
        # --- editar ---
        "menu_edit": "&Edit",
        "undo": "Undo",
        "redo": "Redo",
        "copy_sel": "&Copy",
        "cut_sel": "Cu&t",
        "paste_sel": "&Paste",
        "delete_sel": "&Delete selection",
        "delete_sel_tip": "Delete the selected annotations",
        "select_all": "Select &all annotations",
        "find": "&Find text...",
        "find_tip": "Search for text in the document",
        "find_next": "Find &next",
        "find_prev": "Find &previous",
        "search_placeholder": "Search text in the document...",
        "search_close": "Close and clear the highlight",
        "search_none": "  No results  ",
        "search_of": "  {current} of {total}  ",
        "search_not_found": "'{text}' was not found",
        # --- ver ---
        "menu_view": "&View",
        "zoom_in": "Zoom &in",
        "zoom_out": "Zoom &out",
        "zoom_reset": "Zoom &100%",
        "fit_width": "Fit to &width",
        "fit_page": "Fit to &page",
        "prev_page": "&Previous page",
        "next_page": "&Next page",
        "goto": "&Go to page...",
        "goto_title": "Go to page",
        "goto_label": "Page number (1-{total}):",
        "fullscreen": "&Full screen",
        "thumbnails": "&Thumbnails panel",
        "side_panel": "&Side panel (bookmarks, notes, elements)",
        "pages_dock": "Pages",
        # --- documento ---
        "menu_document": "&Document",
        "page_add": "&Add a page at the end",
        "page_insert": "&Insert a page after this one",
        "page_duplicate": "&Duplicate this page",
        "page_delete": "D&elete this page",
        "page_up": "Move the page &up",
        "page_down": "Move the page &down",
        "page_insert_before": "Insert a blank page &before",
        "page_insert_after": "Insert a blank page &after",
        "page_rotate_left": "Rotate &left (90\u00b0)",
        "page_rotate_right": "Rotate &right (90\u00b0)",
        "page_rotate_180": "Rotate 1&80\u00b0",
        "page_rotate_menu": "&Rotate this page",
        "size_same": "Same as this page",
        "size_A4": "A4",
        "size_A4 horizontal": "A4 landscape",
        "size_Carta": "Letter",
        "size_Carta horizontal": "Letter landscape",
        "size_A5": "A5",
        "size_A3": "A3",
        "size_Oficio": "Legal",
        "page_move_undo": "Page {origin} moved to position {target}",
        "page_size_menu": "&Size of new pages",
        "templates": "&Templates",
        "template_save": "&Save this as a template...",
        "template_save_tip": "Save the current annotations to reuse them",
        "template_none": "(no templates saved yet)",
        "template_new": "&New document from template",
        "template_apply": "&Apply to the current document",
        "template_delete": "D&elete a template",
        "template_folder": "Open the templates &folder",
        "template_name_title": "Save as template",
        "template_name_label": "Template name:",
        "template_saved": "Template saved: {name}",
        "template_applied": "Template '{name}': {count} annotations placed from page {page}",
        "template_new_done": "New document from template '{name}'",
        "template_deleted": "Template deleted: {name}",
        "template_delete_ask": "Delete the template '{name}'?",
        "template_empty": (
            "There is nothing to save yet: add boxes, text, tables or images and try again."
        ),
        "template_detail": "{count} annotations",
        "template_detail_pages": "{pages} pages, {count} annotations",
        # --- herramientas ---
        "menu_tools": "&Tools",
        "tool_select": "&Select",
        "tool_pan": "&Move the view",
        "tool_rect": "&Box",
        "tool_highlight": "High&light",
        "tool_line": "&Line",
        "tool_arrow": "&Arrow",
        "tool_text": "&Text",
        "tool_ink": "&Freehand",
        "tool_table": "Ta&ble",
        "tool_note": "&Note",
        "bookmarks_dock": "Bookmarks",
        "side_dock": "Panel",
        "notes_tab": "Notes",
        "templates_tab": "Templates",
        "tpl_included": "Included",
        "tpl_mine": "Mine",
        "tpl_use": "Use here",
        "tpl_new": "New document",
        "tpl_save": "Save current...",
        "tpl_delete": "Delete",
        "tpl_kind": "Type of template:",
        "tpl_entry": "{name}  -  {pages} p., {count} items",
        "tpl_none": "No document open.",
        "cat_document": "Office",
        "cat_report": "Reports",
        "cat_certificate": "Certificates",
        "cat_letterhead": "Letterheads",
        "cat_table": "Tables and invoices",
        "cat_form": "Forms",
        "cat_other": "Other",
        "notes_show_done": "Show the ones already read",
        "elements_tab": "Elements",
        "el_insert": "Insert",
        "el_hint": "Double click a piece to drop it on the page you are on.",
        "elcat_field": "Fields",
        "elcat_choice": "Tick boxes",
        "elcat_signature": "Signatures",
        "elcat_layout": "Layout",
        "el_text_field": "Field with a line",
        "el_long_field": "Field, three lines",
        "el_date_field": "Date field",
        "el_boxed_field": "Field with a box",
        "el_checkbox": "Tick box",
        "el_checklist": "List of tick boxes",
        "el_yes_no": "Yes / No",
        "el_signature": "Signature line",
        "el_two_signatures": "Two signatures",
        "el_place_date": "Place and date",
        "el_heading": "Heading with a rule",
        "el_separator": "Separator line",
        "el_table": "Table with headers",
        "el_note_box": "Notes box",
        "status_element_added": "{name} added",
        "cmd_element": "Insert {name}",
        "note_entry": "p. {page}  -  {text}",
        "note_empty": "(empty note)",
        "update_check": "Check for &updates",
        "update_auto": "Check for updates on start&up",
        "update_title": "New version available",
        "update_body": "Version <b>{new}</b> is out. You have {old}.",
        "update_go": "Go to the website",
        "update_later": "Not now",
        "update_skip": "Skip this version",
        "update_none": "You have the latest version ({version}).",
        "update_failed": "Could not check for updates.",
        "update_checking": "Checking for updates...",
        "update_download": "Download and install",
        "update_downloading": "Downloading {name}",
        "update_progress": "{done} MB of {total} MB",
        "update_progress_unknown": "{done} MB downloaded",
        "update_verifying": "Checking the download...",
        "update_ready_install": (
            "The download is ready. EasyPDF will close so the installer "
            "can replace it."
        ),
        "update_ready_file": (
            "Saved to:<br><b>{path}</b><br>Unpack it over your current copy "
            "to update."
        ),
        "update_install_now": "Install now",
        "update_open_folder": "Open the folder",
        "update_download_failed": "The download failed: {error}",
        "update_no_asset": (
            "There is no automatic download for this system yet. "
            "The website has all the packages."
        ),
        "update_cancel": "Cancel",
        "update_close": "Close",
        "cursor_pos": "{x} x {y} {unit}",
        "rulers": "&Rulers",
        "ruler_unit_menu": "Ruler &units",
        "unit_mm": "Millimetres",
        "unit_cm": "Centimetres",
        "unit_in": "Inches",
        "unit_pt": "Points",
        "snap": "&Align to guides",
        "guides_clear": "Remove all &guides",
        "guides_hint": "Drag from a ruler to add a guide. Drag it off the page to remove it.",
        "guide_at": "Guide at {value} {unit}",
        "bookmark_add": "Add",
        "bookmark_remove": "Remove",
        "bookmark_prompt": "Name of the bookmark:",
        "bookmark_default": "Page {page}",
        "bookmark_entry": "{title}  -  p. {page}",
        "note_title": "Note",
        "note_prompt": "Text of the note:",
        "tool_eraser": "&Eraser",
        "eraser_size": "Eraser: {size} pt  (Ctrl+ / Ctrl- or [ ] to resize)",
        "eraser_color_tip": "Colour the eraser covers with (white = paper)",
        "tool_image": "&Image",
        "tool_status": "Tool: {name} ({key})",
        "hint_highlight": "Drag over the text you want to highlight",
        "hint_text": "Drag to create the box and type; Esc when done",
        "hint_table": (
            "Drag to create a {rows} x {cols} table; double click a cell to type, "
            "Tab moves to the next one"
        ),
        "hint_image": "Drag on the page to place {name}, or click once for a comfortable size",
        # --- barras ---
        "toolbar_main": "Main",
        "toolbar_tools": "Tools",
        "toolbar_style": "Style",
        "toolbar_search": "Search",
        "color_tip": "Stroke and text colour",
        "fill_tip": "Fill colour",
        "no_fill": "No fill",
        "more_colours": "More colours...",
        "pick_colour": "Choose a colour",
        "width": " Width ",
        "width_tip": "Line thickness",
        "opacity": " Opacity ",
        "opacity_tip": "Annotation opacity",
        "font_size": " Size ",
        "font_size_tip": "Text size",
        "font_tip": "Typeface",
        "bold": "Bold",
        "bold_tip": "Bold (Ctrl+B)",
        "italic": "Italic",
        "italic_tip": "Italic (Ctrl+I)",
        "table_label": " Table ",
        "rows_prefix": "rows ",
        "rows_tip": "Table rows",
        "cols_prefix": "cols ",
        "cols_tip": "Table columns",
        # --- ayuda ---
        "menu_help": "&Help",
        "help": "&Quick guide",
        "about": "&About {app}",
        "website": "easypdf.surf &website",
        "language": "&Language",
        "language_changed": "Language changed to English",
        # --- estado ---
        "status_start": "Open a PDF with Ctrl+O or drag one here",
        "status_page": "Page",
        "status_of": "of {total}",
        "status_opened": "Opened: {path}",
        "status_saved": "Saved: {path}",
        "status_printed": "Document sent to the printer",
        "status_new": "New document. Add pages from the Document menu and save with Ctrl+S",
        "status_image_placed": "Image placed: {name}",
        "status_no_selection": "No annotation is selected",
        "status_erased": "Erased. Saving removes it from the file for good.",
        "status_pick_select": "Nothing is selected. Press Esc to go back to the Select tool, then click what you want.",
        "status_copied": "{count} copied",
        "status_cut": "{count} cut",
        "status_pasted": "{count} pasted",
        "status_clipboard_empty": "There is nothing of easypdf.surf to paste",
        "status_annotations": "{count} annotations",
        "status_annotation": "1 annotation",
        "status_editing": "Type the note; Esc when done",
        # --- dialogos ---
        "open_title": "Open PDF",
        "pdf_filter": "PDF documents (*.pdf);;All files (*)",
        "image_filter": (
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;All files (*)"
        ),
        "image_title": "Choose an image",
        "image_unreadable": "The image could not be read:\n{error}",
        "image_invalid": "That file does not look like an image that can be opened.",
        "save_title": "Save PDF as",
        "password_title": "Protected document",
        "password_label": "Password for {name}:",
        "no_such_file": "There is no such file:\n{path}",
        "unsaved_title": "Unsaved annotations",
        "unsaved": "The document has unsaved annotations.\n\nDo you want to save them?",
        "delete_page_ask": "Delete page {page} of {total}?",
        "delete_page_annots": "\n\nIts {count} annotations will be deleted too.",
        "delete_page_undo": "\n\nThis can be undone with Ctrl+Z.",
        "last_page": "The document cannot be left without pages.",
        "print_restricted": (
            "This PDF asks not to be printed.\n\nThat restriction is not protected by a "
            "password, so the program can print it anyway.\n\nOnly do so if you have the "
            "right to. Continue?"
        ),
        "print_failed": "The printing could not be started.",
        "print_title": "Print document",
        "print_preview_title": "Print preview",
        "print_preparing": "Preparing pages...",
        "print_page_of": "Page {page} of {total}",
    },
    "es": {
        "about_title": "Acerca de {app}",
        "about_tagline": "Lector y anotador de PDF sencillo",
        "about_html": (
            "<p>Software libre publicado bajo la licencia <b>GNU AGPL v3 o posterior</b>. "
            "Puedes usarlo, copiarlo, modificarlo y redistribuirlo respetando esa licencia. "
            "El codigo fuente esta disponible en la pagina web.</p>"
            "<p><a href='{url}'>easypdf.surf</a></p>"
        ),
        "about_licences": "Licencias",
        "licences_title": "Licencias",
        "licences_html": (
            "<p><b>easypdf.surf</b> se publica bajo la "
            "<a href='https://www.gnu.org/licenses/agpl-3.0.html'>GNU AGPL v3 o posterior</a>. "
            "Se distribuye sin ninguna garantia, hasta donde permite la ley.</p>"
            "<p>Esta construido con estas bibliotecas, cada una con su licencia:</p><ul>"
            "<li><a href='https://pymupdf.readthedocs.io'>PyMuPDF</a> - GNU AGPL v3</li>"
            "<li><a href='https://doc.qt.io/qtforpython/'>PySide6</a> (Qt for Python) - "
            "GNU LGPL v3. Puedes sustituirla por tu propia compilacion de la "
            "biblioteca.</li>"
            "</ul>"
        ),
        "help_title": "Guia rapida",
        "help_html": (
            "<h2>Guia rapida</h2>"
            "<h3>Abrir, crear e imprimir</h3><ul>"
            "<li><b>Ctrl+O</b> abre un PDF. Tambien puedes arrastrarlo sobre la ventana.</li>"
            "<li><b>Ctrl+N</b> crea un documento en blanco. Desde el menu <b>Documento</b> "
            "puedes anadir, duplicar, mover y eliminar paginas, y elegir su tamano.</li>"
            "<li><b>Ctrl+P</b> imprime. La vista previa muestra el documento con las "
            "anotaciones tal y como saldran en papel.</li>"
            "<li><b>Ctrl+S</b> guarda las anotaciones dentro del PDF.</li></ul>"
            "<h3>Anotar</h3><ul>"
            "<li>Elige una herramienta en la barra: cuadro, resaltado, linea, flecha, texto, "
            "dibujo a mano alzada, tabla o imagen.</li>"
            "<li>Arrastra sobre la pagina para crear la anotacion.</li>"
            "<li>Manten <b>Mayus</b> para cuadrados perfectos o lineas a 45 grados.</li>"
            "<li>Con la herramienta <b>Seleccionar</b> puedes mover, redimensionar (tiradores "
            "azules) y borrar con <b>Supr</b>.</li>"
            "<li>Doble clic sobre un cuadro de texto para escribir dentro.</li>"
            "<li>En las tablas, doble clic en una celda para escribir y <b>Tab</b> para pasar "
            "a la siguiente. Las filas y columnas se eligen en la barra antes de dibujarla.</li>"
            "<li>El texto admite tipo de letra (sans, serif o monoespaciada), <b>negrita</b> "
            "(Ctrl+B), <i>cursiva</i> (Ctrl+I) y alineacion.</li>"
            "<li>Con la herramienta <b>Imagen</b> (o soltando un archivo de imagen sobre la "
            "ventana) puedes colocar fotos, firmas o logotipos encima del PDF.</li>"
            "<li>La <b>goma</b> borra de verdad: se lleva las anotaciones por las que "
            "pasa y, al guardar el archivo, tambien quita el texto o la imagen "
            "original que haya debajo, de modo que ya no se puede seleccionar ni "
            "copiar. Hasta que guardas, <b>Ctrl+Z</b> lo devuelve todo; una vez "
            "guardado no hay vuelta atras. Con <b>Ctrl+</b> y <b>Ctrl-</b> se cambia "
            "su tamano, y se puede elegir su color.</li>"
            "<li><b>Ctrl+C</b>, <b>Ctrl+X</b> y <b>Ctrl+V</b> copian, cortan y pegan "
            "lo que este seleccionado. Lo pegado cae un poco corrido en la pagina que "
            "se este viendo, ya seleccionado para poder arrastrarlo a su sitio.</li>"
            "<li><b>Ctrl+Z</b> y <b>Ctrl+Y</b> deshacen y rehacen.</li></ul>"
            "<h3>Moverse por el documento</h3><ul>"
            "<li><b>Ctrl+rueda</b> hace zoom; <b>Ctrl+0</b> vuelve al 100%.</li>"
            "<li><b>Ctrl+F</b> busca texto; <b>F3</b> salta al siguiente resultado. <b>Esc</b> "
            "o el boton de cerrar quitan el resaltado amarillo.</li>"
            "<li>La barra lateral de miniaturas permite saltar de pagina.</li>"
            "<li><b>Esc</b> termina lo que estes haciendo y vuelve a la herramienta Seleccionar, dejando seleccionado lo que acabas de hacer para poder copiarlo, moverlo o borrarlo enseguida. Para deseleccionar, pincha en una zona vacia de la hoja.</li></ul>"
            "<h3>Guias</h3>"
            "<p>Arrastrando desde la regla de arriba o la del lado se suelta una guia. Las guias son de todo el documento: la misma linea sale en todas las paginas, asi que un margen o una columna quedan igual en todas. Sacandola fuera de la hoja desaparece, y en <b>Ver -&gt; Quitar las guias</b> se van todas.</p>"
            "<h3>Piezas de formulario</h3>"
            "<p>La pestana <b>Elementos</b> del panel lateral trae piezas ya hechas para "
            "montar formularios: campos con su raya para escribir, casillas, lineas de "
            "firma, titulos y tablas. Doble clic en una y cae en la pagina que estas "
            "viendo. Son anotaciones normales, asi que se editan y se mueven como todo "
            "lo demas, y cuando la hoja esta lista se puede guardar como plantilla.</p>"
            "<h3>Plantillas</h3>"
            "<p>En <b>Documento -&gt; Plantillas</b> puedes guardar lo que hayas montado "
            "(membretes, tablas, sellos, logotipos) y reutilizarlo: crear un documento nuevo a "
            "partir de una plantilla o aplicarla encima del PDF que tengas abierto, desde la "
            "pagina en la que estes. Se deshace de una vez con <b>Ctrl+Z</b>.</p>"
            "<h3>Como se guardan las anotaciones</h3>"
            "<p>El programa escribe anotaciones PDF estandar (cuadro, linea, texto libre, "
            "resaltado, tinta y poligono), asi que se ven igual en Adobe Reader, Edge o "
            "Firefox. Las tablas se guardan como su rejilla mas el texto de cada celda, y las "
            "imagenes se incrustan en la propia pagina para que se impriman siempre.</p>"
            "<h3>Versiones nuevas</h3>"
            "<p>El programa mira de vez en cuando la web oficial y avisa cuando sale una "
            "version mas nueva. Desde ese aviso se puede <b>descargar e instalar</b> sin "
            "salir de la aplicacion: coge el paquete que le toca a tu sistema, comprueba "
            "que la descarga coincide con la publicada y, en Windows, arranca el "
            "instalador. En el menu <b>Ayuda</b> puedes buscarlas a mano o apagar la "
            "comprobacion.</p>"
        ),
        "font_sans": "Sans",
        "font_serif": "Serif",
        "font_mono": "Monoespaciada",
        "act_align_left": "Alinear a la izquierda",
        "act_align_center": "Centrar",
        "act_align_right": "Alinear a la derecha",
        "kind_rect": "cuadro",
        "kind_highlight": "resaltado",
        "kind_line": "linea",
        "kind_arrow": "flecha",
        "kind_text": "texto",
        "kind_ink": "dibujo",
        "kind_table": "tabla",
        "kind_image": "imagen",
        "cmd_add": "Anadir {kind}",
        "cmd_delete_one": "Eliminar anotacion",
        "cmd_delete_many": "Eliminar {count} anotaciones",
        "cmd_change": "Modificar anotacion",
        "cmd_style": "Cambiar estilo",
        "cmd_page_add": "Anadir pagina",
        "cmd_page_duplicate": "Duplicar pagina",
        "cmd_page_delete": "Eliminar la pagina {page}",
        "cmd_page_move": "Mover la pagina {page}",
        "cmd_page_rotate": "Girar la pagina {page}",
        "cmd_erase": "Borrar con la goma",
        "cmd_template": "Aplicar plantilla ({count} anotaciones)",
        "cmd_paste": "Pegar ({count})",
        "new": "&Nuevo documento en blanco",
        "new_tip": "Crear un PDF vacio para empezar de cero",
        "open": "&Abrir...",
        "open_tip": "Abrir un documento PDF",
        "save": "&Guardar",
        "save_tip": "Guardar las anotaciones en el PDF",
        "save_as": "Guardar &como...",
        "save_as_tip": "Guardar una copia del PDF",
        "print": "&Imprimir...",
        "print_tip": "Imprimir el documento",
        "preview": "Vista pre&via de impresion...",
        "preview_tip": "Ver como quedara impreso",
        "close_doc": "&Cerrar documento",
        "quit": "&Salir",
        "menu_file": "&Archivo",
        "recent": "Abrir &reciente",
        "recent_clear": "Vaciar la lista",
        "menu_edit": "&Editar",
        "undo": "Deshacer",
        "redo": "Rehacer",
        "copy_sel": "&Copiar",
        "cut_sel": "Cor&tar",
        "paste_sel": "&Pegar",
        "delete_sel": "&Eliminar seleccion",
        "delete_sel_tip": "Eliminar las anotaciones seleccionadas",
        "select_all": "Seleccionar &todas las anotaciones",
        "find": "&Buscar texto...",
        "find_tip": "Buscar texto en el documento",
        "find_next": "Buscar &siguiente",
        "find_prev": "Buscar &anterior",
        "search_placeholder": "Buscar texto en el documento...",
        "search_close": "Cerrar y quitar el resaltado",
        "search_none": "  Sin resultados  ",
        "search_of": "  {current} de {total}  ",
        "search_not_found": "No se encontro '{text}'",
        "menu_view": "&Ver",
        "zoom_in": "&Acercar",
        "zoom_out": "A&lejar",
        "zoom_reset": "Zoom &100%",
        "fit_width": "Ajustar al &ancho",
        "fit_page": "Ajustar a la &pagina",
        "prev_page": "Pagina &anterior",
        "next_page": "Pagina &siguiente",
        "goto": "&Ir a la pagina...",
        "goto_title": "Ir a la pagina",
        "goto_label": "Numero de pagina (1-{total}):",
        "fullscreen": "Pantalla &completa",
        "thumbnails": "Panel de &miniaturas",
        "side_panel": "Panel &lateral (marcadores, notas, elementos)",
        "pages_dock": "Paginas",
        "menu_document": "&Documento",
        "page_add": "&Anadir una pagina al final",
        "page_insert": "&Insertar una pagina despues de esta",
        "page_duplicate": "&Duplicar esta pagina",
        "page_delete": "&Eliminar esta pagina",
        "page_up": "Mover la pagina &arriba",
        "page_down": "Mover la pagina aba&jo",
        "page_insert_before": "Insertar una pagina en blanco &antes",
        "page_insert_after": "Insertar una pagina en blanco &despues",
        "page_rotate_left": "Girar a la &izquierda (90\u00b0)",
        "page_rotate_right": "Girar a la &derecha (90\u00b0)",
        "page_rotate_180": "Girar 1&80\u00b0",
        "page_rotate_menu": "&Girar esta pagina",
        "size_same": "Igual que esta pagina",
        "size_A4": "A4",
        "size_A4 horizontal": "A4 horizontal",
        "size_Carta": "Carta",
        "size_Carta horizontal": "Carta horizontal",
        "size_A5": "A5",
        "size_A3": "A3",
        "size_Oficio": "Oficio",
        "page_move_undo": "Pagina {origin} movida a la posicion {target}",
        "page_size_menu": "&Tamano de las paginas nuevas",
        "templates": "&Plantillas",
        "template_save": "&Guardar esto como plantilla...",
        "template_save_tip": "Guardar las anotaciones actuales para reutilizarlas",
        "template_none": "(todavia no hay plantillas guardadas)",
        "template_new": "&Nuevo documento desde plantilla",
        "template_apply": "&Aplicar al documento de ahora",
        "template_delete": "&Eliminar una plantilla",
        "template_folder": "Abrir la &carpeta de plantillas",
        "template_name_title": "Guardar como plantilla",
        "template_name_label": "Nombre de la plantilla:",
        "template_saved": "Plantilla guardada: {name}",
        "template_applied": "Plantilla '{name}': {count} anotaciones colocadas desde la pagina {page}",
        "template_new_done": "Documento nuevo desde la plantilla '{name}'",
        "template_deleted": "Plantilla eliminada: {name}",
        "template_delete_ask": "Eliminar la plantilla '{name}'?",
        "template_empty": (
            "Todavia no hay nada que guardar: anade cuadros, textos, tablas o imagenes y "
            "vuelve a intentarlo."
        ),
        "template_detail": "{count} anotaciones",
        "template_detail_pages": "{pages} paginas, {count} anotaciones",
        "menu_tools": "&Herramientas",
        "tool_select": "&Seleccionar",
        "tool_pan": "&Mover la vista",
        "tool_rect": "&Cuadro",
        "tool_highlight": "&Resaltar",
        "tool_line": "&Linea",
        "tool_arrow": "&Flecha",
        "tool_text": "&Texto",
        "tool_ink": "&Dibujo libre",
        "tool_table": "Ta&bla",
        "tool_note": "&Nota",
        "bookmarks_dock": "Marcadores",
        "side_dock": "Panel",
        "notes_tab": "Notas",
        "templates_tab": "Plantillas",
        "tpl_included": "Incluidas",
        "tpl_mine": "Mias",
        "tpl_use": "Usar aqui",
        "tpl_new": "Documento nuevo",
        "tpl_save": "Guardar la actual...",
        "tpl_delete": "Borrar",
        "tpl_kind": "Tipo de plantilla:",
        "tpl_entry": "{name}  -  {pages} p., {count} elementos",
        "tpl_none": "No hay ningun documento abierto.",
        "cat_document": "Oficina",
        "cat_report": "Informes",
        "cat_certificate": "Certificados",
        "cat_letterhead": "Membretes",
        "cat_table": "Cuadros y facturas",
        "cat_form": "Formularios",
        "cat_other": "Otras",
        "notes_show_done": "Ver tambien las leidas",
        "elements_tab": "Elementos",
        "el_insert": "Insertar",
        "el_hint": "Doble clic en una pieza para soltarla en la pagina que estas viendo.",
        "elcat_field": "Campos",
        "elcat_choice": "Casillas",
        "elcat_signature": "Firmas",
        "elcat_layout": "Estructura",
        "el_text_field": "Campo con raya",
        "el_long_field": "Campo de tres rayas",
        "el_date_field": "Campo de fecha",
        "el_boxed_field": "Campo con recuadro",
        "el_checkbox": "Casilla",
        "el_checklist": "Lista de casillas",
        "el_yes_no": "Si / No",
        "el_signature": "Linea de firma",
        "el_two_signatures": "Dos firmas",
        "el_place_date": "Lugar y fecha",
        "el_heading": "Titulo con raya",
        "el_separator": "Linea separadora",
        "el_table": "Tabla con cabeceras",
        "el_note_box": "Recuadro de notas",
        "status_element_added": "{name} anadido",
        "cmd_element": "Insertar {name}",
        "note_entry": "p. {page}  -  {text}",
        "note_empty": "(nota vacia)",
        "update_check": "Buscar &actualizaciones",
        "update_auto": "Buscar actualizaciones al &arrancar",
        "update_title": "Hay una version nueva",
        "update_body": "Ha salido la version <b>{new}</b>. Tienes la {old}.",
        "update_go": "Ir a la pagina web",
        "update_later": "Ahora no",
        "update_skip": "Saltar esta version",
        "update_none": "Ya tienes la ultima version ({version}).",
        "update_failed": "No se ha podido comprobar si hay actualizaciones.",
        "update_checking": "Buscando actualizaciones...",
        "update_download": "Descargar e instalar",
        "update_downloading": "Descargando {name}",
        "update_progress": "{done} MB de {total} MB",
        "update_progress_unknown": "{done} MB descargados",
        "update_verifying": "Comprobando la descarga...",
        "update_ready_install": (
            "La descarga esta lista. EasyPDF se cerrara para que el "
            "instalador la sustituya."
        ),
        "update_ready_file": (
            "Guardado en:<br><b>{path}</b><br>Descomprimelo encima de tu copia "
            "actual para actualizar."
        ),
        "update_install_now": "Instalar ahora",
        "update_open_folder": "Abrir la carpeta",
        "update_download_failed": "La descarga ha fallado: {error}",
        "update_no_asset": (
            "Para este sistema todavia no hay descarga automatica. "
            "En la pagina web estan todos los paquetes."
        ),
        "update_cancel": "Cancelar",
        "update_close": "Cerrar",
        "cursor_pos": "{x} x {y} {unit}",
        "rulers": "&Reglas",
        "ruler_unit_menu": "&Unidades de la regla",
        "unit_mm": "Milimetros",
        "unit_cm": "Centimetros",
        "unit_in": "Pulgadas",
        "unit_pt": "Puntos",
        "snap": "&Alinear con las guias",
        "guides_clear": "Quitar todas las &guias",
        "guides_hint": "Arrastra desde una regla para poner una guia. Sacala de la pagina para quitarla.",
        "guide_at": "Guia en {value} {unit}",
        "bookmark_add": "Anadir",
        "bookmark_remove": "Quitar",
        "bookmark_prompt": "Nombre del marcador:",
        "bookmark_default": "Pagina {page}",
        "bookmark_entry": "{title}  -  p. {page}",
        "note_title": "Nota",
        "note_prompt": "Texto de la nota:",
        "tool_eraser": "&Goma",
        "eraser_size": "Goma: {size} pt  (Ctrl+ / Ctrl- o [ ] para el tamano)",
        "eraser_color_tip": "Color con el que tapa la goma (blanco = papel)",
        "tool_image": "&Imagen",
        "tool_status": "Herramienta: {name} ({key})",
        "hint_highlight": "Arrastra sobre el texto que quieras resaltar",
        "hint_text": "Arrastra para crear el cuadro y escribe; Esc para terminar",
        "hint_table": (
            "Arrastra para crear una tabla de {rows} x {cols}; doble clic en una celda "
            "para escribir, Tab pasa a la siguiente"
        ),
        "hint_image": (
            "Arrastra sobre la pagina para colocar {name}, o haz un clic para ponerla a "
            "un tamano comodo"
        ),
        "toolbar_main": "Principal",
        "toolbar_tools": "Herramientas",
        "toolbar_style": "Estilo",
        "toolbar_search": "Buscar",
        "color_tip": "Color del trazo y del texto",
        "fill_tip": "Color de relleno",
        "no_fill": "Sin relleno",
        "more_colours": "Mas colores...",
        "pick_colour": "Elegir color",
        "width": " Grosor ",
        "width_tip": "Grosor de la linea",
        "opacity": " Opacidad ",
        "opacity_tip": "Opacidad de la anotacion",
        "font_size": " Letra ",
        "font_size_tip": "Tamano del texto",
        "font_tip": "Tipo de letra",
        "bold": "Negrita",
        "bold_tip": "Negrita (Ctrl+B)",
        "italic": "Cursiva",
        "italic_tip": "Cursiva (Ctrl+I)",
        "table_label": " Tabla ",
        "rows_prefix": "filas ",
        "rows_tip": "Filas de la tabla",
        "cols_prefix": "col. ",
        "cols_tip": "Columnas de la tabla",
        "menu_help": "A&yuda",
        "help": "&Guia rapida",
        "about": "&Acerca de {app}",
        "website": "Pagina &web de easypdf.surf",
        "language": "&Idioma",
        "language_changed": "Idioma cambiado a espanol",
        "status_start": "Abre un PDF con Ctrl+O o arrastralo aqui",
        "status_page": "Pagina",
        "status_of": "de {total}",
        "status_opened": "Abierto: {path}",
        "status_saved": "Guardado: {path}",
        "status_printed": "Documento enviado a la impresora",
        "status_new": (
            "Documento nuevo. Anade paginas desde el menu Documento y guardalo con Ctrl+S"
        ),
        "status_image_placed": "Imagen colocada: {name}",
        "status_no_selection": "No hay ninguna anotacion seleccionada",
        "status_erased": "Borrado. Al guardar desaparece del archivo para siempre.",
        "status_pick_select": "No hay nada seleccionado. Pulsa Esc para volver a Seleccionar y pincha lo que quieras.",
        "status_copied": "{count} copiadas",
        "status_cut": "{count} cortadas",
        "status_pasted": "{count} pegadas",
        "status_clipboard_empty": "No hay nada de easypdf.surf que pegar",
        "status_annotations": "{count} anotaciones",
        "status_annotation": "1 anotacion",
        "status_editing": "Escribe la nota; Esc para terminar",
        "open_title": "Abrir PDF",
        "pdf_filter": "Documentos PDF (*.pdf);;Todos los archivos (*)",
        "image_filter": (
            "Imagenes (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;"
            "Todos los archivos (*)"
        ),
        "image_title": "Elegir imagen",
        "image_unreadable": "No se pudo leer la imagen:\n{error}",
        "image_invalid": "Ese archivo no parece una imagen que se pueda abrir.",
        "save_title": "Guardar PDF como",
        "password_title": "Documento protegido",
        "password_label": "Contrasena para {name}:",
        "no_such_file": "No existe el archivo:\n{path}",
        "unsaved_title": "Anotaciones sin guardar",
        "unsaved": "El documento tiene anotaciones sin guardar.\n\nQuieres guardarlas?",
        "delete_page_ask": "Eliminar la pagina {page} de {total}?",
        "delete_page_annots": "\n\nSe borraran tambien sus {count} anotaciones.",
        "delete_page_undo": "\n\nSe puede deshacer con Ctrl+Z.",
        "last_page": "El documento no puede quedarse sin paginas.",
        "print_restricted": (
            "Este PDF pide no ser impreso.\n\nEsa restriccion no esta protegida por "
            "contrasena, asi que el programa puede imprimirlo igualmente.\n\nSolo hazlo si "
            "tienes derecho a ello. Continuar?"
        ),
        "print_failed": "No se pudo iniciar la impresion.",
        "print_title": "Imprimir documento",
        "print_preview_title": "Vista previa de impresion",
        "print_preparing": "Preparando paginas...",
        "print_page_of": "Pagina {page} de {total}",
    },
}

_current = DEFAULT_LANGUAGE
_listeners: list[Callable[[str], None]] = []


def language() -> str:
    """Idioma activo."""
    return _current


def set_language(code: str) -> str:
    """Cambia el idioma y avisa a quien lo haya pedido."""
    global _current
    code = code if code in TEXTS else DEFAULT_LANGUAGE
    if code != _current:
        _current = code
        for aviso in list(_listeners):
            aviso(code)
    return _current


def on_language_changed(callback: Callable[[str], None]) -> None:
    _listeners.append(callback)


def system_language(locale_name: str = "") -> str:
    """Idioma que toca segun el sistema, si lo tenemos traducido."""
    codigo = (locale_name or "").replace("-", "_").split("_")[0].lower()
    return codigo if codigo in TEXTS else DEFAULT_LANGUAGE


def tr(key: str, /, **kwargs) -> str:
    """Texto en el idioma activo. Si falta, cae al ingles y luego a la clave.

    La clave es un parametro solo posicional para que los textos puedan llevar
    un campo llamado ``key`` (por ejemplo el atajo de teclado).
    """
    texto = TEXTS.get(_current, {}).get(key) or TEXTS[DEFAULT_LANGUAGE].get(key) or key
    return texto.format(**kwargs) if kwargs else texto


__all__ = [
    "LANGUAGES",
    "language",
    "on_language_changed",
    "set_language",
    "system_language",
    "tr",
]


def page_size_label(name: str) -> str:
    """Nombre visible de un tamano de pagina en el idioma actual.

    Las claves de PAGE_SIZES son identificadores internos (y estan en
    castellano por historia); esto las traduce solo de cara al usuario, sin
    tocar lo que se guarda en los ajustes ni en las plantillas.
    """
    clave = f"size_{name}"
    return tr(clave) if clave in TEXTS[DEFAULT_LANGUAGE] else name
