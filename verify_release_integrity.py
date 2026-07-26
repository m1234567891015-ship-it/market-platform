from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from derivatives_store import DerivativesStore


DB_PATH = Path("derivatives-platform.sqlite3")

MOCK_DATA_KEYS = ("mock_option_chain", "mock_ai_report", "test_institutional_position")


def db_snapshot(path: Path) -> dict[str, int]:
    # `with sqlite3.connect(...) as connection` only manages the transaction
    # (commit/rollback) -- it does NOT close the connection. Left open, the
    # scratch-db file in the clean-package branch below stays locked and its
    # enclosing TemporaryDirectory cannot be deleted on Windows, so close
    # explicitly.
    connection = sqlite3.connect(path)
    try:
        queries = {
            "option_chain_snapshot_total": "SELECT COUNT(*) FROM option_chain_snapshot",
            "ai_analysis_report_total": "SELECT COUNT(*) FROM ai_analysis_report",
            "institutional_position_total": "SELECT COUNT(*) FROM institutional_position",
            "mock_option_chain": """
                SELECT COUNT(*) FROM option_chain_snapshot
                WHERE put_call_ratio = 1.1 AND max_pain = 21000.0
                   OR payload_json LIKE '%Research only.%'
                   OR payload_json LIKE '%PCR is balanced.%'
                   OR payload_json LIKE '%Range bound%'
            """,
            "mock_ai_report": """
                SELECT COUNT(*) FROM ai_analysis_report
                WHERE summary LIKE '%PCR is balanced.%'
                   OR summary LIKE '%Research only.%'
                   OR summary LIKE '%WinError%'
                   OR bias = 'Range bound'
            """,
            "test_institutional_position": """
                SELECT COUNT(*) FROM institutional_position
                WHERE product_code LIKE '%TEST%' OR institution LIKE '%TEST%'
            """,
        }
        return {name: connection.execute(sql).fetchone()[0] for name, sql in queries.items()}
    finally:
        connection.close()


def run_test_suite() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "unittest", "test_derivatives_platform.py"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> None:
    # test_derivatives_platform.py isolates itself onto its own tempfile-backed
    # DerivativesStore (see setUpClass) and never touches DB_PATH either way,
    # so before/after comparison logic is identical in both modes below --
    # the only difference is *what* gets snapshotted.
    side_effect_db_removed: bool | None = None
    if DB_PATH.exists():
        mode = "existing_database"
        db_source = "pre_existing"
        unverified_in_this_mode: list[str] = []
        before = db_snapshot(DB_PATH)
        result = run_test_suite()
        after = db_snapshot(DB_PATH)
    else:
        # DB_PATH is absent (clean delivery package, e.g. build_portable_package.py's
        # zip before first run, or an older package that shipped none at all).
        # sqlite3.connect() would otherwise silently create an empty file with no
        # tables here, and the queries above would then crash with
        # "OperationalError: no such table". Build a schema-only DB to prove the
        # query mechanics are sound, but do it in a tempdir -- never write anything
        # to DB_PATH itself, so a clean-unzipped package never gains a file that
        # wasn't part of its original manifest.
        mode = "clean_package"
        db_source = "freshly_initialized_in_tempdir_for_clean_package_check (deleted after check)"
        unverified_in_this_mode = [
            f"real {DB_PATH} row counts (file does not exist in this package)",
            "before/after diff against an actual deployed/populated database",
        ]
        with tempfile.TemporaryDirectory(prefix="verify-release-integrity-") as tmp_name:
            scratch_db = Path(tmp_name) / DB_PATH.name
            DerivativesStore(scratch_db).initialize()
            before = db_snapshot(scratch_db)
            result = run_test_suite()
            after = db_snapshot(scratch_db)

        # app.py:117 runs `DERIVATIVES_STORE.initialize()` unconditionally at
        # module import time, using app.py's own directory as the default DB
        # location (see TD-23) -- importing app.py inside the test-suite
        # subprocess above therefore creates a schema-only DB_PATH as an
        # unavoidable side effect, before test_derivatives_platform.py's
        # setUpClass ever gets a chance to monkeypatch it away. Not something
        # this script causes or can prevent; clean it up and say so plainly
        # rather than pretend it can never happen.
        side_effect_db_removed = False
        if DB_PATH.exists():
            DB_PATH.unlink()
            side_effect_db_removed = True

    report = {
        "mode": mode,
        "db_source": db_source,
        "unverified_in_this_mode": unverified_in_this_mode,
        "side_effect_db_removed": side_effect_db_removed,
        "test_returncode": result.returncode,
        "before": before,
        "after": after,
        "db_unchanged": before == after,
        "mock_free": all(after[key] == 0 for key in MOCK_DATA_KEYS),
        "test_output": result.stdout + result.stderr,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if result.returncode != 0 or not report["db_unchanged"] or not report["mock_free"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

