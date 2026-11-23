from pathlib import Path
from types import SimpleNamespace

import pytest

from layoutlingua import desktop


LICENSE_DIR = Path(desktop.__file__).resolve().parent.parent / "packaging" / "desktop-license"


@pytest.mark.parametrize("platform", ["linux", "win32", "darwin"])
def test_build_bundles_desktop_licenses(monkeypatch, platform):
    calls = []
    monkeypatch.setattr(desktop.sys, "platform", platform)
    monkeypatch.setattr(desktop, "_ensure_frontend_built", lambda root: None)
    monkeypatch.setattr(desktop.shutil, "rmtree", lambda *args, **kwargs: None)
    monkeypatch.setattr(desktop, "_smoke_test_executable", lambda path: None)

    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(desktop.subprocess, "run", run)
    assert desktop.build_desktop_executable() == 0
    command = next(cmd for cmd in calls if "PyInstaller" in cmd)
    entries = [command[i + 1] for i, arg in enumerate(command) if arg == "--add-data"]
    separator = ";" if platform == "win32" else ":"
    for filename in ("NOTICE.md", "AGPL-3.0.txt"):
        source = LICENSE_DIR / filename
        assert source.is_file()
        assert f"{source}{separator}licenses" in entries


@pytest.mark.parametrize("frozen", [False, True])
def test_license_prints_notice(monkeypatch, capsys, tmp_path, frozen):
    notice = (LICENSE_DIR / "NOTICE.md").read_text(encoding="utf-8")
    if frozen:
        bundled = tmp_path / "licenses"
        bundled.mkdir()
        (bundled / "NOTICE.md").write_text(notice, encoding="utf-8")
        monkeypatch.setattr(desktop.sys, "_MEIPASS", str(tmp_path), raising=False)
    else:
        monkeypatch.delattr(desktop.sys, "_MEIPASS", raising=False)

    def unexpected_launch(*args, **kwargs):
        pytest.fail("--license must not launch or build the app")

    monkeypatch.setattr(desktop, "launch_desktop_app", unexpected_launch)
    monkeypatch.setattr(desktop, "build_desktop_executable", unexpected_launch)
    assert desktop.main(["--license"]) == 0
    assert capsys.readouterr().out == notice


@pytest.mark.parametrize("contents", ["", None])
def test_license_empty_or_missing_notice(monkeypatch, capsys, tmp_path, contents):
    monkeypatch.setattr(desktop.sys, "_MEIPASS", str(tmp_path), raising=False)
    licenses = tmp_path / "licenses"
    licenses.mkdir()
    if contents is None:
        expected = "Desktop license notice: https://github.com/ThanhNguyxnOrg/LayoutLingua/blob/main/packaging/desktop-license/NOTICE.md\n"
    else:
        (licenses / "NOTICE.md").write_text(contents, encoding="utf-8")
        expected = ""
    assert desktop.main(["--license"]) == 0
    assert capsys.readouterr().out == expected
