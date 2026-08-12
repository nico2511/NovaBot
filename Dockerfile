FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies needed to build some wheels on slim.
# Prefer binary wheels; build-essential kept as fallback for eth-account/cffi.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (prod only — no pytest/mypy; saves RAM during Coolify builds)
COPY requirements-prod.txt .

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120
# Sequential-ish install reduces peak RAM vs parallel wheel builds on 4GB LXC.
RUN pip install --no-cache-dir --upgrade "pip<26" && \
    pip install --no-cache-dir --no-compile -r requirements-prod.txt


# Final stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies (minimal)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Ensure data directories exist
RUN mkdir -p data/config data/state data/cache logs

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PORT=3001

# Expose API port
EXPOSE 3001

# Healthcheck: Coolify / docker will restart the container if /health stops
# answering. We give the bot 60s to boot before the first probe, then poll
# every 30s. Two consecutive failures = unhealthy = restart.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-3001}/health" > /dev/null || exit 1

# Run the unified entry point
CMD ["python", "main.py"]
