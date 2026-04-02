import os
from xai_sdk import AsyncClient
from xai_sdk.chat import user, system

async def stream_article_from_prompt(prompt: str):
    """
    Sends the generated prompt to the Grok API and yields chunks of the article.
    """
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise ValueError("XAI_API_KEY environment variable is not set. Please set it in .env")
        
    client = AsyncClient(api_key=api_key)
    chat = client.chat.create(model="grok-4-1-fast-non-reasoning-latest")
    
    # Send system instructions
    chat.append(system("You are Grok, a highly intelligent, helpful AI assistant."))
    
    # Send user prompt
    chat.append(user(prompt))
    
    # Stream the response
    async for response, chunk in chat.stream():
        if chunk.content:
            yield chunk.content
