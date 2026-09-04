# Web Architecture Blueprint & Strategy Evaluation

This document analyzes the engineering trade-offs between **Native Local Applications** (Desktop/Android) and **Web-Based Deployments**, and provides the technical blueprint for LayoutLingua's self-hosted web architecture.

---

## 1. Native Desktop/Mobile vs. Web Application: Strategic Evaluation

A common question is: *"Why build native desktop and mobile apps when a web app is accessible everywhere?"*

For document translation with layout preservation, the underlying workloads (computer vision layout segmentation, font embedding, vector math reflow) impose unique constraints:

| Evaluation Dimension | Native Desktop / Mobile App | Hosted Cloud Web App |
| :--- | :--- | :--- |
| **Compute & Server Cost** | **$0 / month** (runs 100% on the user's local CPU/GPU). | **High** ($100s - $1,000s/mo). Each active translation consumes 1.5 - 3.5 GB RAM during layout inference and font embedding. |
| **Data Privacy & Compliance** | **Absolute**. Zero document bytes leave the user's machine. Compliant with HIPAA, GDPR, NDAs, and academic non-disclosure. | Requires sending full documents across the network to a central server, raising security and corporate compliance obstacles. |
| **File Size & Page Limits** | **Unlimited**. A user can translate a 600-page textbook directly from an NVMe SSD without network timeouts. | Limited by HTTP request timeouts, file upload bandwidth, and memory quotas on server worker instances. |
| **Offline Capability** | **100% offline**. Works on trains, flights, secure intranets, and disconnected research labs. | Requires continuous high-bandwidth internet connectivity. |
| **Installation Friction** | Requires downloading executable / installer (PyInstaller `.exe`, `.dmg`, `.tar.gz` or Android `.apk`). | Zero friction (open browser URL and start using). |

### Summary Recommendation
- **Flagship Tier**: Standalone desktop apps (Windows, macOS, Linux) and Android native app provide free, unlimited, private document translation.
- **Web Tier**: Self-hosted Docker container for university labs, enterprises, and research groups who want a shared internal web portal.

---

## 2. Web Architecture Blueprint

For self-hosted and cloud web deployments, LayoutLingua uses a modular, decoupled architecture:

```
                  ┌─────────────────────────────────────────┐
                  │          Next.js / React Web UI         │
                  │   (Based on LayoutLingua Design System)  │
                  └────────────────────┬────────────────────┘
                                       │
                               HTTP POST / SSE
                                       │
                  ┌────────────────────▼────────────────────┐
                  │            FastAPI Gateway              │
                  │   - File ingestion & validation         │
                  │   - Session token / rate limiting       │
                  │   - Real-time SSE progress stream       │
                  └─────────────┬───────────────────────────┘
                                │
                                │ Task Enqueue (Redis / Celery)
                                ▼
                  ┌─────────────────────────────────────────┐
                  │          DocLayout Worker Pool          │
                  │   - ONNX Runtime / PyMuPDF pipeline     │
                  │   - Font embedding & formula reflow     │
                  │   - Ephemeral file storage (auto-wipe)  │
                  └─────────────────────────────────────────┘
```

### Components

1. **Frontend (Browser Client)**
   - Built with Next.js or Vite + Tailwind, utilizing the dark obsidian & radiant cyan design system.
   - Communicates with the backend using Server-Sent Events (`/api/v1/jobs/{id}/stream`) to receive real-time page-by-page progress.
   - Uses Web Workers for pre-flight PDF validation and page count inspection before upload.

2. **API Gateway (FastAPI)**
   - Fast, asynchronous Python server (`uvicorn` + `fastapi`).
   - Endpoints:
     - `POST /api/v1/translate`: Accepts multipart PDF upload and translation parameters (source/target language, overwrite, formula preservation).
     - `GET /api/v1/jobs/{id}`: Queries current translation status.
     - `GET /api/v1/jobs/{id}/stream`: Real-time SSE stream of progress events.
     - `GET /api/v1/jobs/{id}/download`: Downloads translated PDF or dual-language bilingual PDF.

3. **Inference Worker Pool**
   - Headless Python runner executing `pdf2zh` core and DocLayout ONNX segmentation.
   - Ephemeral volume management: Input and output files are wiped 1 hour after translation to guarantee user privacy.

---

## 3. Docker Deployment Specification

LayoutLingua can be deployed in a single container or multi-container swarm using Docker:

```yaml
version: "3.9"

services:
  layoutlingua-web:
    image: ghcr.io/thanhnguyxn/layoutlingua:latest
    ports:
      - "8000:8000"
    environment:
      - MAX_FILE_SIZE_MB=150
      - MAX_CONCURRENT_JOBS=4
      - WORKER_TIMEOUT_SECONDS=600
    volumes:
      - layoutlingua-cache:/app/cache
    restart: unless-stopped

volumes:
  layoutlingua-cache:
```
