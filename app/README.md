# LayoutLingua Desktop Application (`app`)

The `app` directory implements the native desktop Graphical User Interface (GUI) for LayoutLingua.

## Architecture

- **UI Framework**: Built with [`customtkinter`](https://github.com/TomSchimansky/CustomTkinter) providing high-DPI scaling, modern dark/light mode themes, and fluid component styling.
- **Drag & Drop**: Integrated via `tkinterdnd2` for direct PDF file dropping.
- **Threading Model**: 
  - UI event loop runs on the main thread with a 20ms animation tick.
  - PDF translation jobs execute on dedicated background worker threads to ensure the UI remains fully responsive.
  - Thread-safe communication uses queue-based events (`self.events.put(...)`).
- **Warmup & Preloading**:
  - The DocLayout-YOLO ONNX model is warmed up asynchronously on background threads while the user browses files, eliminating cold-start latency.

---

## File Structure

| File | Purpose |
|---|---|
| [`gui.py`](gui.py) | Main window layout, drag-and-drop dropzone, language picker, progress indicators, translation trigger. |
| [`errors.py`](errors.py) | Human-readable Vietnamese error mappings for engine failures (e.g. `E-PDF-01`, `E-PDF-03` image-only scan). |
| [`update.py`](update.py) | Automatic GitHub release update checking, version metadata (`APP_VERSION`), and PowerShell/Bash self-updater. |
| [`history.py`](history.py) | Local history log of translated documents and outputs. |
| [`assets/`](assets/) | Application icons (`icon.ico`, `icon.png`, `dropzone_upload.png`). |

---

## Running the Application Locally

```bash
# Run with Python
python app/gui.py

# Or via Windows launch batch script
.\run_gui.bat
```

## Packaging & Building

The application bundles into single-file or folder distributions using PyInstaller:
- **Windows**: `powershell -File build.ps1` (uses `app.spec`)
- **macOS**: `bash build-macos.sh` (uses `app-macos.spec`)
- **Linux**: `bash build-linux.sh` (uses `app-linux.spec`)
