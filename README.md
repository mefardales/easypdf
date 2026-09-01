<p align="center">
  <img src="assets/easypdf.png" width="120" alt="easypdf.surf">
</p>

<h1 align="center">easypdf.surf</h1>

<p align="center">
  <b>A simple PDF reader with annotations and printing.</b><br>
  Open, read, print and draw boxes, lines, arrows and text on top of your PDFs.<br>
  Like Adobe Reader, but far simpler, free and open source.
</p>

<p align="center">
  <b><a href="https://easypdf.surf">easypdf.surf</a></b>
</p>

<p align="center">
  <a href="LICENSE"><img alt="AGPL v3 licence" src="https://img.shields.io/badge/licence-AGPL--3.0-blue.svg"></a>
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-3776ab.svg">
  <img alt="Windows, Linux, macOS" src="https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg">
</p>

---

## Download (one click)

The easiest way is the project's own site:
**[easypdf.surf](https://easypdf.surf)**.
You can also download straight from here:

### Windows 10 or 11

<p align="center">
  <a href="https://github.com/mefardales/easypdf/releases/download/v1.6.2/EasyPDF-1.6.2-Setup.exe">
    <img src="https://img.shields.io/badge/%E2%AC%87%20DOWNLOAD%20EasyPDF%20for%20Windows-installer-d81b1b?style=for-the-badge" alt="Download EasyPDF for Windows">
  </a>
</p>

1. Press the button above: `EasyPDF-1.6.2-Setup.exe` downloads.
2. Double click the downloaded file (it usually lands in your *Downloads* folder).
3. If Windows shows a blue *Windows protected your PC* notice, press
   **More info** and then **Run anyway**. It appears because the program is not
   signed with a paid certificate, not because there is anything odd about it.
4. Next, next, done. easypdf.surf is in the Start menu.

You do not need administrator rights, or Python, or anything else.

<details>
<summary>Other downloads (portable and Linux)</summary>

<br>

| Download | What it is for |
|---|---|
| [**EasyPDF portable for Windows (.zip)**](https://github.com/mefardales/easypdf/releases/download/v1.6.2/EasyPDF-1.6.2-windows-x64-portable.zip) | Installs nothing. Unpack the folder and open `EasyPDF.exe`. It runs from a USB stick. |
| [**EasyPDF for Linux (.tar.xz)**](https://github.com/mefardales/easypdf/releases/download/v1.6.2/EasyPDF-1.6.2-linux-x64.tar.xz) | Unpack and run `./EasyPDF`. No installation needed. |

They are all in the [`build/`](build/) folder too, and on the
[releases page](https://github.com/mefardales/easypdf/releases), each with its
`sha256` so you can check the download.

</details>

## What it does

| | |
|---|---|
| **Read** | Continuous scrolling, page thumbnails, zoom, fit to width or page, text search (`Ctrl+F`), password protected documents. |
| **Create** | Blank documents (`Ctrl+N`), add, duplicate, move and delete pages, in A4, Letter, A5, A3 or Legal, portrait or landscape. |
| **Annotate** | Boxes, highlighting, lines, arrows, text boxes, freehand drawing, **tables** with editable cells and **images** (drag them onto the window). Sans, serif or monospaced font, bold, italic and alignment. They move, resize, change colour and can be deleted. Unlimited undo and redo. |
| **Erase** | A real eraser: it takes the annotations it runs over with it, and on save it strips the original content underneath as well, so what was rubbed out cannot be selected or copied out of the file afterwards. |
| **Fill in** | Ready-made **form pieces** — labelled fields, tick boxes, signature lines, tables and separators — dropped onto the page with a click. |
| **Reuse** | Save letterheads, tables or stamps as **templates** and build them again in another document with one click. |
| **Print** | The system print dialog, print preview, page ranges. What is printed includes the annotations. |
| **Save** | Annotations are written as **standard PDF annotations**: they look the same in Adobe Reader, Edge or Firefox, and the document's original content is left untouched. |

Interface in **English and Spanish** (switch it under *Help -> Language*; it starts
in the system's language), no accounts, no ads and no internet connection needed.
It checks on its own whether a newer version is out and offers to download and
install it; that check can be turned off in the *Help* menu.

## Tools in the browser

Six of the things people need most often also run at
**[easypdf.surf/tools](https://easypdf.surf/tools/)**, with nothing to install:
merge, split, rotate and reorder, delete pages, images to PDF and PDF to image.

They run entirely in the browser — the file is never uploaded anywhere — and
they install on a phone as an app that keeps working with no connection. The
source is in `site/tools/`, built by `tools/build_tools.py`.

## Screenshot

<p align="center">
  <img src="docs/screenshot.png" width="820" alt="The main easypdf.surf window">
</p>

## Quick guide

| Action | Shortcut |
|---|---|
| Open / Save / Save as | `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` |
| Print / Print preview | `Ctrl+P` / `Ctrl+Shift+P` |
| Find / Next / Previous | `Ctrl+F` / `F3` / `Shift+F3` |
| Undo / Redo | `Ctrl+Z` / `Ctrl+Y` |
| Copy / Cut / Paste | `Ctrl+C` / `Ctrl+X` / `Ctrl+V` |
| Zoom | `Ctrl+wheel`, `Ctrl++`, `Ctrl+-`, `Ctrl+0` |
| Fit to width / to page | `Ctrl+1` / `Ctrl+2` |
| Go to page | `Ctrl+G` |
| New document / Add page | `Ctrl+N` / `Ctrl+Shift+N` |
| Show or hide the side panel | `F10` |
| Tools | `S` select, `H` pan, `R` box, `M` highlight, `L` line, `F` arrow, `T` text, `D` drawing, `A` table, `I` image, `E` eraser |
| Bold / Italic | `Ctrl+B` / `Ctrl+I` |
| Cancel / back to select | `Esc` |
| Delete the selection | `Del` |

Useful details:

- Drag a PDF onto the window to open it.
- Hold **Shift** while drawing for perfect squares or 45 degree lines.
- Double click a text box to type inside it; `Esc` to finish.
- The blue handles on a selected annotation resize it.
- The colour, width and opacity in the toolbar apply both to the next annotation
  and to whatever you have selected.
- Drag from a ruler to drop a guide; guides show on every page and annotations
  snap to them.
- With the eraser in hand, `Ctrl++` and `Ctrl+-` (or `[` and `]`) change its size.

## Running from source

It works the same on Windows, Linux and macOS.

```bash
git clone https://github.com/mefardales/easypdf.git
cd easypdf

python -m venv .venv
# Windows:        .venv\Scripts\activate
# Linux / macOS:  source .venv/bin/activate

pip install -r requirements.txt
python -m easypdf                 # or:  python -m easypdf document.pdf
```

On Linux, Qt needs a few system libraries:

```bash
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3
```

## Building the .exe and the installer

### Windows: all at once

With [Inno Setup 6](https://jrsoftware.org/isdl.php) installed (optional):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

The script creates the virtual environment, installs the dependencies,
regenerates the icon, runs the tests and leaves the result in:

```
dist\EasyPDF\EasyPDF.exe                              <- runnable folder
build\EasyPDF-1.6.2-Setup.exe                         <- installer
build\EasyPDF-1.6.2-windows-x64-portable.zip          <- portable
```

### Windows: step by step

```powershell
pip install -r requirements-dev.txt
python tools\make_icon.py                     # builds assets\easypdf.ico
pyinstaller packaging\easypdf.spec --noconfirm --clean --workpath .pyinstaller
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

### Linux

```bash
bash packaging/build_linux.sh                 # -> build/EasyPDF-1.6.2-linux-x64.tar.xz
```

> The Windows executables can only be built from Windows: PyInstaller does not
> cross-compile for a platform other than the one it runs on.

### Automated builds

The workflows `.github/workflows/build-windows.yml` and `build-linux.yml` build on
Windows and Linux runners. They can be started by hand from the *Actions* tab
(they store the result in `build/`) and they also fire on every tag. To publish a
version:

```bash
git tag v1.6.2
git push origin v1.6.2
```

GitHub Actions runs the tests, packages everything and attaches the three files to
the release.

> The version number lives in `src/easypdf/__init__.py`. Update it there and in
> `pyproject.toml`, `packaging/installer.iss` and `packaging/version_info.txt`;
> `tests/test_version.py` checks the four agree.

### Changing the icon

The current icon is drawn in code in `src/easypdf/ui/icons.py`. If you would
rather use your own image, leave a square PNG (512x512 with a transparent
background works nicely) at `assets/easypdf-original.png` and run:

```bash
python tools/make_icon.py
```

`assets/easypdf.ico` and `assets/easypdf.png` are regenerated in every size, and
the window, the executable and the installer all use that image.

## How annotations are stored

easypdf.surf **never modifies the PDF's original content**. It always keeps the
file's bytes as they were when it was opened and, on save, adds the current
annotations to them:

| Tool | PDF annotation written |
|---|---|
| Box | `Square` |
| Highlight | `Highlight` |
| Line and arrow | `Line` (the arrow with a closed head) |
| Text | `FreeText` (Helvetica, Times or Courier; bold and italic as rich text) |
| Table | `Ink` for the grid + one `FreeText` per cell that has text |
| Image | embedded in the page content (not an annotation, so it always prints) |
| Freehand drawing | `Ink` |
| Eraser | a redaction: the content underneath is removed from the file |

Because it always starts from the original file, saving twice duplicates nothing
and the annotations stay editable for the whole session. When the saved file is
opened again the annotations are visible (the PDF itself draws them) but they are
part of the document from then on.

Coordinates are stored in PDF points with the origin at the top left, and the
page's rotation is corrected, so what you draw is exactly what comes out printed,
even on rotated pages.

## Project layout

```
src/easypdf/
  model.py          The annotation model (pure Python, no Qt and no PDF)
  elements.py       Ready-made pieces for building forms
  templates.py      Reusable templates (JSON)
  i18n.py           Interface texts in English and Spanish
  document.py       Opening, rendering, searching and saving (PyMuPDF)
  annotations.py    Model -> real PDF annotations
  printing.py       Printing and print preview
  updates.py        New version check, download and install
  config.py         Preferences (QSettings)
  app.py            Application start-up
  ui/
    main_window.py  Menus, toolbars, thumbnails, search
    page_view.py    The viewer, the tools, zoom and navigation
    items.py        Annotations drawn on screen
    commands.py     Undo / redo
    rulers.py       Rulers and guides
    icons.py        Icons drawn in code
packaging/          PyInstaller + Inno Setup + build scripts
build/              Published executables (Windows and Linux)
site/               The web page (English at /, Spanish at /es/; tools/build_site.py)
site/tools/         The browser tools: a PWA that runs entirely on the visitor's
                    device (pdf-lib + pdf.js, both vendored, no CDN)
render.yaml         Deploying the site on Render
tools/make_icon.py  Builds assets/easypdf.ico
tools/build_tools.py  Builds the browser tools pages
tests/              340 tests (model, PDF, templates, interface, printing,
                    updates, and the browser tools driven in a real Chromium)
```

## Development

```bash
pip install -r requirements-dev.txt
pytest -q          # tests (the interface is tested in offscreen mode)
ruff check src tests tools
```

The browser tools are driven in a real Chromium. Those tests skip themselves
when there is no browser around, which is the case on the CI runners; to run
them locally:

```bash
pip install playwright && playwright install chromium
pytest tests/test_tools_browser.py -q
```

To work on the site: `python tools/build_site.py` regenerates both pages, the
`robots.txt` and the `sitemap.xml`. How it is published is in
[docs/WEB-DEPLOYMENT.md](docs/WEB-DEPLOYMENT.md).

Contributions are welcome: read [CONTRIBUTING.md](CONTRIBUTING.md).

## Roadmap

- [x] Rotate pages and save the rotation
- [ ] Select and copy text from the document
- [ ] Highlighting snapped to the selected lines of text
- [x] Stamps and signing with an image
- [ ] Merge several PDFs into one
- [x] English interface

## Licence

easypdf.surf is free software under the **[GNU AGPL v3 or later](LICENSE)**.

It uses [PyMuPDF](https://pymupdf.readthedocs.io/) (AGPL-3.0) to read and write
PDFs and [PySide6](https://doc.qt.io/qtforpython/) (LGPL-3.0) for the interface.
Because it links against PyMuPDF, any distributed version must also be published
under the AGPL with its source code available.
