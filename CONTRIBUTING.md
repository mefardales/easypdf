# Contributing to easypdf.surf

Thanks for wanting to lend a hand. easypdf.surf aims to stay **simple**: before
adding a feature, ask yourself whether somebody who only wants to read and
annotate a PDF would miss it.

## Setting up

```bash
git clone https://github.com/mefardales/easypdf.git
cd easypdf
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m easypdf                # starts the application
```

## Before opening a pull request

```bash
pytest -q                        # every test green
ruff check src tests tools       # no style warnings
```

If you touch the interface, add a test in `tests/test_ui.py`: they run with the
Qt `offscreen` platform, so they work without a screen and on continuous
integration.

## How the code is laid out

- `model.py` is pure Python: no Qt and no PyMuPDF. Any logic that can be tested
  without an interface belongs there.
- `document.py` and `annotations.py` are the only border with PyMuPDF.
- The interface (`ui/`) never talks to PyMuPDF directly.
- Annotation coordinates are always in **PDF points** with the origin at the top
  left. Never store screen coordinates.

## Style

- Interface texts go in `src/easypdf/i18n.py`, never loose in the code:
  `tr("my_key")`. Every new text is added to both languages (a test checks
  that). Function and variable names in English.
- Comments only where the code does not explain itself.
- Lines up to 100 characters (`ruff` checks that).

## Reporting a bug

Open an issue giving the EasyPDF version, your operating system and, if you can,
an example PDF (or an equivalent one without personal data) and the steps to
reproduce it.

## Licence of contributions

By sending a pull request you agree to publish your code under the
[GNU AGPL v3 or later](LICENSE), the same licence as the project.
