"""Build a clean, self-contained delivery ZIP from an explicit allowlist.

TD-RELEASE-v2 F-02: this script never existed in repo history
(`git log --all -- build_portable_package.py` is empty) even though README
has long described it as part of the delivery workflow. Written fresh
against that description, reusing the existing PAGE_ROUTES/ROOT_STATIC_FILES/
ASSET_STATIC_FILES/JS_MODULE_STATIC_FILES allowlists in market_config.py so
there is a single source of truth for "what ships" shared with the Flask
route wiring and portable_check.py.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path

from derivatives_store import DerivativesStore
from market_config import (
    ASSET_STATIC_FILES,
    JS_MODULE_STATIC_FILES,
    PAGE_ROUTES,
    ROOT_STATIC_FILES,
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_NAME = "market-platform-portable-optimized.zip"
DB_NAME = "derivatives-platform.sqlite3"

BACKEND_MODULES = [
    "app.py",
    "market_config.py",
    "derivatives_store.py",
    "fetch_registry.py",
    "fetchers.py",
    "builders.py",
    "cache.py",
    "security.py",
    "parsers.py",
    "routes_system.py",
    "routes_global_market.py",
    "routes_twse.py",
    "routes_derivatives.py",
    "clean_derivatives_db.py",
    "e2e_smoke.py",
    "verify_release_integrity.py",
    "live_source_validation.py",
    "portable_check.py",
    "build_portable_package.py",
    "security_guardrail_check.py",
    "test_derivatives_platform.py",
]

MISC_FILES = [
    "requirements.txt",
    "Procfile",
    "render.yaml",
    "manifest.webmanifest",
    "service-worker.js",
    "README.md",
    "README_使用說明.md",
    "PORTABLE_README.md",
    "CLOUD_DEPLOYMENT.md",
    "START_WEBSITE.bat",
    "START_MOBILE_APP.bat",
    ".gitattributes",
    ".editorconfig",
]

# Whole-directory copies (minus __pycache__): no per-file allowlist constant
# exists for these in market_config.py the way there is for JS_MODULE_STATIC_FILES.
WHOLE_DIRS = ["derivatives", "tests"]


def _iter_dir_files(dir_name: str) -> list[Path]:
    root = BASE_DIR / dir_name
    return [
        path.relative_to(BASE_DIR)
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    ]


def collect_allowlisted_files() -> list[Path]:
    relative_paths: list[Path] = []
    relative_paths.extend(Path(name) for name in BACKEND_MODULES)
    relative_paths.extend(Path(name) for name in MISC_FILES)
    relative_paths.extend(Path(name) for name in sorted(set(PAGE_ROUTES.values())))
    relative_paths.extend(Path(name) for name in sorted(ROOT_STATIC_FILES))
    relative_paths.extend(Path("assets") / name for name in sorted(ASSET_STATIC_FILES))
    relative_paths.extend(Path("js") / name for name in sorted(JS_MODULE_STATIC_FILES))
    for dir_name in WHOLE_DIRS:
        relative_paths.extend(_iter_dir_files(dir_name))

    missing = [str(path) for path in relative_paths if not (BASE_DIR / path).is_file()]
    if missing:
        raise FileNotFoundError(f"Allowlisted files missing from working tree: {missing}")
    return relative_paths


def build(output_path: Path) -> Path:
    files = collect_allowlisted_files()
    with tempfile.TemporaryDirectory(prefix="market-pulse-portable-") as tmp_name:
        staging = Path(tmp_name)
        for relative in files:
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(BASE_DIR / relative, destination)

        # Ship a schema-only DB (table structure, zero data rows) instead of
        # copying the live working-tree database, so delivery is reproducible
        # and never leaks a snapshot of real market data.
        DerivativesStore(staging / DB_NAME).initialize()

        if output_path.exists():
            output_path.unlink()
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging))

    return output_path


def main() -> int:
    output_path = BASE_DIR / OUTPUT_NAME
    build(output_path)
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    print(f"{OUTPUT_NAME}: {output_path.stat().st_size} bytes, sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
