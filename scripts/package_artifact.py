from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
APP_SLUG = "kunqiong-id-photo"


def main() -> int:
    source = DIST_DIR / f"{APP_SLUG}.app"

    if not source.exists():
        raise FileNotFoundError(f"Build output not found: {source}")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    archive_base = ARTIFACTS_DIR / f"{APP_SLUG}-macos"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=source.parent, base_dir=source.name)
    print(f"Created archive: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
