import copy
import re

from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from .models import UserSettings

HEX_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')

CHOICE_FIELDS = {
    'theme': ('light', 'dark', 'auto'),
    'font_size': ('small', 'medium', 'large', 'xlarge'),
    'font_family': ('system', 'serif', 'mono', 'readable'),
}
COLOR_FIELDS = ('user_bubble', 'bot_bubble')

AI_PRESETS = ('balanced', 'gentle', 'calm', 'direct', 'upbeat', 'custom')
AI_EMOJI = ('off', 'rare', 'often')
AI_LEVEL_FIELDS = ('warmth', 'enthusiasm')

DEFAULTS = {
    'appearance': {
        'theme': 'auto',
        'user_bubble': None,
        'bot_bubble': None,
        'font_size': 'medium',
        'font_family': 'system',
    },
    'ai_style': {
        'preset': 'balanced',
        'warmth': 3,
        'enthusiasm': 2,
        'emoji': 'off',
    },
}


def _invalid(message):
    return serializers.ValidationError(
        {'settings': [ErrorDetail(message, code='invalid_settings')]}
    )


def _clean_appearance_value(key, value):
    if key in CHOICE_FIELDS:
        if isinstance(value, str) and value in CHOICE_FIELDS[key]:
            return value
        raise _invalid(f'Invalid value for {key}.')
    if key in COLOR_FIELDS:
        if value is None:
            return None
        if isinstance(value, str) and HEX_COLOR.match(value):
            return value.lower()
        raise _invalid(f'Invalid color for {key}.')
    raise _invalid(f'Unknown setting: {key}.')


def _clean_ai_style_value(key, value):
    if key == 'preset':
        if isinstance(value, str) and value in AI_PRESETS:
            return value
        raise _invalid('Invalid value for preset.')
    if key in AI_LEVEL_FIELDS:
        if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5:
            return value
        raise _invalid(f'Invalid value for {key}.')
    if key == 'emoji':
        if isinstance(value, str) and value in AI_EMOJI:
            return value
        raise _invalid('Invalid value for emoji.')
    raise _invalid(f'Unknown setting: {key}.')


CLEANERS = {
    'appearance': _clean_appearance_value,
    'ai_style': _clean_ai_style_value,
}


def effective_settings(stored):
    result = copy.deepcopy(DEFAULTS)
    stored = stored if isinstance(stored, dict) else {}
    for section, cleaner in CLEANERS.items():
        values = stored.get(section)
        if not isinstance(values, dict):
            continue
        for key in result[section]:
            if key in values:
                try:
                    result[section][key] = cleaner(key, values[key])
                except serializers.ValidationError:
                    pass
    return result


def apply_patch(stored, patch):
    if not isinstance(patch, dict):
        raise _invalid('Settings must be an object.')

    merged = copy.deepcopy(stored) if isinstance(stored, dict) else {}
    for section, values in patch.items():
        cleaner = CLEANERS.get(section)
        if cleaner is None:
            raise _invalid(f'Unknown section: {section}.')
        if not isinstance(values, dict):
            raise _invalid(f'Section {section} must be an object.')
        current = merged.get(section)
        current = current if isinstance(current, dict) else {}
        for key, value in values.items():
            current[key] = cleaner(key, value)
        merged[section] = current
    return merged


def get_user_settings(user):
    record = UserSettings.objects.filter(user=user).first()
    return effective_settings(record.data if record else {})