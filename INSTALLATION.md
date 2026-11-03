# Installation

KOMPRESS-OR.CLI runs on Python **3.14+** and depends only on **Pillow** and
**Rich**. Everything else (Zenity, Tkinter) is optional integration that the
application detects at runtime.

## CachyOS / Linux

### 1. Install Python and build prerequisites

```bash
# CachyOS / Arch
sudo pacman -S python python-pip python-virtualenv

# Fedora
sudo dnf install python3 python3-pip python3-virtualenv

# Debian / Ubuntu
sudo apt install python3 python3-pip python3-venv
```

Python 3.14 or newer is required (`python --version`).

### 2. (Optional) install Zenity for the graphical file picker

```bash
# CachyOS / Arch
sudo pacman -S zenity
# Fedora
sudo dnf install zenity
# Debian / Ubuntu
sudo apt install zenity
```

Without Zenity the app still works perfectly — you type file paths
(separated by commas for multiple files).

### 3. Create a virtual environment and install

```bash
cd <repository-folder>
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 4. Launch

```bash
./kompressor            # easiest: uses .venv automatically
```

or with the virtual environment activated:

```bash
source .venv/bin/activate
kompressor
# or
python -m kompressor
```

Windows (after `pip install -e ".[dev]"` as above):

```powershell
.venv\Scripts\Activate.ps1
kompressor
```

## Windows 10 / Windows 11

1. Install Python 3.14+ from <https://www.python.org/downloads/> and tick
   **"Add python.exe to PATH"** during setup.
2. Open **PowerShell** or **Command Prompt**:

```powershell
cd <repository-folder>
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
kompressor
```

Notes for Windows:

- The file picker uses the built-in **Tkinter** dialog. If your Python build
  ships without Tk, the app falls back to manual path input automatically.
- If PowerShell blocks activation scripts, run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use the
  plain `cmd.exe` prompt with `.venv\Scripts\activate.bat`.

## Dependency installation only (no editable install)

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m kompressor
```

## Verify the installation

```bash
kompressor --check
```

Expected output lists each encoder and whether it is available, e.g.:

```
KOMPRESS-OR.CLI 1.0.0
Settings file: /home/you/.config/kompressor/settings.json
Encoders:
  JPEG: available
  PNG: available
  WebP: available
  AVIF: available
...
Available output formats: JPEG, PNG, WebP, TIFF, BMP, AVIF
```

`AVIF: UNAVAILABLE` is not an error — it means your Pillow build lacks the
AVIF encoder and the app will offer the formats that do work.

## Running the tests

```bash
./run-tests              # from the repository root, no activation needed
# or, with the venv activated:
pytest
```

All test images are generated programmatically; no sample files are needed.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `kompressor: command not found` | The venv is not activated. Use `source .venv/bin/activate`, or run `./kompressor` (uses `.venv` automatically), or `python -m kompressor` inside the venv. |
| `Pillow` / `rich` import errors | Install dependencies: `pip install -r requirements.txt`. |
| `Python 3.14+ required` | Your system Python is older; create the venv with a 3.14+ interpreter. |
| File picker never opens | No graphical session, Zenity/Tk missing, or `KOMPRESS_NO_PICKER=1` is set. Type paths manually — everything works without a GUI. |
| `AVIF output is not available` | Reinstall a Pillow build with AVIF (`pip install --force-reinstall Pillow`), or choose JPEG/WebP/PNG. |
| `libtk8.6.so` / Tkinter errors on Linux | `sudo pacman -S tk` (or `sudo apt install python3-tk`); the app falls back to manual input meanwhile. |
| Settings seem reset after a crash | A corrupted `settings.json` is moved to `settings.json.corrupt` and defaults are restored — open the `.corrupt` file to inspect it. |
| Colors look wrong in a legacy terminal | The app uses Rich's default color system; run in a modern terminal (Windows Terminal, konsole, kitty, gnome-terminal). |
