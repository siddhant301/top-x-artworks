import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import from our services layer
from services.prompt_builder import build_article_prompt
from services.grok_client import stream_article_from_prompt

app = FastAPI(
    title="MutualArt Article Generator AI Service",
    description="Generates editorial articles about an artist's top artworks via MutualArt GraphQL and Grok API.",
    version="1.0.0"
)

class ArticleResponse(BaseModel):
    artist_id: str
    article: str

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

@app.get("/generate-article/{artist_id}")
async def generate_article(artist_id: str):
    """
    Generates a full AI article about the provided artist_id and streams it back.
    This safely leverages httpx and async I/O internally for concurrency.
    """
    try:
        # 1. Gather context data and construct prompt string
        prompt = await build_article_prompt(artist_id)
        if not prompt:
            raise HTTPException(status_code=404, detail=f"No data found for artist ID: {artist_id}")
            
        # 2. Return a streaming response back to the client
        return StreamingResponse(stream_article_from_prompt(prompt), media_type="text/plain")
        
    except ValueError as ve:
        # E.g. Missing API keys
        raise HTTPException(status_code=500, detail=str(ve))
    except Exception as e:
        # Any unexpected network or GraphQL errors
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# If started directly (e.g. python main.py)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
