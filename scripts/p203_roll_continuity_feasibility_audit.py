"""Read-only feasibility audit for frozen P2-03 Research V2 roll rules.

This diagnostic consumes only the already frozen V1R1 selected series and
V2 implementation. It does not fit or persist forecasts and writes only to a
new, isolated .tmp output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import p203_v2_historical_development as v2

EXPECTED_SERIES = "90ca05e0472b09ba3f67e641dae16f8ed9ad310fc87d056e7fd2c3e0baa1c48f"
EXPECTED_TRACE = "a1f5bfd250f1cb94f09a7324f5314686fc29e298cde649a26dd4f817e11e251a"
DEFAULT_OUTPUT = ROOT / ".tmp" / "p203-roll-continuity-feasibility-audit"


def _runs(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runs: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    start = 0
    for index in range(1, len(rows) + 1):
        if index < len(rows) and rows[index]["contractMonth"] == rows[start]["contractMonth"]:
            continue
        run = {
            "contractMonth": rows[start]["contractMonth"],
            "startIndex": start,
            "endIndex": index - 1,
            "startDate": rows[start]["time"],
            "endDate": rows[index - 1]["time"],
            "sessionCount": index - start,
        }
        runs.append(run)
        if index < len(rows):
            boundaries.append({
                "oldContractMonth": rows[index - 1]["contractMonth"],
                "newContractMonth": rows[index]["contractMonth"],
                "oldContractLastDate": rows[index - 1]["time"],
                "newContractFirstDate": rows[index]["time"],
                "sessionsSincePreviousTransition": index - start,
                "featureWindowInvalidationDates": [],
                "targetBoundaryInvalidationDates": [],
                "volumeAtBoundary": {
                    "oldContract": rows[index - 1]["volume"],
                    "newContract": rows[index]["volume"],
                    "selectedContractVolumeRatioNewOverOld": (
                        rows[index]["volume"] / rows[index - 1]["volume"]
                        if rows[index - 1]["volume"] else None
                    ),
                },
            })
        start = index

    for boundary in boundaries:
        new_index = next(i for i, row in enumerate(rows) if row["time"] == boundary["newContractFirstDate"])
        # Determine affected decision dates from the frozen D-20..D+1 rule.
        for index, row in enumerate(rows):
            if index < 20 or index + 1 >= len(rows):
                continue
            if new_index in range(index - 20, index + 1):
                boundary["featureWindowInvalidationDates"].append(row["time"])
            if new_index == index + 1:
                boundary["targetBoundaryInvalidationDates"].append(row["time"])
    return runs, boundaries


def _counterfactual_counts(rows: list[dict[str, Any]], windows: list[int]) -> dict[str, Any]:
    """Diagnostic only: same frozen features/target, relax feature continuity."""
    output: dict[str, Any] = {}
    for window in windows:
        statuses: dict[str, int] = {}
        eligible_dates: list[str] = []
        for index in range(len(rows)):
            if index < 20:
                status = "LOOKBACK_WARMUP_EXCLUDED"
            else:
                features, direction, sign5 = v2.derive_features(rows, index)
                if features is None or direction is None or sign5 is None:
                    status = "FEATURE_INCOMPLETE"
                elif direction == "UNAVAILABLE":
                    status = "DIRECTION_INELIGIBLE"
                elif index + 1 >= len(rows):
                    status = "TARGET_UNAVAILABLE"
                else:
                    current, next_row = rows[index], rows[index + 1]
                    if current["close"] <= 0 or next_row["close"] <= 0:
                        status = "TARGET_UNAVAILABLE"
                    elif current["contractMonth"] != next_row["contractMonth"]:
                        status = "TARGET_ROLL_INELIGIBLE"
                    elif any(rows[pos]["contractMonth"] != current["contractMonth"]
                             for pos in range(max(0, index - window), index + 1)):
                        status = "FEATURE_WINDOW_ROLL_INELIGIBLE"
                    else:
                        aligned = (1.0 if sign5 > 0 else -1.0) * (next_row["close"] / current["close"] - 1.0)
                        if aligned == 0:
                            status = "FLAT_TARGET_EXCLUDED"
                        else:
                            status = "ELIGIBLE_MATURED_LABEL"
                            eligible_dates.append(current["time"])
            statuses[status] = statuses.get(status, 0) + 1
        output[str(window)] = {
            "featureWindowSessions": window,
            "counts": dict(sorted(statuses.items())),
            "maturedLabelCount": len(eligible_dates),
            "firstEligibleDate": eligible_dates[0] if eligible_dates else None,
            "lastEligibleDate": eligible_dates[-1] if eligible_dates else None,
            "classification": "COUNTERFACTUAL_DIAGNOSTIC_ONLY_NOT_APPROVED_NOT_IMPLEMENTED",
        }
    return output


def build_report() -> dict[str, Any]:
    protocol = v2._verify_effective_protocol()
    rows, inventory = v2._load_selected_series()
    if inventory["selectedSeriesSha256"] != EXPECTED_SERIES:
        raise v2.IntegrityError("selected series hash differs from owner-authorized frozen hash")
    if inventory["selectionTraceSha256"] != EXPECTED_TRACE:
        raise v2.IntegrityError("selection trace hash differs from owner-authorized frozen hash")

    candidates = [v2._candidate_for_index(rows, index) for index in range(len(rows))]
    result = v2.run_development(rows)
    funnel = result["funnel"]
    runs, boundaries = _runs(rows)
    for boundary in boundaries:
        boundary["featureWindowInvalidationCount"] = len(boundary["featureWindowInvalidationDates"])
        boundary["targetBoundaryInvalidationCount"] = len(boundary["targetBoundaryInvalidationDates"])

    run_lengths = [item["sessionCount"] for item in runs]
    roll_excluded = [row for row in candidates if row["status"] == "ROLL_INELIGIBLE"]
    exclusive = {}
    for row in candidates:
        exclusive[row["status"]] = exclusive.get(row["status"], 0) + 1
    overlap = {
        "featureRollOnly": sum(bool(row.get("featureRollIneligible")) and not bool(row.get("targetRollIneligible")) for row in roll_excluded),
        "targetRollOnly": sum(bool(row.get("targetRollIneligible")) and not bool(row.get("featureRollIneligible")) for row in roll_excluded),
        "featureAndTargetRoll": sum(bool(row.get("featureRollIneligible")) and bool(row.get("targetRollIneligible")) for row in roll_excluded),
    }
    counterfactual = _counterfactual_counts(rows, [5, 10, 15, 20])
    counterfactual["targetOnly"] = _counterfactual_counts(rows, [0])["0"]
    counterfactual["ignoreContractSwitching"] = {
        "maturedLabelCount": sum(row["status"] in {"ELIGIBLE_MATURED_LABEL", "ROLL_INELIGIBLE"} for row in candidates),
        "classification": "COUNTERFACTUAL_DIAGNOSTIC_ONLY_NOT_APPROVED_NOT_IMPLEMENTED",
        "warning": "Includes cross-contract feature/target comparisons and is not leakage-safe continuity evidence.",
    }

    session_rows = []
    for row in candidates:
        session_rows.append({
            "marketDate": row["decisionDate"],
            "selectedContractMonth": row["selectedContractMonth"],
            "status": row["status"],
            "featureRollIneligible": row.get("featureRollIneligible", False),
            "targetRollIneligible": row.get("targetRollIneligible", False),
            "targetDate": row.get("targetDate"),
            "exclusionReason": row.get("exclusionReason"),
        })

    report = {
        "auditType": "P2_03_HISTORICAL_ROLL_CONTINUITY_FEASIBILITY_READ_ONLY",
        "classification": "RESEARCH_DIAGNOSTIC_ONLY_NOT_AUTHORITATIVE_NEW_EVIDENCE",
        "protocolHashes": protocol["hashes"],
        "effectiveProtocolIdentity": protocol["identity"].get("effectiveIdentitySha256") or protocol["identity"].get("sha256"),
        "frozenInputs": {
            "selectedSeriesSha256": inventory["selectedSeriesSha256"],
            "selectionTraceSha256": inventory["selectionTraceSha256"],
            "selectedSessionCount": len(rows),
            "dateRange": {"start": rows[0]["time"], "end": rows[-1]["time"]},
            "reconstructedFrom24SavedRawWindows": True,
            "selectionRule": inventory["selectionRule"],
        },
        "frozenRule": {
            "rule": v2.ROLL_RULE,
            "minimumPriorMaturedLabels": v2.MIN_TRAINING_SAMPLES,
            "target": v2.TARGET_ID,
            "antiLeakage": "Training decision dates and T+1 target dates must both precede forecast date.",
            "publicationTimingVintageRevisionHistory": "NOT PROVEN",
        },
        "funnel": {
            "exclusiveStatuses": dict(sorted(exclusive.items())),
            "frozenSummary": funnel,
            "overlappingRollExclusions": overlap,
        },
        "contracts": {
            "runCount": len(runs),
            "runLength": {
                "min": min(run_lengths), "max": max(run_lengths),
                "median": statistics.median(run_lengths),
                "mean": round(statistics.mean(run_lengths), 6),
                "counts": {
                    "lt5": sum(value < 5 for value in run_lengths),
                    "lt10": sum(value < 10 for value in run_lengths),
                    "lt20": sum(value < 20 for value in run_lengths),
                    "ge20": sum(value >= 20 for value in run_lengths),
                    "ge21": sum(value >= 21 for value in run_lengths),
                    "ge22": sum(value >= 22 for value in run_lengths),
                },
            },
            "transitions": boundaries,
        },
        "trainingCapacity": {
            "maturedEligibleLabels": funnel["maturedEligibleLabels"],
            "requiredPriorLabels": v2.MIN_TRAINING_SAMPLES,
            "maximumForecastsUnderFrozenRule": len(result["forecasts"]),
            "maximumOosPairsUnderFrozenRule": len(result["pairs"]),
            "bothClassesRequired": True,
            "forecastGenerated": funnel["forecastGenerated"],
            "validDevelopmentOosPairs": funnel["validDevelopmentOosPairs"],
            "classification": "NO_FROZEN_RULE_FORECAST_CAPACITY_IN_THIS_FIXED_WINDOW",
        },
        "counterfactualDiagnostics": counterfactual,
        "constraintClassification": {
            "sameContractFeatureAndTargetContinuity": "FROZEN_RESEARCH_DESIGN; not amended by this audit",
            "strictlyPriorDecisionAndMaturedTargetChronology": "REQUIRED_ANTI_LEAKAGE",
            "historicalProviderPublicationVintageAndRevisionAvailability": "REQUIRED_POINT_IN_TIME_EVIDENCE_NOT_AVAILABLE; historical limitation remains NOT PROVEN",
            "19LabelsBelow30PriorLabels": "FROZEN_MINIMUM_TRAINING_RULE; not an implementation override",
            "counterfactualRelaxedRollWindows": "DIAGNOSTIC_ONLY; no proposal promoted to approved change",
        },
    }
    report["runLengthTable"] = runs
    report["sessionCountCheck"] = len(session_rows) == len(rows) == 441
    report["allSessionRows"] = session_rows
    return report


def _write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite audit artifacts: {output_dir}")
    output_dir.mkdir(parents=True)
    payloads = {
        "report.json": (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "sessions.csv": _csv_bytes(report["allSessionRows"]),
        "contract_runs.csv": _csv_bytes(report["runLengthTable"]),
        "roll_boundaries.json": (json.dumps(report["contracts"]["transitions"], ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    manifest = {}
    for name, data in payloads.items():
        (output_dir / name).write_bytes(data)
        manifest[name] = hashlib.sha256(data).hexdigest()
    (output_dir / "manifest.json").write_text(json.dumps({"artifactSha256": manifest}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    output = __import__("io").StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report()
    _write_outputs(report, args.output_dir)
    print(json.dumps({
        "status": "AUDIT_COMPLETE",
        "outputDir": str(args.output_dir),
        "funnel": report["funnel"]["frozenSummary"],
        "runLength": report["contracts"]["runLength"],
        "transitionCount": len(report["contracts"]["transitions"]),
        "trainingCapacity": report["trainingCapacity"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
