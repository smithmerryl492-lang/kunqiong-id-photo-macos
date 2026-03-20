"""Configuration helpers."""

import json
import os
import sys

from i18n import tr

_FROZEN_RETINAFACE_ONNX = "models/retinaface/retinaface-resnet50.onnx"
_FROZEN_HIVISION_ONNX = "models/u2net/hivision_modnet.onnx"


def _get_resource_path(relative_path):
    """Return an absolute resource path for dev and frozen builds."""
    if not relative_path or relative_path.strip() == "":
        relative_path = "models"
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass_path = os.path.normpath(os.path.join(meipass, relative_path))
            return os.path.abspath(meipass_path)
        internal_path = os.path.normpath(os.path.join(exe_dir, "_internal", relative_path))
        if os.path.exists(internal_path):
            return internal_path
        exe_path = os.path.normpath(os.path.join(exe_dir, relative_path))
        if os.path.exists(exe_path):
            return exe_path
        return internal_path

    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.normpath(os.path.abspath(os.path.join(base_path, relative_path)))


def get_retinaface_onnx_path():
    """Return the RetinaFace ONNX file path."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return os.path.normpath(
                os.path.join(
                    os.path.abspath(meipass),
                    "models",
                    "retinaface",
                    "retinaface-resnet50.onnx",
                )
            )
    return os.path.abspath(
        os.path.join(_get_resource_path("models"), "retinaface", "retinaface-resnet50.onnx")
    )


def get_hivision_modnet_onnx_path():
    """Return the hivision MODNet ONNX file path."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return os.path.normpath(
                os.path.join(
                    os.path.abspath(meipass),
                    "models",
                    "u2net",
                    "hivision_modnet.onnx",
                )
            )
    return os.path.abspath(
        os.path.join(_get_resource_path("models"), "u2net", "hivision_modnet.onnx")
    )


MODEL_DIR = _get_resource_path("models")
MODELS_DIR = MODEL_DIR
U2NET_MODEL_DIR = os.path.join(MODEL_DIR, "u2net")

DEFAULT_BRUSH_SIZE = 20
DEFAULT_SCALE = 2
DEFAULT_FEATHER = 3

SUPPORTED_IMAGE_FORMATS = [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"]

FORCE_CPU = True
CUDA_VISIBLE_DEVICES = "-1"

TEMP_DIR = "temp"
CLEANUP_TEMP_FILES = True

SOFT_NUMBER = "10037"

VERSION = "V1.0"
WINDOW_TITLE = f"鲲穹AI证件照 {VERSION}"
APP_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".kunqiong_id_photo")
APP_CONFIG_PATH = os.path.join(APP_CONFIG_DIR, "settings.json")


def get_window_title():
    """Return the localized application title."""
    return tr("app.title", version=VERSION)


def get_footer_text():
    """Return the localized footer text."""
    return tr("app.footer", version=VERSION)


def load_app_settings():
    """Load user-scoped app settings from disk."""
    try:
        if not os.path.exists(APP_CONFIG_PATH):
            return {}
        with open(APP_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_app_settings(settings):
    """Persist user-scoped app settings to disk."""
    os.makedirs(APP_CONFIG_DIR, exist_ok=True)
    with open(APP_CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, ensure_ascii=False, indent=2)


def get_saved_locale():
    """Return the persisted locale preference if available."""
    locale_code = load_app_settings().get("locale")
    return locale_code if isinstance(locale_code, str) and locale_code.strip() else None


def save_locale(locale_code):
    """Persist the locale preference."""
    settings = load_app_settings()
    settings["locale"] = locale_code
    save_app_settings(settings)


WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 650
WINDOW_DEFAULT_WIDTH = 1380
WINDOW_DEFAULT_HEIGHT = 900
