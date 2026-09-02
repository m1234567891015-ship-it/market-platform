from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


MOCK_SNAPSHOT_PATTERNS = [
    "%Research only.%",
    "%PCR is balanced.%",
    "%Taiwan Index Options%",
    "%Range bound%",
]

MOCK_AI_PATTERNS = [
    "%PCR is balanced.%",
    "%Range bound%",
    "%Research only.%",
    "%WinError%",
    "%urlopen error%",
]


def clean_database(path: Path, vacuum: bool = True) -> dict[str, int]:
    if not path.exists():
        raise FileNotFoundError(path)
    with sqlite3.connect(path) as connection:
        snapshot_deleted = 0
        for pattern in MOCK_SNAPSHOT_PATTERNS:
            cursor = connection.execute(
                "DELETE FROM option_chain_snapshot WHERE payload_json LIKE ?",
                (pattern,),
            )
            snapshot_deleted += cursor.rowcount if cursor.rowcount != -1 else 0

        ai_deleted = 0
        for pattern in MOCK_AI_PATTERNS:
            cursor = connection.execute(
                """
                DELETE FROM ai_analysis_report
                WHERE summary LIKE ? OR bias LIKE ?
                """,
                (pattern, pattern),
            )
            ai_deleted += cursor.rowcount if cursor.rowcount != -1 else 0

        cursor = connection.execute(
            """
            DELETE FROM institutional_position
            WHERE product_code LIKE '%TEST%' OR institution LIKE '%TEST%'
            """
        )
        institutional_deleted = cursor.rowcount if cursor.rowcount != -1 else 0

        connection.commit()
        if vacuum:
            connection.execute("VACUUM")
    return {
        "option_chain_snapshot_deleted": snapshot_deleted,
        "ai_analysis_report_deleted": ai_deleted,
        "institutional_position_deleted": institutional_deleted,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean known mock-test pollution from derivatives SQLite DB.")
    parser.add_argument("--db", default="derivatives-platform.sqlite3", help="SQLite DB path")
    parser.add_argument("--no-vacuum", action="store_true", help="Skip VACUUM after cleanup")
    args = parser.parse_args()
    result = clean_database(Path(args.db), vacuum=not args.no_vacuum)
    print(result)


if __name__ == "__main__":
    main()
