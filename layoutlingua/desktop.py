"""Native Desktop Application launcher and standalone executable builder for LayoutLingua.

Runs the Python PDF translation & typesetting engine together with the compiled UI
inside a native OS desktop window (via pywebview WebView2/WebKit or native OS App host)
without opening a web browser tab or requiring a running Vite dev server.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from layoutlingua.server import start_server


def _get_bundle_root() -> Path:
    """Resolve root directory whether running from source or a PyInstaller bundle."""
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def _find_free_port(preferred: int = 8765) -> int:
    """Return preferred port if available on 127.0.0.1, else pick an ephemeral free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])


def _ensure_frontend_built(root_dir: Path) -> None:
    """Ensure dist/index.html exists before opening the native desktop window."""
    dist_index = root_dir / "dist" / "index.html"
    if dist_index.is_file() or hasattr(sys, "_MEIPASS"):
        return

    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    if shutil.which(npm_cmd) is None:
        return

    if not (root_dir / "node_modules").is_dir():
        print("[LayoutLingua Desktop] Installing UI dependencies...")
        subprocess.run([npm_cmd, "install", "--legacy-peer-deps"], cwd=str(root_dir), check=False)

    print("[LayoutLingua Desktop] Building production desktop UI bundle...")
    subprocess.run([npm_cmd, "run", "build"], cwd=str(root_dir), check=True)


