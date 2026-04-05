# =============================================================================
# OpenDoc - Dockerfile
# Python 3.11 + Playwright (Chromium) for SAT portal automation
# Optimized: multi-stage build, minimal image size, non-root user
# =============================================================================

# --------------- Stage 1: Builder ---------------
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --------------- Stage 2: Runtime ---------------
FROM python:3.11-slim-bookworm AS runtime

# System deps required by Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    libx11-xcb1 \
    fonts-noto-cjk \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Install Playwright browsers (Chromium only to keep image small)
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
RUN playwright install chromium

# Create non-root user
RUN groupadd -r opendoc && useradd -r -g opendoc -m -s /bin/bash opendoc

WORKDIR /app

# Copy application code
COPY . .

# Own the app directory
RUN chown -R opendoc:opendoc /app

USER opendoc

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import google.generativeai; print('ok')" || exit 1

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

CMD ["python", "-m", "src.core.main"]
