#!/usr/bin/env bash
# Compila EasyPDF para Linux y deja el paquete en build/
#
#   ./packaging/build_linux.sh
#
# Resultado: build/EasyPDF-<version>-linux-x64.tar.xz
# Dentro del tar hay una carpeta EasyPDF/ autocontenida: se descomprime y se
# ejecuta ./EasyPDF, sin instalar nada ni necesitar Python.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VERSION="$($PYTHON -c "import re;print(re.search(r'__version__ = \"(.+)\"', open('src/easypdf/__init__.py').read()).group(1))")"
NOMBRE="EasyPDF-${VERSION}-linux-x64"

echo "== EasyPDF ${VERSION}: compilando para Linux"

echo "-- Pruebas"
QT_QPA_PLATFORM=offscreen $PYTHON -m pytest -q

echo "-- Icono"
$PYTHON tools/make_icon.py

echo "-- PyInstaller"
rm -rf .pyinstaller dist/EasyPDF
$PYTHON -m PyInstaller packaging/easypdf.spec --noconfirm --clean \
    --workpath "$ROOT/.pyinstaller" --log-level WARN

echo "-- Comprobando el ejecutable"
QT_QPA_PLATFORM=offscreen ./dist/EasyPDF/EasyPDF --version

echo "-- Empaquetando"
cp LICENSE dist/EasyPDF/LICENSE.txt
cat > dist/EasyPDF/LEEME.txt <<'TXT'
EasyPDF - lector y anotador de PDF
==================================

Para ejecutarlo:

    ./EasyPDF                 (o bien:  ./EasyPDF documento.pdf)

No hace falta instalar nada ni tener Python. Si el sistema es muy minimo,
puede que falten bibliotecas de Qt:

    sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3

Codigo fuente y licencia (GNU AGPL v3): https://github.com/mefardales/easypdf
TXT

mkdir -p build
rm -f "build/${NOMBRE}.tar.xz"
XZ_OPT='-6 -T0' tar cJf "build/${NOMBRE}.tar.xz" -C dist EasyPDF

( cd build && sha256sum "${NOMBRE}.tar.xz" > "${NOMBRE}.tar.xz.sha256" )

echo "== Listo -> build/${NOMBRE}.tar.xz  ($(du -h "build/${NOMBRE}.tar.xz" | cut -f1))"
