from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

import PyInstaller.__main__


ROOT_DIR = Path(__file__).resolve().parent.parent
MAIN_FILE = ROOT_DIR / "main.py"
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
APP_SLUG = "kunqiong-id-photo"
RUNTIME_HOOK = ROOT_DIR / "runtime_hook_meipass.py"


def add_data_argument(arguments: list[str], source: Path, destination: str) -> None:
    separator = ";" if os.name == "nt" else ":"
    arguments.extend(["--add-data", f"{source}{separator}{destination}"])


def append_asset_files(arguments: list[str]) -> None:
    for asset_name in ("logo.png", "logo.ico", "biglogo.png", "kunqiong.ico"):
        asset_path = ROOT_DIR / asset_name
        if asset_path.exists():
            add_data_argument(arguments, asset_path, ".")

    models_dir = ROOT_DIR / "models"
    if not models_dir.exists():
        return

    for source_path in models_dir.rglob("*"):
        if not source_path.is_file():
            continue
        relative_path = source_path.relative_to(ROOT_DIR)
        destination = str(relative_path.parent).replace("\\", "/")
        add_data_argument(arguments, source_path, destination)


def build_arguments() -> list[str]:
    system = platform.system()
    arguments = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_SLUG,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--paths",
        str(ROOT_DIR),
        "--runtime-hook",
        str(RUNTIME_HOOK),
        "--collect-submodules",
        "ui",
        "--collect-submodules",
        "modules",
        "--collect-submodules",
        "utils",
        "--collect-submodules",
        "i18n",
        "--collect-submodules",
        "onnxruntime",
        "--collect-submodules",
        "mtcnnruntime",
        "--collect-data",
        "mtcnnruntime",
        "--hidden-import",
        "PIL.Image",
        "--hidden-import",
        "PIL.ImageFont",
        "--hidden-import",
        "PIL.ImageDraw",
        "--hidden-import",
        "cv2",
        "--hidden-import",
        "numpy",
        "--hidden-import",
        "PyQt6.QtSvg",
        "--exclude-module",
        "torch",
        "--exclude-module",
        "torchvision",
        "--exclude-module",
        "torchaudio",
        "--exclude-module",
        "rembg",
    ]

    if system == "Windows":
        icon_path = ROOT_DIR / "logo.ico"
        if icon_path.exists():
            arguments.extend(["--icon", str(icon_path)])

    append_asset_files(arguments)
    arguments.append(str(MAIN_FILE))
    return arguments


def clean_previous_outputs() -> None:
    for path in (DIST_DIR / APP_SLUG, DIST_DIR / f"{APP_SLUG}.app", BUILD_DIR):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    if not MAIN_FILE.exists():
        raise FileNotFoundError(f"Unable to find entrypoint: {MAIN_FILE}")

    clean_previous_outputs()
    arguments = build_arguments()
    print("Running PyInstaller with arguments:")
    for argument in arguments:
        print(f"  {argument}")
    PyInstaller.__main__.run(arguments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
