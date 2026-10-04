from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from scripts import p203_tx_contract_roll_audit as audit

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "p203"
V1_FIXTURE_DIR = FIXTURE_ROOT / "historical-v1"
HISTORICAL_INPUT = FIXTURE_ROOT / "historical-asof" / "taifex_tx_daily_normalized.json"


@contextmanager
def _isolated_logical_ledger():
    """Create the frozen one-decision/no-outcome logical state in a temp DB."""
    with tempfile.TemporaryDirectory(prefix="p203-tx-roll-ledger-") as directory:
        db_path = Path(directory) / "prospective-ledger.sqlite3"
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("CREATE TABLE decision_ledger (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE decision_outcome (id INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO decision_ledger DEFAULT VALUES")
            connection.commit()
        finally:
            connection.close()
        yield db_path


def _fixture_inputs():
    rows = []
    for index in range(8):
        month = "202501" if index < 5 else "202502"
        close = 20000.0 + index * 10
        rows.append({
            "time": f"2025-01-{index + 1:02d}",
            "contractMonth": month,
            "close": close,
            "volume": 1000 + index,
            "openInterest": 50000 + index * 100,
        })
    feature_rows = []
    for index in range(2, len(rows)):
        feature_rows.append({
            "marketDate": rows[index]["time"],
            "momentum_5": "0.01",
            "range_pct_1": "0.005",
            "open_interest_change_1": "0.002",
            "researchDirection": "RESEARCH_LONG",
        })
    pairs = [
        {
            "forecastDate": rows[2]["time"], "targetDate": rows[3]["time"],
            "researchDirection": "RESEARCH_LONG", "decisionAlignedReturn": "0.001", "probability": "0.55",
        },
        {
            "forecastDate": rows[4]["time"], "targetDate": rows[5]["time"],
            "researchDirection": "RESEARCH_LONG", "decisionAlignedReturn": "0.002", "probability": "0.56",
        },
        {
            "forecastDate": rows[5]["time"], "targetDate": rows[6]["time"],
            "researchDirection": "RESEARCH_LONG", "decisionAlignedReturn": "0.003", "probability": "0.57",
        },
    ]
    return {
        "rows": rows,
        "inputHash": "fixture-input-hash",
        "contractHash": "fixture-contract-hash",
        "contractDocumentHash": "fixture-contract-document-hash",
        "v1Hashes": {},
        "featureRows": feature_rows,
        "forecasts": [],
        "pairs": pairs,
        "trainingTrace": [],
    }


class TxContractRollAuditTests(unittest.TestCase):
    def test_roll_transition_and_cross_contract_features_are_detected(self):
        outputs = audit.analyze(_fixture_inputs())
        report = __import__("json").loads(outputs["roll_integrity_report.json"])
        self.assertEqual(1, len(report["rollBoundaries"]))
        self.assertEqual("2025-01-06", report["rollBoundaries"][0]["transitionDate"])
        self.assertEqual(3, report["featureExposure"]["momentum5CrossContractCount"])
        self.assertEqual(1, report["featureExposure"]["openInterestChange1CrossContractCount"])
        self.assertFalse(report["featureExposure"]["rangePct1DirectCrossContractDependency"])

    def test_pairs_distinguish_clean_features_and_roll_target_exposure(self):
        outputs = audit.analyze(_fixture_inputs())
        report = __import__("json").loads(outputs["roll_integrity_report.json"])
        self.assertEqual(1, report["oosPairExposure"]["cleanPairCount"])
        self.assertEqual(1, report["oosPairExposure"]["targetRollAffectedCount"])
        self.assertEqual(1, report["oosPairExposure"]["featureRollAffectedCount"])
        rows = list(__import__("csv").DictReader(__import__("io").StringIO(outputs["oos_pair_roll_exposure.csv"].decode())))
        self.assertEqual("CLEAN_PAIR", rows[0]["primaryClassification"])
        self.assertEqual("ROLL_BOUNDARY_TARGET_DATE", rows[1]["primaryClassification"])
        self.assertEqual("ROLL_BOUNDARY_FORECAST_DATE", rows[2]["primaryClassification"])

    def test_training_sets_report_feature_and_target_roll_exposure_separately(self):
        inputs = _fixture_inputs()
        inputs["forecasts"] = [{"forecastDate": inputs["rows"][7]["time"], "trainingSampleCount": 4}]
        inputs["trainingTrace"] = [{
            "forecastDate": inputs["rows"][7]["time"],
            "trainingPositiveCount": 4,
            "trainingNegativeCount": 0,
            "trainingStartTargetDate": inputs["rows"][3]["time"],
            "trainingEndTargetDate": inputs["rows"][6]["time"],
        }]
        outputs = audit.analyze(inputs)
        exposure = __import__("json").loads(outputs["training_roll_exposure.json"])
        item = exposure["byForecast"][0]
        self.assertEqual(4, item["trainingSampleCount"])
        self.assertEqual(1, item["featureRollAffectedTrainingLabels"])
        self.assertEqual(1, item["targetRollAffectedTrainingLabels"])
        self.assertEqual(2, item["anyRollAffectedTrainingLabels"])

    def test_frozen_fixtures_and_isolated_database_remain_unchanged(self):
        before_artifacts = {name: hashlib.sha256((V1_FIXTURE_DIR / name).read_bytes()).hexdigest() for name in audit.EXPECTED_V1_SHA256}
        with _isolated_logical_ledger() as db_path:
            before_db = audit._db_snapshot(db_path)
            inputs = audit.load_inputs(input_path=HISTORICAL_INPUT, v1_dir=V1_FIXTURE_DIR)
            first = audit.analyze(inputs)
            second = audit.analyze(inputs)
            after_artifacts = {name: hashlib.sha256((V1_FIXTURE_DIR / name).read_bytes()).hexdigest() for name in audit.EXPECTED_V1_SHA256}
            after_db = audit._db_snapshot(db_path)
        self.assertEqual(audit.EXPECTED_V1_SHA256, before_artifacts)
        self.assertEqual(before_artifacts, after_artifacts)
        self.assertEqual(before_db, after_db)
        self.assertEqual(1, before_db["decisionCount"])
        self.assertEqual(0, before_db["outcomeCount"])
        self.assertEqual(first, second)
        report = __import__("json").loads(first["roll_integrity_report.json"])
        self.assertEqual(audit.EXPECTED_INPUT_SHA256, report["dataset"]["sha256"])
        self.assertEqual("BLOCKED", report["productionP2_03"])
        self.assertFalse(report["probabilityLabelAllowed"])


if __name__ == "__main__":
    unittest.main()
