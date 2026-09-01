# easypdf.surf builds

This folder holds the already-built programs, ready to use. **You do not need
Python installed.**

The easiest way to download is the project's site:
**[easypdf.surf](https://easypdf.surf)**.

Here too: click the file name and the download starts on its own:

| Download | Who it is for | What it is |
|---|---|---|
| [**EasyPDF-1.6.2-Setup.exe**](https://github.com/mefardales/easypdf/releases/download/v1.6.2/EasyPDF-1.6.2-Setup.exe) | Windows 10/11 (64 bit) | Installer. It creates the shortcut, registers the application under *Open with* and uninstalls from *Settings -> Apps*. It needs no administrator rights: it can be installed for your user only. |
| [**EasyPDF-1.6.2-windows-x64-portable.zip**](https://github.com/mefardales/easypdf/releases/download/v1.6.2/EasyPDF-1.6.2-windows-x64-portable.zip) | Windows 10/11 (64 bit) | Portable version. Unpack the folder and run `EasyPDF.exe`. It installs nothing and does not touch the registry: it works from a USB stick. |
| [**EasyPDF-1.6.2-linux-x64.tar.xz**](https://github.com/mefardales/easypdf/releases/download/v1.6.2/EasyPDF-1.6.2-linux-x64.tar.xz) | Linux (x86-64) | Portable version. Unpack and run `./EasyPDF`. |

Checking the `sha256` is **optional**: only if you want to make sure the download
arrived intact. There is one next to every file:

```bash
sha256sum -c EasyPDF-1.6.2-linux-x64.tar.xz.sha256      # Linux
```

```powershell
Get-FileHash EasyPDF-1.6.2-Setup.exe -Algorithm SHA256  # Windows
```

## How to use them

**Windows (installer)** — double click `EasyPDF-1.6.2-Setup.exe` and press next.
Windows SmartScreen may warn that the publisher is unknown, because the
executable is not digitally signed (a code signing certificate costs money):
press *More info -> Run anyway*.

**Windows (portable)** — unpack the `.zip` and run `EasyPDF.exe` from inside the
folder. Keep the whole folder, not just the `.exe`.

**Linux** —

```bash
tar xf EasyPDF-1.6.2-linux-x64.tar.xz
cd EasyPDF
./EasyPDF                 # or:  ./EasyPDF document.pdf
```

On a very minimal system some Qt libraries may be missing:

```bash
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 libdbus-1-3
```

**macOS** — there is no published build; run it from source
(`pip install -r requirements.txt && python -m easypdf`).

## Where these files come from

They are always produced by the repository's own scripts, never by hand:

| Platform | How it is built |
|---|---|
| Windows | `.github/workflows/build-windows.yml` on a `windows-latest` runner (PyInstaller + Inno Setup). It can also be done locally: `powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1` |
| Linux | `.github/workflows/build-linux.yml` on `ubuntu-22.04`, or locally: `bash packaging/build_linux.sh` |

The Windows executables can only be built **from Windows**: PyInstaller does not
cross-compile for a platform other than the one it runs on.

To publish a new version it is enough to tag it; both workflows build and attach
the files to the GitHub release:

```bash
git tag v1.6.2
git push origin v1.6.2
```
