from apps.accounts.user_settings import get_user_settings
from .styles import build_style_block

import logging
import re
from functools import lru_cache

from django.conf import settings
from google import genai
from google.genai import types

from apps.crisis.services import build_crisis_block_for_user

from .prompts import SUMMARY_PROMPT, TITLE_PROMPT, build_system_prompt

logger = logging.getLogger(__name__)

RETRYABLE_CODES = {404, 429, 503}
MAX_TITLE_CHARS = 60


@lru_cache(maxsize=1)
def _get_client():
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _models_to_try():
    models = [settings.GEMINI_MODEL, *settings.GEMINI_FALLBACK_MODELS]
    unique = []
    for model in models:
        if model and model not in unique:
            unique.append(model)
    return unique


def _run_with_fallback(run):
    last_error = None
    for model in _models_to_try():
        try:
            return run(model)
        except Exception as exc:
            code = getattr(exc, 'code', None)
            if code not in RETRYABLE_CODES:
                raise
            logger.warning('Model %s failed with code %s, trying the next one', model, code)
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError('No Gemini model is configured')


def _default_language_name(user):
    profile = getattr(user, 'profile', None)
    language = getattr(profile, 'language', None)
    return language.name if language else 'English'

def _style_block_for(user):
    try:
        return build_style_block(get_user_settings(user)['ai_style'])
    except Exception:
        logger.exception('Failed to load AI style settings')
        return build_style_block(None)

def get_ai_response(message_history: list[dict], new_message: str, user) -> str:
    system_prompt = build_system_prompt(
        crisis_block=build_crisis_block_for_user(user),
        default_language=_default_language_name(user),
        style_block=_style_block_for(user),
    )

    gemini_history = [
        types.Content(
            role=msg["role"] if msg["role"] == "user" else "model",
            parts=[types.Part(text=msg["content"])],
        )
        for msg in message_history
    ]

    def run(model):
        chat = _get_client().chats.create(
            model=model,
            history=gemini_history,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        return chat.send_message(new_message).text

    return _run_with_fallback(run)


def summarize_conversation(previous_summary: str, messages: list[dict]) -> str:
    transcript = '\n'.join(
        f"{'USER' if m['role'] == 'user' else 'ASSISTANT'}: {m['content']}"
        for m in messages
    ).replace('</transcript>', '')
    previous = (previous_summary or '').replace('</previous_summary>', '')

    contents = (
        f"<previous_summary>\n{previous}\n</previous_summary>\n\n"
        f"<transcript>\n{transcript}\n</transcript>"
    )

    def run(model):
        chat = _get_client().chats.create(
            model=model,
            config=types.GenerateContentConfig(system_instruction=SUMMARY_PROMPT),
        )
        return chat.send_message(contents).text

    return _run_with_fallback(run)


def clean_title(text):
    text = (text or '').strip()
    if not text:
        return ''
    first_line = text.splitlines()[0]
    cleaned = re.sub(r'["“”«»*#_`]', '', first_line)
    cleaned = ' '.join(cleaned.split()).strip(' .\t')
    return cleaned[:MAX_TITLE_CHARS].rstrip()


def generate_title(user_message: str, ai_reply: str) -> str:
    first = (user_message or '')[:500].replace('</conversation>', '')
    reply = (ai_reply or '')[:500].replace('</conversation>', '')
    contents = f"<conversation>\nUSER: {first}\nASSISTANT: {reply}\n</conversation>"

    def run(model):
        chat = _get_client().chats.create(
            model=model,
            config=types.GenerateContentConfig(system_instruction=TITLE_PROMPT),
        )
        return chat.send_message(contents).text

    return clean_title(_run_with_fallback(run))