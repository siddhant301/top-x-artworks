# MutualArt Article Generator AI Service

This project is a FastAPI-based backend service that automatically generates sophisticated editorial articles about specific artists. It fetches an artist's top auction records, artwork details, and volume turnover data from the MutualArt GraphQL API, and then uses the `xai_sdk` (Grok) to synthesize a narrative article analyzing their market legacy.

## Features
- **FastAPI Backend:** Clean, high-performance API endpoint structure.
- **RESTful Endpoints:** Generate articles simultaneously using standard HTTP requests.
- **Auto-generated Documentation:** Built-in interactive Swagger UI to explore and test the API.
- **Async + Streaming:** Uses `httpx` and the `xai_sdk` async client for non-blocking, streaming article generation.
- **Docker-ready:** Multi-stage `Dockerfile` produces a lean, production-grade image with **no secrets baked in** — environment variables are injected at runtime by AWS (ECS/EKS Task Definitions).

## Project Structure
```text
Project/
│
├── main.py                           # FastAPI entry point & API endpoints
├── services/
│   ├── __init__.py
│   ├── prompt_builder.py             # GraphQL requests & prompt string construction
│   ├── grok_client.py                # xAI/Grok LLM async streaming wrapper
│   └── chart_data_formatter.py       # Utility for formatting chart data
├── Dockerfile                        # Multi-stage container definition (production-ready)
├── .dockerignore                     # Files excluded from Docker build context
├── requirements.txt                  # Python dependencies
└── README.md                         # This file
```

---

## Prerequisites

- **Python 3.8+** — for local development
- **Docker** — for containerised deployment
- **XAI API Key** — an active key to access Grok models via `xai_sdk`

---

## Option A — Run Locally (Development)

### 1. Create a Virtual Environment

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Core dependencies: `fastapi`, `uvicorn`, `httpx`, `python-dotenv`, `xai_sdk`.

### 3. Set Environment Variables

Create a `.env` file at the project root:

```env
XAI_API_KEY=your_actual_api_key_here
```

> **Note:** Both `XAI_API_KEY` and `MUTUALART_AUTH_TOKEN` must be present. The service will refuse to start if either is missing.

### 4. Start the Server

```bash
uvicorn main:app --reload
```

The `--reload` flag auto-restarts on code changes. Server starts at `http://127.0.0.1:8000`.

---

## Option B — Run with Docker (Production / Staging)

### 1. Build the Image

```bash
docker build -t mutualart-article-service:latest .
```

The **multi-stage build** keeps the image lean:
- **Stage 1 (builder):** Installs all Python packages into an isolated prefix.
- **Stage 2 (runtime):** Copies only the packages and application source — no build tools, no dev files, no secrets.

### 2. Environment Variables

> **The `.env` file is NOT baked into the image.** All secrets are injected at runtime by the hosting platform.

**Local Docker test:**
```bash
docker run \
  -e XAI_API_KEY=your_actual_api_key_here \
  -p 8000:8000 \
  mutualart-article-service:latest
```

**AWS deployment (ECS / EKS):**
Pass the following via the **ECS Task Definition** environment block or a **Kubernetes Secret**: no image rebuild required.

| Variable | Description |
|---|---|
| `XAI_API_KEY` | xAI / Grok API key |
| `MUTUALART_AUTH_TOKEN` | MutualArt GraphQL bearer token (once extracted from source) |

### 3. Health Check

The `Dockerfile` registers a `HEALTHCHECK` that polls `/health` every 30 s. Verify manually:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### 4. Push to Amazon ECR

```bash
# Authenticate
aws ecr get-login-password --region <region> | \
  docker login --username AWS --password-stdin <account_id>.dkr.ecr.<region>.amazonaws.com

# Tag
docker tag mutualart-article-service:latest \
  <account_id>.dkr.ecr.<region>.amazonaws.com/mutualart-article-service:latest

# Push
docker push <account_id>.dkr.ecr.<region>.amazonaws.com/mutualart-article-service:latest
```

---

## Using the API

### Interactive Docs (Swagger UI)

With the server running, open: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Click `GET /generate-article/{artist_id}` → **Try it out** → enter an artist ID (e.g. `68EFD50CBA356F91`) → **Execute**.

### cURL

```bash
curl -X GET \
  'http://127.0.0.1:8000/generate-article/68EFD50CBA356F91' \
  -H 'accept: application/json'
```

### Example Response

The endpoint returns a structured **JSON** object validated against the `ArticleResponse` Pydantic schema:

```json
{
  "meta": {
    "artist_id": "68EFD50CBA356F91",
    "artist_name": "Edvard Munch",
    "generated_at": "2026-04-02T07:30:00+00:00",
    "publication_date": "April 02, 2026"
  },
  "header": {
    "title": "Edvard Munch's 5 Most Expensive Works: The Anguish of Modern Existence",
    "deck": "A survey of five seminal works that cement Munch's reputation ..."
  },
  "lead": "Edvard Munch stands as one of the defining progenitors ...",
  "lots": [
    {
      "rank": 1,
      "title": "Skrik",
      "url": "https://www.mutualart.com/Artwork/Skrik/...",
      "year_created": "1895",
      "price_usd": 119922500,
      "price_display": "$119,922,500",
      "auction_house": "Sotheby's New York",
      "sale_year": 2012,
      "narrative": "Among the most iconic images in Western art ...",
      "provenance": "Petter Olsen collection",
      "exhibition": "National Gallery, Oslo 1927"
    }
  ],
  "conclusion": {
    "heading": "Edvard Munch's Market Legacy: An Enduring Ascent",
    "body": "Munch's auction market recorded a decisive spike in 2012 ..."
  }
}
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `HTTP 500` — API key missing | `XAI_API_KEY` not set | Inject the env var via `.env` (local) or ECS Task Definition (AWS) |
| `GraphQL Errors: ...` | MutualArt token expired or schema changed | Refresh `AUTH_TOKEN` in `prompt_builder.py` |
| Container exits immediately | Missing required env var | Run `docker logs <id>` to inspect |
