from google import genai
from google.genai import types
from django.conf import settings
from .prompts import SYSTEM_PROMPT

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def get_ai_response(message_history: list[dict], new_message: str) -> str:
    gemini_history = [
        types.Content(
            role=msg["role"] if msg["role"] == "user" else "model",
            parts=[types.Part(text=msg["content"])]
        )
        for msg in message_history
    ]

    chat = client.chats.create(
        model="gemini-3.1-flash-lite",
        history=gemini_history,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT
        )
    )
    response = chat.send_message(new_message)
    return response.text