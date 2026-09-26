"""Build the P2-20 deterministic worktree portable package.

The existing release allowlist remains the source of truth.  This wrapper adds
only a package-local provenance manifest and refuses to overwrite an output.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_MANIFEST = "P2_PACKAGE_PROVENANCE.json"
DEFAULT_OUTPUT = "market-platform-worktree-p2-20-deterministic.zip"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_portable_package import collect_allowlisted_files
from regression.p2_release_provenance import source_identity


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output_path: Path) -> Path:
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {output_path}")
    # The legacy allowlist includes an optional warm-start runtime cache.  It
    # is intentionally excluded here because it is mutable execution data,
    # not source state; portable_check already treats it as optional.
    files = sorted(
        (path for path in collect_allowlisted_files() if path.as_posix() != "twse-cache.json"),
        key=lambda path: path.as_posix(),
    )
    with tempfile.TemporaryDirectory(prefix="market-platform-p2-20-") as tmp_name:
        staging = Path(tmp_name)
        for relative in files:
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)

        inventory = [
            {
                "path": relative.as_posix(),
                "bytes": (staging / relative).stat().st_size,
                "sha256": sha256(staging / relative),
            }
            for relative in files
        ]
        package_manifest = {
            "schema": "p2-portable-package-v1",
            "package_type": "WORKTREE PACKAGE",
            "release_status": "NOT CLEAN COMMITTED RELEASE",
            "source_identity": source_identity(),
            "inclusion_policy": {
                "allowlist_owner": "build_portable_package.collect_allowlisted_files",
                "package_root": ".",
                "manifest_self_hash": "excluded_from_payload_inventory",
                "runtime_cache": "twse-cache.json is excluded as mutable optional warm-start data; live API fallback remains available",
            },
            "payload_file_count": len(inventory),
            "files": inventory,
            "forbidden_patterns": [
                ".git/", ".venv/", "venv/", "node_modules/", "__pycache__/",
                ".pytest_cache/", "logs/", "twse-cache.runtime", ".sqlite3",
                ".zip", ".tar", ".tar.gz", ".7z",
            ],
        }
        manifest_path = staging / PACKAGE_MANIFEST
        manifest_path.write_text(json.dumps(package_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*"), key=lambda item: item.relative_to(staging).as_posix()):
                if not path.is_file():
                    continue
                relative = path.relative_to(staging)
                info = zipfile.ZipInfo(relative.as_posix())
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
    return output_path


if __name__ == "__main__":
    target = ROOT / "release_proof" / DEFAULT_OUTPUT
    result = build(target)
    print(f"{result}: {result.stat().st_size} bytes sha256={sha256(result)}")
