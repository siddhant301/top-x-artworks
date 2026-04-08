# ── Stage 1: Builder ────────────────────────────────────────────────────────
# Use a slim Python image as the base to keep the final image small.
FROM python:3.11-slim AS builder

# Set a working directory inside the image
WORKDIR /app

# Install system-level build dependencies needed by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to leverage Docker layer caching.
# Dependencies won't be reinstalled unless requirements.txt changes.
COPY requirements.txt .

# Install Python dependencies into a dedicated prefix so we can copy
# just the installed packages into the final (lean) stage.
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Metadata labels (good Docker hygiene)
LABEL maintainer="MutualArt Engineering"
LABEL description="MutualArt Article Generator AI Service"

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application source code
COPY main.py .
COPY services/ ./services/

# ── Environment Variables ─────────────────────────────────────────────────────
# These are NOT set here. They will be injected by the orchestration platform
# at runtime (e.g., AWS ECS Task Definition, EKS, or docker run -e ...).
# Required variables:
#   XAI_API_KEY           – xAI / Grok API key
#   MUTUALART_API_USERNAME – MutualArt API/login username
#   MUTUALART_API_PASSWORD – MutualArt API/login password
# Optional:
#   MUTUALART_TOKEN_URL    – token endpoint (default: https://gql.test.mutualart.com/token)
#   MUTUALART_VERIFY_SSL   – set true when cert chain is trusted in runtime
# Example (for local testing only):
#   docker run -e XAI_API_KEY=<key> -p 8000:8000 mutualart-article-service

# Expose the port Uvicorn listens on
EXPOSE 8000

# ── Health-check ─────────────────────────────────────────────────────────────
# Docker / ECS will poll this to decide if the container is healthy.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# ── Entrypoint ───────────────────────────────────────────────────────────────
# Run Uvicorn directly (no --reload in production).
# host 0.0.0.0 makes the port reachable from outside the container.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
