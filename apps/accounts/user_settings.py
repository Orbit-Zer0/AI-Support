import copy
import re

from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

HEX_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')

CHOICE_FIELDS = {
    'theme': ('light', 'dark', 'auto'),
    'font_size': ('small', 'medium', 'large', 'xlarge'),
    'font_family': ('system', 'serif', 'mono', 'readable'),
}
COLOR_FIELDS = ('user_bubble', 'bot_bubble')

DEFAULTS = {
    'appearance': {
        'theme': 'auto',
        'user_bubble': None,
        'bot_bubble': None,
        'font_size': 'medium',
        'font_family': 'system',
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


CLEANERS = {'appearance': _clean_appearance_value}


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