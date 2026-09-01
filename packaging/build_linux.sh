#!/usr/bin/env bash
# Builds EasyPDF for Linux and leaves the package in build/
#
#   ./packaging/build_linux.sh
#
# Result: build/EasyPDF-<version>-linux-x64.tar.xz
# Inside the tar there is a self-contained EasyPDF/ folder: unpack it and run
# ./EasyPDF, with nothing to install and no Python needed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VERSION="$($PYTHON -c "import re;print(re.search(r'__version__ = \"(.+)\"', open('src/easypdf/__init__.py').read()).group(1))")"
NAME="EasyPDF-${VERSION}-linux-x64"

echo "== EasyPDF ${VERSION}: building for Linux"

echo "-- Tests"
QT_QPA_PLATFORM=offscreen $PYTHON -m pytest -q

echo "-- Icon"
$PYTHON tools/make_icon.py

echo "-- PyInstaller"
rm -rf .pyinstaller dist/EasyPDF
$PYTHON -m PyInstaller packaging/easypdf.spec --noconfirm --clean \
    --workpath "$ROOT/.pyinstaller" --log-level WARN

echo "-- Checking the executable"
QT_QPA_PLATFORM=offscreen ./dist/EasyPDF/EasyPDF --version

echo "-- Packaging"
cp LICENSE dist/EasyPDF/LICENSE.txt
cat > dist/EasyPDF/README.txt <<'TXT'
EasyPDF - PDF reader and annotator
==================================

To run it:

    ./EasyPDF                 (or:  ./EasyPDF document.pdf)

There is nothing to install and no need for Python. On a very minimal system
some Qt libraries may be missing:

    sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3

Source code and licence (GNU AGPL v3): https://github.com/mefardales/easypdf
TXT

mkdir -p build
rm -f "build/${NAME}.tar.xz"
XZ_OPT='-6 -T0' tar cJf "build/${NAME}.tar.xz" -C dist EasyPDF

( cd build && sha256sum "${NAME}.tar.xz" > "${NAME}.tar.xz.sha256" )

echo "== Done -> build/${NAME}.tar.xz  ($(du -h "build/${NAME}.tar.xz" | cut -f1))"
