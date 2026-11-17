import json
import logging
import time

from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.crisis.layer import (
    apply_crisis_layer,
    build_emergency_reply,
    crisis_suffix,
    strip_emoji,
)
from apps.crisis.detection import detect_crisis

from .memory import get_history, maybe_summarize
from .models import Conversation, Message
from .services import get_ai_response, stream_ai_response
from .throttles import ChatBurstThrottle, ChatDailyThrottle

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4000


def _error(code, message, status):
    return Response({'error': message, 'code': code}, status=status)


def _prepare(request):
    data = request.data if isinstance(request.data, dict) else {}
    user_message = data.get('message')
    conversation_id = data.get('conversation_id')

    if not isinstance(user_message, str) or not user_message.strip():
        return _error('message_required', 'Field "message" is required.', 400), None, None, None
    if len(user_message) > MAX_MESSAGE_LENGTH:
        error = _error(
            'message_too_long',
            f'Message is too long (max {MAX_MESSAGE_LENGTH} characters).',
            400,
        )
        return error, None, None, None

    conversation = None
    history = []
    if conversation_id is not None:
        try:
            conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            error = _error('invalid_conversation_id', 'conversation_id must be a number.', 400)
            return error, None, None, None
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        history = get_history(conversation)

    return None, user_message, conversation, history


def _failure(exc, user_message, user):
    logger.error('AI call failed', exc_info=exc)
    emergency = build_emergency_reply(user_message, user)
    if emergency is not None:
        return emergency, None
    if getattr(exc, 'code', None) == 429:
        return None, _error('ai_quota', 'Too many requests, try again later.', 429)
    return None, _error(
        'ai_unavailable',
        'The AI service is temporarily unavailable, please try again later.',
        503,
    )


def _save_exchange(user, conversation, user_text, received_at, reply_text, *,
                    first_token_ms=None, duration_ms=None, interrupted=False):
    with transaction.atomic():
        if conversation is None:
            conversation = Conversation.objects.create(user=user, created_at=received_at)
        user_msg = Message.objects.create(
            conversation=conversation, role='user', content=user_text, created_at=received_at
        )
        bot_msg = Message.objects.create(
            conversation=conversation,
            role='model',
            content=reply_text,
            first_token_ms=first_token_ms,
            duration_ms=duration_ms,
            interrupted=interrupted,
        )
    return conversation, user_msg, bot_msg


def _result_payload(conversation, user_msg, bot_msg, text, crisis):
    return {
        'response': text,
        'conversation_id': conversation.id,
        'crisis': crisis,
        'user_message': {
            'id': user_msg.id,
            'created_at': user_msg.created_at.isoformat(),
        },
        'bot_message': {
            'id': bot_msg.id,
            'created_at': bot_msg.created_at.isoformat(),
            'first_token_ms': bot_msg.first_token_ms,
            'duration_ms': bot_msg.duration_ms,
            'interrupted': bot_msg.interrupted,
        },
    }


def _elapsed_ms(started):
    return max(0, int((time.monotonic() - started) * 1000))


@api_view(['POST'])
@throttle_classes([ChatBurstThrottle, ChatDailyThrottle])
@permission_classes([IsAuthenticated])
def chat_view(request):
    received_at = timezone.now()
    started = time.monotonic()

    error, user_message, conversation, history = _prepare(request)
    if error is not None:
        return error

    crisis = False
    timing = {}
    try:
        ai_response = get_ai_response(history, user_message, request.user)
    except Exception as exc:
        emergency, failure = _failure(exc, user_message, request.user)
        if failure is not None:
            return failure
        ai_response, crisis = emergency, True
    else:
        timing = {'duration_ms': _elapsed_ms(started)}
        ai_response, crisis = apply_crisis_layer(user_message, ai_response, request.user)

    if not ai_response or not ai_response.strip():
        return _error('ai_empty', 'The AI service returned an empty response.', 502)

    conversation, user_msg, bot_msg = _save_exchange(
        request.user, conversation, user_message, received_at, ai_response, **timing
    )
    maybe_summarize(conversation)

    return Response(_result_payload(conversation, user_msg, bot_msg, ai_response, crisis))


