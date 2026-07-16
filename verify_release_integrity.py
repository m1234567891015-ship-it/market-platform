from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


DB_PATH = Path("derivatives-platform.sqlite3")


def db_snapshot(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as connection:
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


def main() -> None:
    before = db_snapshot(DB_PATH)
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "test_derivatives_platform.py"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    after = db_snapshot(DB_PATH)
    report = {
        "test_returncode": result.returncode,
        "before": before,
        "after": after,
        "db_unchanged": before == after,
        "mock_free": all(after[key] == 0 for key in ("mock_option_chain", "mock_ai_report", "test_institutional_position")),
        "test_output": result.stdout + result.stderr,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if result.returncode != 0 or not report["db_unchanged"] or not report["mock_free"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

