"""P2-17..P2-20 artifact audit, separation, and reproducibility checks."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath

from release_proof.build_p2_worktree_package import PACKAGE_MANIFEST, build, sha256
from regression.p2_release_provenance import source_identity


ROOT = Path(__file__).resolve().parent.parent
FINAL_PACKAGE = ROOT / "release_proof" / "market-platform-worktree-p2-20-deterministic.zip"
ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".7z"}
FORBIDDEN_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def current_final_package() -> Path:
    candidates = sorted(ROOT.glob("release_proof/market-platform-worktree-p2-20-deterministic*.zip"))
    for candidate in candidates:
        try:
            with zipfile.ZipFile(candidate) as archive:
                manifest = json.loads(archive.read(PACKAGE_MANIFEST).decode("utf-8"))
            if manifest.get("source_identity") == source_identity():
                return candidate
        except (KeyError, OSError, ValueError, zipfile.BadZipFile):
            continue
    return FINAL_PACKAGE


class P2ArtifactHygieneTests(unittest.TestCase):
    def test_existing_archive_audit_has_no_nested_or_unsafe_entries(self) -> None:
        archives = sorted(path for path in ROOT.rglob("*") if path.is_file() and path.suffix.lower() in ARCHIVE_SUFFIXES)
        self.assertIn(ROOT / "market-platform-portable-optimized.zip", archives)
        for archive_path in archives:
            if archive_path.suffix.lower() != ".zip":
                continue
            with zipfile.ZipFile(archive_path) as archive:
                names = archive.namelist()
                self.assertTrue(all(safe_member(name) for name in names), archive_path)
                nested = [name for name in names if PurePosixPath(name).suffix.lower() in ARCHIVE_SUFFIXES]
                self.assertEqual(nested, [], archive_path)

    def test_final_package_separation_and_manifest(self) -> None:
        package = current_final_package()
        self.assertTrue(package.is_file())
        with zipfile.ZipFile(package) as archive:
            names = archive.namelist()
            self.assertEqual(names.count(PACKAGE_MANIFEST), 1)
            self.assertTrue(all(safe_member(name) for name in names))
            self.assertTrue(all(not any(part in FORBIDDEN_PARTS for part in PurePosixPath(name).parts) for name in names))
            self.assertFalse(any(PurePosixPath(name).suffix.lower() in ARCHIVE_SUFFIXES for name in names if name != PACKAGE_MANIFEST))
            self.assertFalse(any(name.startswith("release_proof/") for name in names))
            self.assertNotIn("twse-cache.json", names)
            manifest = json.loads(archive.read(PACKAGE_MANIFEST).decode("utf-8"))
            self.assertEqual(manifest["package_type"], "WORKTREE PACKAGE")
            self.assertEqual(manifest["release_status"], "NOT CLEAN COMMITTED RELEASE")
            self.assertEqual(manifest["source_identity"], source_identity())
            self.assertEqual(manifest["payload_file_count"], len(manifest["files"]))
            self.assertTrue(manifest["source_identity"]["worktree_dirty"])
            entries = {item.filename: item for item in archive.infolist()}
            for record in manifest["files"]:
                self.assertIn(record["path"], entries)
                self.assertEqual(record["bytes"], entries[record["path"]].file_size)
                self.assertEqual(record["sha256"], hashlib.sha256(archive.read(record["path"])).hexdigest())

    def test_two_independent_builds_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p2-20-repro-") as temp_name:
            first = Path(temp_name) / "first.zip"
            second = Path(temp_name) / "second.zip"
            build(first)
            build(second)
            self.assertEqual(sha256(first), sha256(second))


if __name__ == "__main__":
    unittest.main()
