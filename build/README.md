# Compilados de easypdf.surf

Esta carpeta contiene los programas ya compilados, listos para usar. **No hace
falta tener Python instalado.**

La forma mas comoda de descargar es la web del proyecto:
**[mefardales.github.io/easypdf](https://mefardales.github.io/easypdf/)**.

Aqui tambien: pulsa el nombre del archivo y la descarga empieza sola:

| Descarga | Para quien | Que es |
|---|---|---|
| [**EasyPDF-1.0.0-Setup.exe**](https://github.com/mefardales/easypdf/raw/main/build/EasyPDF-1.0.0-Setup.exe) | Windows 10/11 (64 bits) | Instalador. Crea el acceso directo, registra la aplicacion en *Abrir con* y se desinstala desde *Configuracion -> Aplicaciones*. No necesita permisos de administrador: puede instalarse solo para tu usuario. |
| [**EasyPDF-1.0.0-windows-x64-portable.zip**](https://github.com/mefardales/easypdf/raw/main/build/EasyPDF-1.0.0-windows-x64-portable.zip) | Windows 10/11 (64 bits) | Version portable. Descomprime la carpeta y ejecuta `EasyPDF.exe`. No instala nada ni toca el registro: funciona desde un pendrive. |
| [**EasyPDF-1.0.0-linux-x64.tar.xz**](https://github.com/mefardales/easypdf/raw/main/build/EasyPDF-1.0.0-linux-x64.tar.xz) | Linux (x86-64) | Version portable. Descomprime y ejecuta `./EasyPDF`. |

Comprobar el `sha256` es **opcional**: solo si quieres verificar que la descarga
llego intacta. Junto a cada archivo hay uno:

```bash
sha256sum -c EasyPDF-1.0.0-linux-x64.tar.xz.sha256      # Linux
```

```powershell
Get-FileHash EasyPDF-1.0.0-Setup.exe -Algorithm SHA256  # Windows
```

## Como usarlos

**Windows (instalador)** — doble clic en `EasyPDF-1.0.0-Setup.exe` y siguiente.
Windows SmartScreen puede avisar de que el editor es desconocido, porque el
ejecutable no esta firmado digitalmente (una firma de codigo es de pago): pulsa
*Mas informacion -> Ejecutar de todas formas*.

**Windows (portable)** — descomprime el `.zip` y ejecuta `EasyPDF.exe` de dentro
de la carpeta. Hay que mantener la carpeta entera, no solo el `.exe`.

**Linux** —

```bash
tar xf EasyPDF-1.0.0-linux-x64.tar.xz
cd EasyPDF
./EasyPDF                 # o:  ./EasyPDF documento.pdf
```

Si el sistema es muy minimo puede que falten bibliotecas de Qt:

```bash
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3
```

**macOS** — no hay compilado publicado; se ejecuta desde el codigo fuente
(`pip install -r requirements.txt && python -m easypdf`).

## De donde salen estos archivos

Se generan siempre con los mismos guiones del repositorio, nunca a mano:

| Plataforma | Como se genera |
|---|---|
| Windows | `.github/workflows/build-windows.yml` en un runner `windows-latest` (PyInstaller + Inno Setup). Tambien se puede en local: `powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1` |
| Linux | `.github/workflows/build-linux.yml` en `ubuntu-22.04`, o en local: `bash packaging/build_linux.sh` |

Los ejecutables de Windows solo se pueden generar **desde Windows**: PyInstaller
no compila para otra plataforma distinta de aquella en la que se ejecuta.

Para publicar una version nueva basta con etiquetarla; los dos flujos compilan y
adjuntan los archivos a la release de GitHub:

```bash
git tag v1.0.0
git push origin v1.0.0
```
