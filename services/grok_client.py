import os
import re
from xai_sdk import AsyncClient
from xai_sdk.chat import user, system


def _strip_markdown_fences(text: str) -> str:
    """
    Strip markdown code fences that LLMs sometimes wrap JSON in.
    Handles: ```json ... ```, ``` ... ```, and leading/trailing whitespace.
    """
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ``` fences
    match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


async def generate_article_from_prompt(prompt: str) -> str:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise ValueError("XAI_API_KEY environment variable is not set.")

    client = AsyncClient(api_key=api_key)
    chat = client.chat.create(model="grok-4-1-fast-non-reasoning-latest")

    chat.append(system(
        "You are a precise AI that outputs only valid JSON. "
        "Never include markdown code fences, preamble, or any text outside the JSON object. "
        "Your entire response must start with '{' and end with '}'."
    ))
    chat.append(user(prompt))

    full_response = ""
    async for response, chunk in chat.stream():
        if chunk.content:
            full_response += chunk.content

    return _strip_markdown_fences(full_response)
