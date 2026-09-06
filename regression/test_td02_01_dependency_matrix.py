"""Focused TD02-01 reproducibility and documentation-alignment guards."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from regression.td02_01_dependency_matrix import (
    ROOT,
    build_matrix,
    canonical_artifacts,
    locked_inputs,
    render_markdown,
    validate_json_markdown_parity,
)


class TD0201DependencyMatrixTests(unittest.TestCase):
    def copy_fixture(self, destination: Path) -> None:
        (destination / "regression" / "baseline" / "frontend").mkdir(parents=True)
        for html_file in ROOT.glob("*.html"):
            shutil.copy2(html_file, destination / html_file.name)
        for relative in {"regression/td18_shadow_build.lock.json", "regression/baseline/frontend/global_symbols.json"}:
            source = ROOT / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for relative in locked_inputs(ROOT)[0]:
            source = ROOT / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def test_same_input_produces_identical_bytes_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.copy_fixture(root)
            json_one, markdown_one = canonical_artifacts(build_matrix(root))
            json_two, markdown_two = canonical_artifacts(build_matrix(root))
            self.assertEqual(json_one, json_two)
            self.assertEqual(markdown_one, markdown_two)
            self.assertEqual(hashlib.sha256(json_one).digest(), hashlib.sha256(json_two).digest())
            self.assertEqual(hashlib.sha256(markdown_one).digest(), hashlib.sha256(markdown_two).digest())

    def test_identical_inputs_in_different_roots_produce_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root = Path(first) / "one"
            second_root = Path(second) / "nested" / "two"
            self.copy_fixture(first_root)
            self.copy_fixture(second_root)
            first_json, first_markdown = canonical_artifacts(build_matrix(first_root))
            second_json, second_markdown = canonical_artifacts(build_matrix(second_root))
            self.assertEqual(first_json, second_json)
            self.assertEqual(first_markdown, second_markdown)

    def test_cli_is_independent_of_current_working_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "regression" / "td02_01_dependency_matrix.py"), "--check"],
            cwd=ROOT.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("TD02_01_MATRIX_OK", result.stdout)

    def test_legitimate_fixture_input_change_changes_canonical_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.copy_fixture(root)
            before = build_matrix(root)
            before_json, _ = canonical_artifacts(before)
            pwa = root / "pwa.js"
            pwa.write_bytes(pwa.read_bytes() + b"\n// fixture input revision\n")
            after = build_matrix(root)
            after_json, _ = canonical_artifacts(after)
            self.assertNotEqual(before["evidence"]["source_hashes"]["pwa.js"], after["evidence"]["source_hashes"]["pwa.js"])
            self.assertNotEqual(before_json, after_json)

    def test_derived_collections_have_canonical_order(self) -> None:
        matrix = build_matrix()
        self.assertEqual([row["source"] for row in matrix["modules"]], sorted(row["source"] for row in matrix["modules"]))
        self.assertEqual(
            [(row["source"], row["symbol"]) for row in matrix["symbols"]],
            sorted((row["source"], row["symbol"]) for row in matrix["symbols"]),
        )
        self.assertEqual(
            [(row["from_source"], row["to_source"]) for row in matrix["dependency_edges"]],
            sorted((row["from_source"], row["to_source"]) for row in matrix["dependency_edges"]),
        )
        self.assertEqual(
            [page["file"] for page in matrix["pages"]],
            sorted((page["file"] for page in matrix["pages"]), key=str.casefold),
        )

    def test_canonical_contract_excludes_time_and_absolute_paths(self) -> None:
        matrix = build_matrix()
        json_bytes, markdown_bytes = canonical_artifacts(matrix)
        parsed = json.loads(json_bytes)
        self.assertNotIn("generated_at", parsed)
        self.assertTrue(parsed["reproducibility"]["timestamps_excluded"])
        self.assertTrue(parsed["reproducibility"]["absolute_paths_excluded"])
        self.assertNotIn(str(ROOT).encode(), json_bytes)
        self.assertNotIn(str(ROOT).encode(), markdown_bytes)
        self.assertNotIn(b"\r\n", json_bytes)
        self.assertNotIn(b"\r\n", markdown_bytes)
        self.assertEqual(json_bytes.decode("utf-8").encode("utf-8"), json_bytes)
        self.assertEqual(markdown_bytes.decode("utf-8").encode("utf-8"), markdown_bytes)

    def test_json_markdown_parity_guard_rejects_missing_module_row(self) -> None:
        matrix = build_matrix()
        markdown = render_markdown(matrix)
        first_module = next(row for row in matrix["modules"] if row["source"] == "app.js")
        marker = f"| `{first_module['source']}` |"
        tampered = markdown.replace(marker, "| `removed.js` |", 1)
        with self.assertRaisesRegex(ValueError, "JSON/Markdown semantic parity failed"):
            validate_json_markdown_parity(matrix, tampered)

    def test_markdown_states_reproduction_contract(self) -> None:
        markdown = render_markdown(build_matrix())
        for expected in (
            "regression/td02_01_dependency_matrix.py",
            "regression/td18_shadow_build.lock.json",
            "regression/baseline/frontend/global_symbols.json",
            "--write",
            "--check",
            "sha256sum",
            "generation timestamp",
            "absolute machine/temp paths",
            "generated files 不得手動編輯",
        ):
            self.assertIn(expected, markdown)


if __name__ == "__main__":
    unittest.main()
