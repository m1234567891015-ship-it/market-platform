"""Build a deterministic, allowlist-only Cloudflare Static Assets directory."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from market_config import ASSET_STATIC_FILES, JS_MODULE_STATIC_FILES, PAGE_ROUTES, ROOT_STATIC_FILES

DIST_ROOT = REPO_ROOT / "dist" / "cloudflare-static"
MANIFEST_NAME = "cloudflare-dist-manifest.json"
ROUTES_NAME = "_routes.json"

# Files deliberately added to the existing frontend allowlists for the PWA and
# Static Assets runtime. Runtime data such as twse-cache.json is never copied.
EXTRA_ROOT_FILES = {"manifest.webmanifest", "service-worker.js"}
EXTRA_ASSET_FILES: set[str] = set()


def source_targets() -> list[tuple[Path, str]]:
    targets: list[tuple[Path, str]] = []
    pages = {name for name in PAGE_ROUTES.values() if name.endswith(".html")}
    for name in sorted(pages):
        targets.append((REPO_ROOT / name, name))
    for name in sorted((ROOT_STATIC_FILES | EXTRA_ROOT_FILES) - {"twse-cache.json"}):
        targets.append((REPO_ROOT / name, name))
    for name in sorted(ASSET_STATIC_FILES | EXTRA_ASSET_FILES):
        targets.append((REPO_ROOT / "assets" / name, f"assets/{name}"))
    for name in sorted(JS_MODULE_STATIC_FILES):
        targets.append((REPO_ROOT / "js" / name, f"js/{name}"))
    return targets


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_dist(output_root: Path = DIST_ROOT) -> dict:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    entries = []
    for source, relative in source_targets():
        if not source.is_file():
            raise FileNotFoundError(f"allowlisted frontend file is missing: {source}")
        destination = output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        entries.append({"path": relative.replace("\\", "/"), "sha256": sha256(destination), "size": destination.stat().st_size})

    headers = output_root / "_headers"
    headers.write_text(
        """/*
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'self'; frame-ancestors 'none'
  Strict-Transport-Security: max-age=31536000; includeSubDomains

/api/*
  Cache-Control: no-store, no-cache, must-revalidate, max-age=0
  Pragma: no-cache
  Expires: 0
""",
        encoding="utf-8",
        newline="\n",
    )

    manifest = {
        "format": 1,
        "asset_file_count": len(entries),
        "files": sorted(entries, key=lambda item: item["path"]),
    }
    (output_root / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_root / ROUTES_NAME).write_text(
        json.dumps({"version": 1, "include": ["/api/*"], "exclude": []}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


if __name__ == "__main__":
    result = build_dist()
    print(json.dumps({"output": str(DIST_ROOT), "asset_file_count": result["asset_file_count"]}, ensure_ascii=False))