def _line(event):
    return json.dumps(event, ensure_ascii=False) + '\n'


def _timed(first_text, chunks):
    if first_text:
        yield first_text, time.monotonic()
    for text in chunks:
        yield text, time.monotonic()


def _stream_body(*, user, user_message, conversation, received_at, started,
                    chunks, first_text, first_at, crisis):

    created_here = conversation is None
    saved = False
    delivered = []
    first_ms = None

    try:
        if created_here:
            conversation = Conversation.objects.create(user=user, created_at=received_at)
        yield _line({'type': 'start', 'conversation_id': conversation.id, 'crisis': crisis})

        for raw, arrived in _timed(first_text, chunks):
            text = strip_emoji(raw) if crisis else raw
            if not text:
                continue
            if first_ms is None:
                first_ms = max(0, int((time.monotonic() - started) * 1000))
            delivered.append(text)
            yield _line({'type': 'delta', 'text': text})

        full = ''.join(delivered)
        if crisis:
            suffix = crisis_suffix(full, user)
            if suffix:
                delivered.append(suffix)
                full += suffix
                yield _line({'type': 'delta', 'text': suffix})

        full = full.strip()
        if not full:
            yield _line({'type': 'error', 'code': 'ai_empty', 'partial': False})
            return

        conversation, user_msg, bot_msg = _save_exchange(
            user, conversation, user_message, received_at, full,
            first_token_ms=first_ms, duration_ms=_elapsed_ms(started),
        )
        saved = True
        yield _line({'type': 'done', **_result_payload(conversation, user_msg, bot_msg, full, crisis)})
    except Exception as exc:
        logger.error('Streaming reply failed', exc_info=exc)
        code = 'ai_quota' if getattr(exc, 'code', None) == 429 else 'ai_unavailable'
        yield _line({'type': 'error', 'code': code, 'partial': bool(delivered)})
    finally:
        try:
            chunks.close()
        except Exception:
            pass

        summarize_target = conversation if saved else None
        if not saved:
            partial = ''.join(delivered).strip()
            if partial:
                if crisis:
                    partial = (partial + crisis_suffix(partial, user)).strip()
                conversation, _, _ = _save_exchange(
                    user, conversation, user_message, received_at, partial,
                    first_token_ms=first_ms, duration_ms=_elapsed_ms(started),
                    interrupted=True,
                )
                summarize_target = conversation
            elif created_here and conversation is not None:
                Conversation.objects.filter(pk=conversation.pk).delete()
        if summarize_target is not None:
            maybe_summarize(summarize_target)


@api_view(['POST'])
@throttle_classes([ChatBurstThrottle, ChatDailyThrottle])
@permission_classes([IsAuthenticated])
def chat_stream_view(request):
    received_at = timezone.now()
    started = time.monotonic()

    error, user_message, conversation, history = _prepare(request)
    if error is not None:
        return error

    chunks = stream_ai_response(history, user_message, request.user)
    try:
        first_text = next(chunks)
        first_at = time.monotonic()
    except StopIteration:
        return _error('ai_empty', 'The AI service returned an empty response.', 502)
    except Exception as exc:
        emergency, failure = _failure(exc, user_message, request.user)
        if failure is not None:
            return failure
        conversation, user_msg, bot_msg = _save_exchange(
            request.user, conversation, user_message, received_at, emergency
        )
        maybe_summarize(conversation)
        return Response(_result_payload(conversation, user_msg, bot_msg, emergency, True))

    body = _stream_body(
        user=request.user,
        user_message=user_message,
        conversation=conversation,
        received_at=received_at,
        started=started,
        chunks=chunks,
        first_text=first_text,
        first_at=first_at,
        crisis=detect_crisis(user_message),
    )

    class SafeStreamingHttpResponse(StreamingHttpResponse):
        def close(self):
            try:
                if hasattr(body, 'close'):
                    body.close()
            except Exception:
                pass
            super().close()

    response = SafeStreamingHttpResponse(
        body, content_type='application/x-ndjson; charset=utf-8'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
