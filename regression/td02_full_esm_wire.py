"""TD-02 Phase 3/4: wire the full-site loader into all 21 HTML entries.

The rewrite is deliberately byte-preserving apart from the locked script block
so existing line endings and unrelated working-copy changes remain untouched.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "td02-full-esm-20260901-1"
LOADER = f'<script src="market-pulse-esm-loader.js?v={VERSION}"></script>'.encode()


def wire_page(path: Path) -> bool:
    raw = path.read_bytes()
    replacement = LOADER
    patterns = [
        (
            b'<script src="common-runtime.min.js?v=td18-minify-20260901-1"></script>\r\n'
            b'<script src="route-bundle.min.js?v=td18-minify-20260901-1"></script>\r\n'
            b'<script src="derivatives-status-esm-loader.js?v=td02-remain-02-20260901-1"></script>',
            replacement,
        ),
        (
            b'<script src="common-runtime.min.js?v=td18-minify-20260901-1"></script>\r\n'
            b'<script src="route-bundle.min.js?v=td18-minify-20260901-1"></script>',
            replacement,
        ),
        (
            b'<script src="common-runtime.min.js?v=td18-minify-20260901-1"></script>\n'
            b'<script src="route-bundle.min.js?v=td18-minify-20260901-1"></script>\n'
            b'<script src="derivatives-status-esm-loader.js?v=td02-remain-02-20260901-1"></script>',
            replacement,
        ),
        (
            b'<script src="common-runtime.min.js?v=td18-minify-20260901-1"></script>\n'
            b'<script src="route-bundle.min.js?v=td18-minify-20260901-1"></script>',
            replacement,
        ),
    ]
    matches = 0
    for old, new in patterns:
        count = raw.count(old)
        if count:
            raw = raw.replace(old, new)
            matches += count
    if matches > 1:
        raise RuntimeError(f"{path.name}: expected one script block, found {matches}")
    if matches:
        path.write_bytes(raw)
        return True
    return False


def main() -> None:
    pages = sorted(ROOT.glob("*.html"))
    if len(pages) != 21:
        raise RuntimeError(f"expected 21 HTML pages, found {len(pages)}")
    changed = [path.name for path in pages if wire_page(path)]
    remaining = []
    for path in pages:
        raw = path.read_bytes()
        if b"common-runtime.min.js?v=td18-minify-20260901-1" in raw or b"derivatives-status-esm-loader.js" in raw:
            remaining.append(path.name)
    if remaining:
        raise RuntimeError("legacy production script wiring remains: " + ", ".join(remaining))
    print(f"TD02_FULL_ESM_WIRE_OK: pages={len(pages)} changed={len(changed)} version={VERSION}")


if __name__ == "__main__":
    main()
