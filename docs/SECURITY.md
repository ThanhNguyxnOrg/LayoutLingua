# 🔐 Security Policy (`SECURITY.md`)

<p align="center">
  <a href="../README.md">🏠 README</a> ·
  <a href="ARCHITECTURE.md">🏛 Architecture</a> ·
  <a href="ALGORITHM.md">🧮 Algorithms</a> ·
  <a href="API_REFERENCE.md">🔌 API</a> ·
  <a href="CHANGELOG.md">📜 Changelog</a> ·
  <a href="CONTEXT.md">🧭 Context</a> ·
  <a href="CONTRIBUTING.md">🤝 Contributing</a> ·
  <a href="CODE_OF_CONDUCT.md">🌈 Conduct</a> ·
  <a href="SECURITY.md">🔐 Security</a>
</p>

---

<p>
  <img src="https://img.shields.io/badge/🔐_Security-Local_First_Privacy-0D9488?style=for-the-badge" alt="Security Policy" />
  <img src="https://img.shields.io/badge/🧊_PDF_Execution-PyMuPDF_Sandboxed_Parsing-0284C7?style=for-the-badge" alt="Sandboxed PyMuPDF" />
  <img src="https://img.shields.io/badge/🛡️_Data_Leakage-Zero_(Offline_Mode)-22C55E?style=for-the-badge" alt="Zero Leakage" />
  <img src="https://img.shields.io/badge/📴_Air--Gapped-100%25_Local_AI-8B5CF6?style=for-the-badge" alt="Air Gapped" />
</p>

## 📌 Supported Versions

| Version | Supported |
|:---|:---:|
| `2.1.x` | ✅ Yes (Active Release) |
| `2.0.x` | ⚠️ Security fixes only |
| `< 2.0.0` | ❌ End of Life |

## 🛡️ Privacy & Data Handling Architecture

1. **🧊 Sandboxed Vector Parsing**: PDF documents are parsed in memory using PyMuPDF (`fitz`). Embedded JavaScript actions inside untrusted PDFs are never executed.
2. **🔒 Formula Shielding Before External Calls**: Only extracted prose spans (`ProseGroup.sourceText` with inline math masked as `⟦M0⟧` / `<b0></b0>`) are sent to the configured translation provider; raw PDF files and vector diagrams never leave your local machine.
3. **📴 100% Offline Air-Gapped Mode**: The Argos Translate (CTranslate2) provider runs completely on-device — zero network calls, zero data leakage, zero API keys required. 🛡️
4. **🧭 Path Traversal & Base URL SSRF Protection**: Export filenames and session cache identifiers (`docId`) are strictly sanitized. Custom OpenAI endpoints undergo SSRF validation rejecting link-local, cloud metadata (`169.254.169.254`), and loopback re-binding.
5. **💾 Session Cache Isolation**: Persisted sessions live entirely inside the user's local operating system cache directory (`platformdirs`) and never leave the host machine.

## 🚨 Reporting a Vulnerability

Please report suspected security vulnerabilities **privately via GitHub Security Advisories** rather than public issues. 🔏 We respond to all security reports within **48 hours**. ⏱️
