import builtins
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from layoutlingua import desktop


def test_desktop_entrypoint_does_not_import_server(monkeypatch):
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
        if name == "layoutlingua.server":
            pytest.fail("headless entrypoint imported the server")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_module)
    runpy.run_path(desktop.__file__, run_name="desktop_smoke_entrypoint")


@pytest.mark.parametrize("languages", [[], ["English"]])
def test_check_argos_is_headless_with_windowed_streams(monkeypatch, tmp_path, languages):
    log_path = tmp_path / "argos.log"
    monkeypatch.setenv("LAYOUTLINGUA_SMOKE_LOG", str(log_path))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    def installed():
        sys.stdout.write("checked\n")
        sys.stderr.flush()
        return languages

    monkeypatch.setitem(sys.modules, "argostranslate", SimpleNamespace(
        translate=SimpleNamespace(get_installed_languages=installed),
    ))
    monkeypatch.setattr(desktop, "launch_desktop_app", Mock(side_effect=AssertionError("launched")))
    assert desktop.main(["--check-argos"]) == 0
    assert log_path.read_text(encoding="utf-8") == "checked\n"
    assert sys.stdout is None
    assert sys.stderr is None


@pytest.mark.parametrize("during_import", [False, True])
def test_check_argos_reports_errors_without_bootloader_dialog(monkeypatch, tmp_path, during_import):
    log_path = tmp_path / "argos.log"
    monkeypatch.setenv("LAYOUTLINGUA_SMOKE_LOG", str(log_path))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    def fail():
        raise RuntimeError("offline import failed")

    if during_import:
        original_import = builtins.__import__

        def import_module(name, *args, **kwargs):
            if name == "argostranslate":
                fail()
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", import_module)
    else:
        monkeypatch.setitem(sys.modules, "argostranslate", SimpleNamespace(
            translate=SimpleNamespace(get_installed_languages=fail),
        ))
    assert desktop.main(["--check-argos"]) == 1
    assert "RuntimeError: offline import failed" in log_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("returncode", [0, 1])
def test_smoke_subprocess_result(monkeypatch, returncode, capsys):
    proc = Mock(pid=123)
    proc.wait.return_value = returncode

    def popen(command, **kwargs):
        assert command == ["app", "--check-argos"]
        Path(kwargs["env"]["LAYOUTLINGUA_SMOKE_LOG"]).write_text("runtime diagnostic\n", encoding="utf-8")
        return proc

    monkeypatch.setattr(desktop.subprocess, "Popen", popen)
    if returncode:
        with pytest.raises(subprocess.CalledProcessError):
            desktop._smoke_test_executable(Path("app"))
    else:
        desktop._smoke_test_executable(Path("app"))
    proc.wait.assert_called_once_with(timeout=180)
    assert "runtime diagnostic" in capsys.readouterr().out


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_smoke_timeout_kills_process_tree(monkeypatch, platform, cleanup_fails):
    proc = Mock(pid=123)
    proc.wait.side_effect = [subprocess.TimeoutExpired("app", 180), 1]
    proc.poll.return_value = None
    popen = Mock(return_value=proc)
    run = Mock(side_effect=OSError("cleanup failed") if cleanup_fails else None)
    killpg = Mock(side_effect=OSError("cleanup failed") if cleanup_fails else None)
    monkeypatch.setattr(desktop.sys, "platform", platform)
    monkeypatch.setattr(desktop.subprocess, "Popen", popen)
    monkeypatch.setattr(desktop.subprocess, "run", run)
    monkeypatch.setattr(desktop.os, "killpg", killpg, raising=False)
    monkeypatch.setattr(desktop.signal, "SIGKILL", 9, raising=False)
    with pytest.raises(RuntimeError, match="smoke test timed out after 180s") as error:
        desktop._smoke_test_executable(Path("app"))
    assert ("Process-tree cleanup failed" in str(error.value)) == cleanup_fails
    proc.kill.assert_called_once_with()
    assert proc.wait.call_count == 2
    assert popen.call_args.kwargs["start_new_session"] == (platform != "win32")
    if platform == "win32":
        run.assert_called_once_with(["taskkill", "/PID", "123", "/T", "/F"], check=True, timeout=30)
        killpg.assert_not_called()
    else:
        killpg.assert_called_once_with(123, desktop.signal.SIGKILL)
        run.assert_not_called()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX executable fixture")
def test_smoke_timeout_kills_real_process(tmp_path):
    executable = tmp_path / "hanging-app"
    executable.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(60)\n", encoding="utf-8")
    executable.chmod(0o755)
    with pytest.raises(RuntimeError, match="smoke test timed out after 0.1s"):
        desktop._smoke_test_executable(executable, timeout=0.1)
