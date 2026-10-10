# ==============================================================================
# Multi-Stage Production Dockerfile for Kalshi Bot 1 V4 Trading Appliance
# Target Architecture: Linux amd64 / AWS EC2 c6i.large (us-east-1)
# ==============================================================================

# STAGE 1: Frontend Build
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit
COPY frontend/ ./
RUN npm run build

# STAGE 2: Python Headless Trading Engine Runtime
FROM python:3.12-slim AS runner

# Install system dependencies for cryptography and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create unprivileged service user
RUN groupadd -r kalshi && useradd -r -g kalshi -d /app -s /sbin/nologin kalshi

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source tree and assets
COPY src/ /app/src/
COPY models/ /app/models/
COPY data/ /app/data/

# Copy compiled frontend from Stage 1
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Set permissions
RUN chown -R kalshi:kalshi /app
USER kalshi

# Environment configuration
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV KALSHI_MODE=live
ENV KALSHI_ENV=live
ENV KALSHI_LIVE_TRADING_ENABLED=true

EXPOSE 8000

# Healthcheck against institutional integrity endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/integrity/status || exit 1

ENTRYPOINT ["python", "-u", "-m", "kalshi_sim.server"]
