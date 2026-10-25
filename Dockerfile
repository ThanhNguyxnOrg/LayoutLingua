# Multi-stage production Dockerfile for LayoutLingua PDF Translation Server
FROM python:3.12-slim-bookworm as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8765

# Install system dependencies required by PyMuPDF, OpenCV, and ONNX Runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for caching
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy LayoutLingua source tree
COPY layoutlingua/ ./layoutlingua/

# Expose default API server port
EXPOSE 8765

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8765/api/health || exit 1

# Default entry point
CMD ["python", "-m", "layoutlingua.server"]
