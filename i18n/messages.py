"""Message loading, locale normalization, and translation lookup."""

import importlib
import locale as system_locale
import os
from typing import Dict, List, Optional

from .config import DEFAULT_LOCALE, FALLBACK_LOCALE, LOCALE_METADATA, RTL_LOCALES
from .types import MessageMap

_LOCALE_MODULE_CACHE: Dict[str, MessageMap] = {}
_CURRENT_LOCALE = DEFAULT_LOCALE


def normalize_locale(locale_code: Optional[str]) -> str:
    if not locale_code:
        return DEFAULT_LOCALE

    normalized = locale_code.replace("-", "_")
    normalized = normalized.split(".")[0]

    if normalized in LOCALE_METADATA:
        return normalized

    lowered = normalized.lower()
    for candidate in LOCALE_METADATA:
        if candidate.lower() == lowered:
            return candidate

    language_only = lowered.split("_")[0]
    for candidate in LOCALE_METADATA:
        if candidate.lower() == language_only:
            return candidate

    return DEFAULT_LOCALE


def detect_system_locale() -> str:
    env_locale = os.environ.get("APP_LOCALE") or os.environ.get("LANG")
    if env_locale:
        return normalize_locale(env_locale)

    try:
        locale_value = system_locale.getdefaultlocale()[0]
    except (TypeError, ValueError, IndexError):
        locale_value = None

    return normalize_locale(locale_value)


def load_locale_messages(locale_code: str) -> MessageMap:
    normalized = normalize_locale(locale_code)
    cached = _LOCALE_MODULE_CACHE.get(normalized)
    if cached is not None:
        return cached

    module = importlib.import_module("i18n.locales.{0}".format(normalized))
    messages = getattr(module, "MESSAGES", {})
    _LOCALE_MODULE_CACHE[normalized] = messages
    return messages


def set_locale(locale_code: Optional[str]) -> str:
    global _CURRENT_LOCALE
    _CURRENT_LOCALE = normalize_locale(locale_code)
    return _CURRENT_LOCALE


def initialize_i18n(locale_code: Optional[str] = None) -> str:
    return set_locale(locale_code or detect_system_locale())


def get_current_locale() -> str:
    return _CURRENT_LOCALE


def get_supported_locales() -> List[str]:
    return list(LOCALE_METADATA.keys())


def get_locale_label(locale_code: str, native: bool = False) -> str:
    normalized = normalize_locale(locale_code)
    metadata = LOCALE_METADATA.get(normalized, {})
    if native:
        return metadata.get("native_label", normalized)
    return metadata.get("label", normalized)


def is_rtl_locale(locale_code: Optional[str] = None) -> bool:
    normalized = normalize_locale(locale_code or _CURRENT_LOCALE)
    return normalized in RTL_LOCALES


def _format_message(message: str, **kwargs) -> str:
    if not kwargs:
        return message
    try:
        return message.format(**kwargs)
    except Exception:
        return message


def tr(key: str, locale_code: Optional[str] = None, **kwargs) -> str:
    requested_locale = normalize_locale(locale_code or _CURRENT_LOCALE)
    requested_messages = load_locale_messages(requested_locale)

    if key in requested_messages:
        return _format_message(requested_messages[key], **kwargs)

    fallback_messages = load_locale_messages(FALLBACK_LOCALE)
    if key in fallback_messages:
        return _format_message(fallback_messages[key], **kwargs)

    return _format_message(key, **kwargs)
