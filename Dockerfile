# ── Dockerfile — Production-grade container configuration for HarvestGate ──

# Base Image
FROM python:3.11-slim

# Set Python build and runtime behaviors
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies (curl is required for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Create a non-root system user for security hardening
RUN useradd --create-home appuser
WORKDIR /home/appuser/app

# Copy application directories with non-root ownership
COPY --chown=appuser:appuser gateway/ ./gateway/
COPY --chown=appuser:appuser inference/ ./inference/
COPY --chown=appuser:appuser drift/ ./drift/
COPY --chown=appuser:appuser monitoring/ ./monitoring/
COPY --chown=appuser:appuser models/ ./models/
COPY --chown=appuser:appuser data/ ./data/

# Switch context to the non-root user
USER appuser

# Expose HTTP API gateway port
EXPOSE 8000

# Automated container health check monitoring /health API endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start uvicorn server bound to 0.0.0.0 (required for bridge networks)
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
