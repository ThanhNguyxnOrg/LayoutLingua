"""Command Line Interface (CLI) for LayoutLingua.

All user-facing options, help text, logs, and messages are strictly 100% English.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from layoutlingua._version import __version__
from layoutlingua.core.parser import PDFParseError, parse_pdf
from layoutlingua.ipc import JsonRpcServer
from layoutlingua.translation.mock import MockTranslationProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="layoutlingua",
        description="LayoutLingua: High-precision document translation engine preserving layout geometry.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit.",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--parse",
        metavar="INPUT_PDF",
        type=str,
        help="Parse input PDF into Intermediate Representation (DocumentIR) JSON.",
    )
    group.add_argument(
        "--translate-mock",
        metavar="INPUT_PDF",
        type=str,
        help="Parse and run deterministic offline mock translation.",
    )
    group.add_argument(
        "--rpc",
        action="store_true",
        help="Start the JSON-RPC 2.0 NDJSON standard I/O server for Electron desktop client.",
    )

    parser.add_argument(
        "--target-lang",
        type=str,
        default="vi",
        help="Target language code (default: 'vi').",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to write output JSON file (default: stdout).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2).",
    )

    return parser


def main(args: list[str] | None = None) -> int:
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.rpc:
        server = JsonRpcServer()
        try:
            server.serve_stdio()
            return 0
        except KeyboardInterrupt:
            print("[LayoutLingua] RPC server stopped by user", file=sys.stderr)
            return 0
        except Exception as exc:
            print(f"[LayoutLingua] RPC server fatal error: {exc}", file=sys.stderr)
            return 1

    # Handle --parse
    if parsed_args.parse:
        input_path = Path(parsed_args.parse)
        try:
            print(f"[LayoutLingua] Parsing PDF: {input_path}", file=sys.stderr)
            doc_ir = parse_pdf(input_path)
            json_output = doc_ir.to_json(indent=parsed_args.indent)

            if parsed_args.output:
                out_path = Path(parsed_args.output)
                out_path.write_text(json_output, encoding="utf-8")
                print(f"[LayoutLingua] Wrote DocumentIR to {out_path}", file=sys.stderr)
            else:
                sys.stdout.write(json_output + "\n")
            return 0
        except PDFParseError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 2
        except Exception as err:
            print(f"Unexpected error: {err}", file=sys.stderr)
            return 1

    # Handle --translate-mock
    if parsed_args.translate_mock:
        input_path = Path(parsed_args.translate_mock)
        try:
            print(f"[LayoutLingua] Parsing PDF: {input_path}", file=sys.stderr)
            doc_ir = parse_pdf(input_path)
            provider = MockTranslationProvider()
            print(f"[LayoutLingua] Translating via Mock Provider to '{parsed_args.target_lang}'", file=sys.stderr)
            translated_ir = provider.translate_document(doc_ir, target_lang=parsed_args.target_lang)
            json_output = translated_ir.to_json(indent=parsed_args.indent)

            if parsed_args.output:
                out_path = Path(parsed_args.output)
                out_path.write_text(json_output, encoding="utf-8")
                print(f"[LayoutLingua] Wrote Translated DocumentIR to {out_path}", file=sys.stderr)
            else:
                sys.stdout.write(json_output + "\n")
            return 0
        except PDFParseError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 2
        except Exception as err:
            print(f"Unexpected error: {err}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
