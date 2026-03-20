"""Locale configuration and metadata."""

DEFAULT_LOCALE = "en"
FALLBACK_LOCALE = "en"

LOCALE_METADATA = {
    "ar": {"label": "Arabic", "native_label": "العربية", "rtl": True},
    "bn": {"label": "Bengali", "native_label": "বাংলা", "rtl": False},
    "de": {"label": "German", "native_label": "Deutsch", "rtl": False},
    "en": {"label": "English", "native_label": "English", "rtl": False},
    "es": {"label": "Spanish", "native_label": "Español", "rtl": False},
    "fa": {"label": "Farsi/Persian", "native_label": "فارسی", "rtl": True},
    "fr": {"label": "French", "native_label": "Français", "rtl": False},
    "he": {"label": "Hebrew", "native_label": "עברית", "rtl": True},
    "hi": {"label": "Hindi", "native_label": "हिन्दी", "rtl": False},
    "id": {"label": "Indonesian", "native_label": "Bahasa Indonesia", "rtl": False},
    "it": {"label": "Italian", "native_label": "Italiano", "rtl": False},
    "ja": {"label": "Japanese", "native_label": "日本語", "rtl": False},
    "ko": {"label": "Korean", "native_label": "한국어", "rtl": False},
    "ms": {"label": "Malay", "native_label": "Bahasa Melayu", "rtl": False},
    "nl": {"label": "Dutch", "native_label": "Nederlands", "rtl": False},
    "pl": {"label": "Polish", "native_label": "Polski", "rtl": False},
    "pt": {"label": "Portuguese", "native_label": "Português", "rtl": False},
    "pt_BR": {"label": "Brazilian Portuguese", "native_label": "Português (Brasil)", "rtl": False},
    "ru": {"label": "Russian", "native_label": "Русский", "rtl": False},
    "sw": {"label": "Swahili", "native_label": "Kiswahili", "rtl": False},
    "ta": {"label": "Tamil", "native_label": "தமிழ்", "rtl": False},
    "th": {"label": "Thai", "native_label": "ไทย", "rtl": False},
    "tl": {"label": "Tagalog", "native_label": "Tagalog", "rtl": False},
    "tr": {"label": "Turkish", "native_label": "Türkçe", "rtl": False},
    "uk": {"label": "Ukrainian", "native_label": "Українська", "rtl": False},
    "ur": {"label": "Urdu", "native_label": "اردو", "rtl": True},
    "vi": {"label": "Vietnamese", "native_label": "Tiếng Việt", "rtl": False},
    "zh_CN": {"label": "Simplified Chinese", "native_label": "简体中文", "rtl": False},
    "zh_TW": {"label": "Traditional Chinese", "native_label": "繁體中文", "rtl": False},
}

RTL_LOCALES = {
    locale_code
    for locale_code, metadata in LOCALE_METADATA.items()
    if metadata.get("rtl")
}
