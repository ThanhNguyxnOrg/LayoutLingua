# Security Policy (`SECURITY.md`)

<p>
  <img src="https://img.shields.io/badge/Security-Local--First%20Privacy-0D9488?style=for-the-badge" alt="Security Policy" />
  <img src="https://img.shields.io/badge/PDF%20Execution-Sandboxed%20MuPDF%20WASM-0284C7?style=for-the-badge" alt="Sandboxed MuPDF" />
</p>

## Supported Versions

| Version | Supported |
|:---|:---:|
| `2.1.x` | ✅ Yes |
| `2.0.x` | ⚠️ Security fixes only |
| `< 2.0.0` | ❌ No |

## Privacy & Data Handling Architecture

1. **Sandboxed Vector Parsing**: PDF documents are parsed in memory using WebAssembly-sandboxed MuPDF (`mupdf`) and `pdf-lib`. Embedded JavaScript actions inside untrusted PDFs are never executed.
2. **Formula Shielding Before External Calls**: Only extracted prose spans (`ProseGroup.sourceText` with inline math masked as `⟦M0⟧`) are sent to the configured translation provider; raw PDF files and vector diagrams never leave your local server.
3. **Path Traversal Protection**: Export filenames and session cache identifiers (`docId`) are strictly sanitized (`replace(/[^a-zA-Z0-9_-]/g, '_')`) before any filesystem read/write operation.

## Reporting a Vulnerability

Please report suspected security vulnerabilities privately via GitHub Security Advisories rather than public issues. We respond to all security reports within 48 hours.
