# ─────────────────────────────────────────────────────────
# Stage 1: Builder (Playwright image with browsers pre‑installed)
# ─────────────────────────────────────────────────────────
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy AS builder

WORKDIR /app

# Install Python dependencies for both stages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code for caching purposes
COPY api ./api

# ─────────────────────────────────────────────────────────
# Stage 2: Runtime (slim Python + necessary binaries and libs)
# ─────────────────────────────────────────────────────────
FROM python:3.10-slim AS runtime

WORKDIR /app

# Install OS‑level dependencies for Playwright browsers
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgbm1 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libasound2 \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies at runtime to ensure httpx, selectolax, etc.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Playwright browser binaries from builder
COPY --from=builder /ms-playwright /ms-playwright

# Copy application code
COPY api ./api

# Point Playwright to its browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Expose and launch the FastAPI app
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
