# Security Policy

The LayoutLingua team takes the security, confidentiality, and integrity of academic documents, technical publications, and user credentials extremely seriously.

---

## 1. Supported Versions

Security updates, bug fixes, and vulnerability patches are actively provided for the following releases:

| Version | Supported          | Status                                      |
|---------|--------------------|---------------------------------------------|
| 2.0.x   | :white_check_mark: | Current Active Stable Development (Release) |
| < 2.0   | :x:                | Deprecated                                  |

---

## 2. Reporting a Vulnerability

If you discover a security vulnerability, privacy defect, or credential handling issue in LayoutLingua, **please do NOT open a public GitHub issue**.

Instead, report it responsibly via one of the following channels:
1. **GitHub Security Advisory**: Navigate to the [Security Advisories tab](https://github.com/ThanhNguyxnOrg/LayoutLingua/security/advisories) on our repository and click **"Report a vulnerability"**.
2. **Email**: Contact project maintainers directly at `security@layoutlingua.org` or reach out to the core team (`@ThanhNguyxnOrg/core`).

### 2.1. What to Include

Please provide:
- A clear description of the vulnerability and its potential impact.
- Step-by-step reproduction instructions or a minimal proof of concept.
- Affected component(s) (e.g., Desktop Client, Python HTTP IPC server, Translation Cache).

### 2.2. Response Timeline

- **Initial Acknowledgment**: Within 48 hours of receipt.
- **Triage & Assessment**: Within 5 business days.
- **Patch Release & Advisory**: Coordinated disclosure within 30 days of confirmed fix.

---

## 3. Security Architecture & Guarantees

LayoutLingua incorporates strict security and privacy safeguards:

- **Zero Cloud Leakage Guarantee (Offline Mode)**: When configured with `Argos Translate`, all neural translation and layout typesetting run 100% locally on-device. No telemetry, text segments, or network packets are transmitted externally.
- **Local SQLite Segment Storage**: All cached translation segments and embeddings are stored strictly on the local filesystem (`translations.db`) under platform-standard user application data directories.
- **API Key Sanitization**: Provider credentials and API keys are stored in secure local configuration files or native operating system keyrings and are **never** logged, exposed in error traces, or included in exported diagnostic logs.
- **Fail-Closed PDF Sanitization**: When rendering untrusted or third-party PDF streams, LayoutLingua enforces strict boundary validation and coordinate normalization to prevent buffer overruns or malformed PDF object injection.
