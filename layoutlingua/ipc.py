"""JSON-RPC 2.0 Server over Standard I/O using Newline-Delimited JSON (NDJSON).

Rules:
- Standard output (stdout) is strictly reserved for protocol messages.
- All diagnostics, logs, and stack traces must be directed to stderr.
- Complies strictly with the JSON-RPC 2.0 specification (RFC 2.0).
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable, TextIO

from layoutlingua.core.ir import DocumentIR
from layoutlingua.core.parser import PDFParseError, parse_pdf
from layoutlingua.translation.mock import MockTranslationProvider

# JSON-RPC 2.0 Standard Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JsonRpcServer:
    """Dispatches JSON-RPC 2.0 calls over NDJSON stdio."""

    def __init__(self) -> None:
        self.methods: dict[str, Callable[[Any], Any]] = {}
        self.mock_provider = MockTranslationProvider()
        self._register_default_methods()

    def register_method(self, name: str, handler: Callable[[Any], Any]) -> None:
        """Register a handler method for JSON-RPC invocations."""
        self.methods[name] = handler

    def _register_default_methods(self) -> None:
        self.register_method("ping", self._handle_ping)
        self.register_method("get_schema_version", self._handle_get_schema_version)
        self.register_method("parse_document", self._handle_parse_document)
        self.register_method("translate_document_mock", self._handle_translate_document_mock)
        self.register_method("translate_ir_mock", self._handle_translate_ir_mock)

    def _handle_ping(self, _params: Any) -> dict[str, Any]:
        return {"pong": True, "version": "1.0.0"}

    def _handle_get_schema_version(self, _params: Any) -> dict[str, Any]:
        return {"ir_version": "1.0", "rpc_version": "2.0"}

    def _handle_parse_document(self, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict) or "file_path" not in params:
            raise ValueError("Parameter 'file_path' is required as a string")
        file_path = str(params["file_path"])
        doc_ir = parse_pdf(file_path)
        return doc_ir.to_dict()

    def _handle_translate_document_mock(self, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict) or "file_path" not in params:
            raise ValueError("Parameter 'file_path' is required")
        target_lang = str(params.get("target_lang", "vi"))
        doc_ir = parse_pdf(str(params["file_path"]))
        translated_ir = self.mock_provider.translate_document(doc_ir, target_lang=target_lang)
        return translated_ir.to_dict()

    def _handle_translate_ir_mock(self, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict) or "doc_ir" not in params:
            raise ValueError("Parameter 'doc_ir' is required")
        target_lang = str(params.get("target_lang", "vi"))
        doc_ir = DocumentIR.from_dict(params["doc_ir"])
        translated_ir = self.mock_provider.translate_document(doc_ir, target_lang=target_lang)
        return translated_ir.to_dict()

    def process_message(self, line: str, err_stream: TextIO = sys.stderr) -> str | None:
        """Process a single JSON-RPC request line and return the NDJSON response string."""
        line = line.strip()
        if not line:
            return None

        req_id: Any = None
        try:
            try:
                request = json.loads(line)
            except Exception as json_err:
                print(f"[JSON-RPC Log] JSON Parse Error: {json_err}", file=err_stream)
                return self._make_error_response(None, PARSE_ERROR, f"Parse error: {json_err}")

            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or "method" not in request:
                return self._make_error_response(
                    request.get("id") if isinstance(request, dict) else None,
                    INVALID_REQUEST,
                    "Invalid Request: missing 'jsonrpc': '2.0' or 'method'",
                )

            req_id = request.get("id")
            method = request["method"]
            params = request.get("params", {})

            if method not in self.methods:
                return self._make_error_response(
                    req_id,
                    METHOD_NOT_FOUND,
                    f"Method not found: '{method}'",
                )

            # Execute method
            try:
                result = self.methods[method](params)
                # If notification (no id), no response is sent
                if req_id is None:
                    return None
                return self._make_success_response(req_id, result)
            except ValueError as val_err:
                return self._make_error_response(req_id, INVALID_PARAMS, str(val_err))
            except PDFParseError as parse_err:
                return self._make_error_response(req_id, INTERNAL_ERROR, f"PDF Parse Error: {parse_err}")
            except Exception as exc:
                print(f"[JSON-RPC Log] Internal error in method '{method}':\n{traceback.format_exc()}", file=err_stream)
                return self._make_error_response(req_id, INTERNAL_ERROR, f"Internal error: {exc}")

        except Exception as unhandled:
            print(f"[JSON-RPC Log] Unhandled server error: {unhandled}", file=err_stream)
            return self._make_error_response(req_id, INTERNAL_ERROR, "Server internal error")

    def _make_success_response(self, req_id: Any, result: Any) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }
        return json.dumps(payload, ensure_ascii=False)

    def _make_error_response(self, req_id: Any, code: int, message: str, data: Any = None) -> str:
        error_payload: dict[str, Any] = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error_payload["data"] = data
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": error_payload,
        }
        return json.dumps(payload, ensure_ascii=False)

    def serve_stdio(
        self,
        in_stream: TextIO = sys.stdin,
        out_stream: TextIO = sys.stdout,
        err_stream: TextIO = sys.stderr,
    ) -> None:
        """Run the continuous stdio server loop reading NDJSON lines."""
        print("[LayoutLingua IPC] Server started on stdio", file=err_stream)
        for line in in_stream:
            response = self.process_message(line, err_stream=err_stream)
            if response is not None:
                out_stream.write(response + "\n")
                out_stream.flush()
