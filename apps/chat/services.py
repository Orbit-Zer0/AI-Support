from functools import lru_cache

from django.conf import settings
from google import genai
from google.genai import types

from apps.crisis.services import build_crisis_block_for_user

from .prompts import build_system_prompt

MODEL = 'gemini-3.1-flash-lite'


@lru_cache(maxsize=1)
def _get_client():
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _default_language_name(user):
    profile = getattr(user, 'profile', None)
    language = getattr(profile, 'language', None)
    return language.name if language else 'English'


def get_ai_response(message_history: list[dict], new_message: str, user) -> str:
    system_prompt = build_system_prompt(
        crisis_block=build_crisis_block_for_user(user),
        default_language=_default_language_name(user),
    )

    gemini_history = [
        types.Content(
            role=msg["role"] if msg["role"] == "user" else "model",
            parts=[types.Part(text=msg["content"])],
        )
        for msg in message_history
    ]

    chat = _get_client().chats.create(
        model=MODEL,
        history=gemini_history,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    response = chat.send_message(new_message)
    return response.text