import json
import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from services.prompt_builder import build_article_prompt
from services.grok_client import generate_article_from_prompt

app = FastAPI(
    title="MutualArt Article Generator AI Service",
    description="Generates structured editorial articles via MutualArt GraphQL and Grok API.",
    version="2.0.0"
)


# ── Response Models ──────────────────────────────────────────────────────────

class ArticleMeta(BaseModel):
    artist_id: str
    artist_name: str
    generated_at: str
    publication_date: str

class ArticleHeader(BaseModel):
    title: str
    deck: str

class ArticleLot(BaseModel):
    rank: int
    title: str
    url: str
    year_created: str
    price_usd: float
    price_display: str
    auction_house: str
    sale_year: int
    narrative: str
    provenance: str
    exhibition: str

class ArticleConclusion(BaseModel):
    heading: str
    body: str

class ArticleResponse(BaseModel):
    meta: ArticleMeta
    header: ArticleHeader
    lead: str
    lots: List[ArticleLot]
    conclusion: ArticleConclusion


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.get("/generate-article/{artist_id}", response_model=ArticleResponse)
async def generate_article(artist_id: str):
    """
    Generates a structured JSON article about the provided artist_id.
    Calls MutualArt GraphQL to fetch auction data, then calls Grok to
    synthesise the article and return it as a typed JSON response.
    """
    try:
        # 1. Build prompt with live auction data
        prompt = await build_article_prompt(artist_id)
        if not prompt:
            raise HTTPException(
                status_code=404,
                detail=f"No auction data found for artist ID: {artist_id}"
            )

        # 2. Call Grok — get back a raw JSON string
        raw_json = await generate_article_from_prompt(prompt)

        # 3. Parse and validate against Pydantic schema
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Grok returned invalid JSON: {e}. Raw: {raw_json[:300]}"
            )

        return ArticleResponse(**parsed)

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=500, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


# If started directly (e.g. python main.py)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
