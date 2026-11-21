import io
import json
import sys
from unittest.mock import Mock, patch

from layoutlingua.server import LayoutLinguaHandler


def post_install(**request):
    body = json.dumps(request).encode()
    handler = Mock(spec=LayoutLinguaHandler)
    handler.path = "/api/argos/install"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    LayoutLinguaHandler.do_POST(handler)
    return handler._send_json.call_args


def test_frozen_install_never_launches_pip(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    with patch("layoutlingua.translation.argos.manager.ArgosModelManager") as manager, patch(
        "layoutlingua.server.subprocess.run"
    ) as run:
        manager.return_value.is_runtime_available.return_value = False
        response = post_install()
        run.assert_not_called()
        assert response.kwargs["status"] == 400
        assert response.args[0]["status"] == "error"
        assert "Reinstall LayoutLingua" in response.args[0]["message"]

        manager.return_value.is_runtime_available.return_value = True
        route = manager.return_value.plan_route.return_value
        route.describe.return_value = "en -> vi"
        response = post_install(from_code="en", to_code="vi")
        assert response.args[0]["status"] == "ok"
        assert response.args[0]["runtime_available"] is True
        manager.return_value.ensure_route_installed.assert_called_once_with(route)
        run.assert_not_called()


def test_source_install_uses_engine_python():
    with patch("layoutlingua.translation.argos.manager.ArgosModelManager") as manager, patch(
        "layoutlingua.server.subprocess.run"
    ) as run:
        manager.return_value.is_runtime_available.side_effect = [False, True]
        run.return_value.returncode = 0
        response = post_install()
        assert response.args[0]["runtime_available"] is True
        assert run.call_args.args[0] == [sys.executable, "-m", "pip", "install", "argostranslate"]