def _find_native_app_host_binary() -> str | None:
    """Locate native Edge WebView / Chromium binary for frameless --app window fallback."""
    if sys.platform == "win32":
        candidates = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
    elif sys.platform == "darwin":
        mac_candidates = [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
        for c in mac_candidates:
            if os.path.isfile(c):
                return c
    else:
        for name in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
            found = shutil.which(name)
            if found:
                return found
    return None


def _schedule_window_icon_setup(window_title: str) -> None:
    """Ensure native OS window titlebar and taskbar inherit LayoutLingua brand icon."""
    if sys.platform != "win32":
        return

    def _worker():
        import ctypes
        from ctypes import wintypes
        import os
        import time

        root_dir = _get_bundle_root()
        icon_path = root_dir / "public" / "icon.ico"
        if not icon_path.is_file():
            icon_path = root_dir / "layoutlingua" / "resources" / "icon.ico"
        if not icon_path.is_file():
            return

        try:
            user32 = ctypes.windll.user32
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1

            hicon_big = user32.LoadImageW(None, str(icon_path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            hicon_small = user32.LoadImageW(None, str(icon_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

            if not hicon_big and not hicon_small:
                return

            current_pid = os.getpid()
            applied = False

            def enum_cb(hwnd, _):
                nonlocal applied
                lpdw_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
                if lpdw_pid.value == current_pid:
                    if hicon_big:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                    if hicon_small:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                    applied = True
                else:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        if window_title in buf.value or "LayoutLingua" in buf.value:
                            if hicon_big:
                                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                            if hicon_small:
                                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                            applied = True
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            cb = WNDENUMPROC(enum_cb)

            for _ in range(30):
                time.sleep(0.2)
                user32.EnumWindows(cb, 0)
                if applied:
                    break
        except Exception:
            pass

    import threading
    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def launch_desktop_app(port: int | None = None) -> int:
    """Start the local engine and open the native LayoutLingua desktop window."""
    root_dir = _get_bundle_root()
    _ensure_frontend_built(root_dir)

    actual_port = port or _find_free_port(8765)
    os.environ["PYTHON_ENGINE_PORT"] = str(actual_port)
    server = start_server(host="127.0.0.1", port=actual_port)
    app_url = f"http://127.0.0.1:{actual_port}/"
    window_title = "LayoutLingua — AI Document Translation Studio"

    # Resolve application brand icon per platform
    if sys.platform.startswith("linux"):
        brand_icon = root_dir / "public" / "logo.png"
        if not brand_icon.is_file():
            brand_icon = root_dir / "layoutlingua" / "resources" / "logo.png"
    elif sys.platform == "darwin":
        brand_icon = root_dir / "public" / "icon.icns"
        if not brand_icon.is_file():
            brand_icon = root_dir / "public" / "logo.png"
    else:
        brand_icon = root_dir / "public" / "icon.ico"
        if not brand_icon.is_file():
            brand_icon = root_dir / "layoutlingua" / "resources" / "icon.ico"
        if not brand_icon.is_file():
            brand_icon = root_dir / "public" / "logo.png"

    try:
        # 1. Primary: Native OS WebView window via pywebview (WebView2 on Windows, WebKit on macOS)
        try:
            import webview  # type: ignore

            webview.create_window(
                title=window_title,
                url=app_url,
                width=1440,
                height=920,
                min_size=(1080, 720),
                text_select=True,
            )
            _schedule_window_icon_setup(window_title)
            if brand_icon.is_file():
                webview.start(icon=str(brand_icon))
            else:
                webview.start()
            return 0
        except ImportError:
            pass

        # 2. Fallback: Standalone Native App Window (--app mode with isolated profile, no browser tabs/bar)
        host_bin = _find_native_app_host_binary()
        if host_bin:
            profile_dir = Path(tempfile.gettempdir()) / "LayoutLinguaDesktopWindowProfile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            proc = subprocess.Popen(
                [
                    host_bin,
                    f"--app={app_url}",
                    f"--user-data-dir={profile_dir}",
                    "--window-size=1440,920",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-extensions",
                ]
            )
            proc.wait()
            return 0

        print(f"[LayoutLingua Desktop] Native engine running at {app_url} (Press Ctrl+C to quit)")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        return 0
    finally:
        try:
            server.shutdown()
        except Exception:
            pass


def build_desktop_executable(onefile: bool = False, output_name: str | None = None) -> int:
    """Package LayoutLingua into a standalone native desktop executable."""
    root_dir = Path(__file__).resolve().parent.parent
    _ensure_frontend_built(root_dir)

    print("[LayoutLingua Desktop] Installing desktop packaging tools (pywebview, pyinstaller)...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pywebview", "pyinstaller"],
        check=True,
    )

    sep = ";" if sys.platform == "win32" else ":"
    dist_src = root_dir / "dist"
    res_src = root_dir / "layoutlingua" / "resources"
    fonts_src = root_dir / "layoutlingua" / "typesetting" / "assets" / "fonts"
    release_dir = root_dir / "release"
    build_work_dir = root_dir / "build_desktop_tmp"
    app_name = output_name or "LayoutLingua"

    bundle_mode = "--onefile" if onefile else "--onedir"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        bundle_mode,
        "--windowed",
        "--name",
        app_name,
        "--distpath",
        str(release_dir),
        "--workpath",
        str(build_work_dir),
        "--collect-all",
        "pymupdf",
        "--collect-all",
        "webview",
        "--hidden-import",
        "fitz",
        "--hidden-import",
        "ftfy",
        "--hidden-import",
        "platformdirs",
        "--add-data",
        f"{dist_src}{sep}dist",
        "--add-data",
        f"{res_src}{sep}layoutlingua/resources",
    ]

    public_src = root_dir / "public"
    if public_src.is_dir():
        cmd.extend(["--add-data", f"{public_src}{sep}public"])

    icon_path = None
    if sys.platform == "win32":
        for cand in [public_src / "icon.ico", res_src / "icon.ico"]:
            if cand.is_file():
                icon_path = cand
                break
    elif sys.platform == "darwin":
        for cand in [public_src / "icon.icns", res_src / "icon.icns"]:
            if cand.is_file():
                icon_path = cand
                break
    else:
        for cand in [public_src / "logo.png", res_src / "logo.png"]:
            if cand.is_file():
                icon_path = cand
                break

    if icon_path:
        cmd.extend(["--icon", str(icon_path)])

    if fonts_src.exists():
        cmd.extend(["--add-data", f"{fonts_src}{sep}layoutlingua/typesetting/assets/fonts"])
    cmd.append(str(root_dir / "layoutlingua" / "desktop.py"))

    print(f"[LayoutLingua Desktop] Building standalone native application ({bundle_mode} -> {app_name})...")
    res = subprocess.run(cmd, cwd=str(root_dir))
    shutil.rmtree(build_work_dir, ignore_errors=True)
    spec_file = root_dir / f"{app_name}.spec"
    if spec_file.is_file():
        spec_file.unlink()

    if res.returncode == 0:
        exe_ext = ".exe" if sys.platform == "win32" else ""
        if onefile:
            exe_path = release_dir / f"{app_name}{exe_ext}"
        else:
            exe_path = release_dir / app_name / f"{app_name}{exe_ext}"
        print(f"\n[OK] Standalone Desktop App built successfully: {exe_path}")
    return res.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LayoutLingua Native Desktop Application")
    parser.add_argument(
        "--build-exe",
        action="store_true",
        help="Compile a standalone native Desktop executable.",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Compile into a single standalone executable file instead of a directory.",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="Custom executable name.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Optional local port for the embedded engine.",
    )
    args = parser.parse_args(argv)
    if args.build_exe:
        return build_desktop_executable(onefile=args.onefile, output_name=args.output_name)
    return launch_desktop_app(port=args.port)


if __name__ == "__main__":
    sys.exit(main())
