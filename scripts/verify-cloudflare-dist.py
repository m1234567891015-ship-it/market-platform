"""Verify the generated Cloudflare Static Assets directory and its boundaries."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

_BUILDER_PATH = Path(__file__).with_name("build-cloudflare-static.py")
_BUILDER_SPEC = importlib.util.spec_from_file_location("build_cloudflare_static", _BUILDER_PATH)
assert _BUILDER_SPEC and _BUILDER_SPEC.loader
_BUILDER = importlib.util.module_from_spec(_BUILDER_SPEC)
_BUILDER_SPEC.loader.exec_module(_BUILDER)
DIST_ROOT = _BUILDER.DIST_ROOT
MANIFEST_NAME = _BUILDER.MANIFEST_NAME
from market_config import PAGE_ROUTES

FORBIDDEN_NAMES = {".git", "node_modules", "__pycache__", "reports", "backups"}
FORBIDDEN_SUFFIXES = (".sqlite3", ".db", ".har", ".log", ".bak")
FORBIDDEN_TEXT = ("taiwan-market-pulse.onrender.com", "DATABASE_URL", "DERIVATIVES_DB_PATH")
HTML_REF_RE = re.compile(r"(?:src|href)\s*=\s*[\"']([^\"'#]+)", re.IGNORECASE)
CSS_URL_RE = re.compile(r"url\(\s*[\"']?([^\"')]+)", re.IGNORECASE)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_reference_path(source: Path, reference: str) -> Path | None:
    parsed = urlsplit(reference.strip())
    if parsed.scheme or parsed.netloc or reference.startswith(("//", "data:", "mailto:", "javascript:")):
        return None
    raw = parsed.path
    if not raw:
        return None
    if raw.startswith("/"):
        return DIST_ROOT / raw.lstrip("/")
    return source.parent / raw


def verify_dist(dist_root: Path = DIST_ROOT) -> dict:
    errors: list[str] = []
    if not dist_root.is_dir():
        return {"ok": False, "errors": [f"missing dist directory: {dist_root}"]}
    manifest_path = dist_root / MANIFEST_NAME
    if not manifest_path.is_file():
        return {"ok": False, "errors": [f"missing manifest: {manifest_path}"]}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"invalid manifest: {exc}"]}

    entries = manifest.get("files", [])
    actual_assets = []
    for path in sorted(dist_root.rglob("*")):
        if path.is_file() and path.name not in {MANIFEST_NAME, "_headers"}:
            actual_assets.append(path.relative_to(dist_root).as_posix())
    actual_assets.sort()
    listed_assets = sorted(item.get("path", "") for item in entries)
    if listed_assets != actual_assets:
        errors.append("manifest file list does not match generated assets")
    for item in entries:
        target = dist_root / item.get("path", "")
        if not target.is_file():
            errors.append(f"manifest target is missing: {item.get('path')}")
        elif file_sha256(target) != item.get("sha256"):
            errors.append(f"manifest hash mismatch: {item.get('path')}")
    if manifest.get("asset_file_count") != len(actual_assets):
        errors.append("manifest asset_file_count mismatch")

    expected_pages = sorted({name for name in PAGE_ROUTES.values() if name.endswith(".html")})
    actual_pages = sorted(path.name for path in dist_root.glob("*.html"))
    if actual_pages != expected_pages:
        errors.append(f"expected 21 HTML pages, found {len(actual_pages)}")

    all_files = sorted(path for path in dist_root.rglob("*") if path.is_file())
    for path in all_files:
        relative_parts = set(path.relative_to(dist_root).parts)
        if relative_parts & FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden file in dist: {path.relative_to(dist_root)}")
        if path.suffix.lower() in {".html", ".js", ".css", ".webmanifest", ".json", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in FORBIDDEN_TEXT:
                if marker in text:
                    errors.append(f"forbidden text {marker!r} in {path.relative_to(dist_root)}")
            refs = HTML_REF_RE.findall(text) if path.suffix.lower() == ".html" else CSS_URL_RE.findall(text) if path.suffix.lower() == ".css" else []
            for reference in refs:
                target = local_reference_path(path, reference)
                if target is not None and not target.is_file():
                    errors.append(f"broken local reference {reference!r} in {path.relative_to(dist_root)}")

    headers_path = dist_root / "_headers"
    if not headers_path.is_file():
        errors.append("missing dist/_headers")
    else:
        header_text = headers_path.read_text(encoding="utf-8")
        for marker in ("Content-Security-Policy:", "frame-ancestors 'none'", "X-Frame-Options: DENY", "/api/*", "Cache-Control: no-store"):
            if marker not in header_text:
                errors.append(f"missing required static header marker: {marker}")

    return {
        "ok": not errors,
        "errors": errors,
        "html_page_count": len(actual_pages),
        "asset_file_count": len(actual_assets),
        "dist_file_count": len(all_files),
        "manifest_sha256": file_sha256(manifest_path),
    }


if __name__ == "__main__":
    result = verify_dist()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)
