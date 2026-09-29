from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from derivatives.execution_costs import CONTRACTS, calculate_futures_cost, resolve_cost_snapshot


ROOT = Path(__file__).resolve().parents[1]


class P1DP0BCostContractTests(unittest.TestCase):
    def test_python_matches_current_javascript_oracle(self) -> None:
        node = shutil.which("node")
        if not node:
            self.fail("Node.js is required to execute the authoritative P0-B JavaScript parity oracle")
        requests = []
        for symbol in CONTRACTS:
            requests.append({"symbol": symbol, "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 2})
        requests += [
            {"symbol": "TX", "direction": "LONG", "entryPrice": 100, "exitPrice": 110, "quantity": 2},
            {"symbol": "TX", "direction": "SHORT", "entryPrice": 100, "exitPrice": 90, "quantity": 2},
            {"symbol": "TX", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 2, "overrides": {"brokerCommissionPerContract": 0, "slippageTicks": 0}},
            {"symbol": "TX", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 2, "overrides": {"brokerCommissionPerContract": None}},
            {"symbol": "TX", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 2, "overrides": {"slippageTicks": None}},
            {"symbol": "TX", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 2, "overrides": {"multiplier": 50}},
            {"symbol": "TX", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 2, "overrides": {"tickSize": 0.5}},
            {"symbol": "TX", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 2, "overrides": {"currency": "USD"}},
            {"symbol": "TX", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 1},
            {"symbol": "TE", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 1, "overrides": {"slippageTicks": 1}},
            {"symbol": "TE", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 1, "overrides": {"slippageTicks": 2}},
            {"symbol": "TF", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 1, "overrides": {"slippageTicks": 1}},
            {"symbol": "TF", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 1, "overrides": {"slippageTicks": 2}},
            {"symbol": "UNKNOWN", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 1},
            {"symbol": "SOF", "direction": "LONG", "entryPrice": 100, "exitPrice": 101, "quantity": 1},
        ]
        completed = subprocess.run(
            [node, str(ROOT / "regression" / "p1d_p0b_cost_oracle.js")],
            input=json.dumps(requests), text=True, capture_output=True, check=True,
        )
        oracle = json.loads(completed.stdout)
        keys = ("grossPnl", "commissionCost", "taxCost", "slippageCost", "totalEntryCost", "totalExitCost", "totalCost", "netPnl", "normalizedCostPct", "currency", "side")
        for request, expected in zip(requests, oracle):
            snapshot = resolve_cost_snapshot(request["symbol"], request.get("overrides"))
            actual = calculate_futures_cost(snapshot, request["direction"], request["entryPrice"], request["exitPrice"], request["quantity"])
            expected_cost = expected["cost"]
            if expected_cost.get("supported"):
                self.assertTrue(actual.get("supported"), request)
                for key in keys:
                    self.assertAlmostEqual(actual[key], expected_cost[key], delta=1e-9, msg=f"{request} {key}") if isinstance(actual[key], (int, float)) else self.assertEqual(actual[key], expected_cost[key], f"{request} {key}")
                self.assertAlmostEqual(actual["costAdjustedReturnPct"], expected["netReturnPct"], delta=1e-9, msg=f"{request} calculateNetReturn parity")
            else:
                self.assertFalse(actual.get("supported"), request)
                self.assertEqual(actual.get("reason"), expected_cost.get("reason"), request)

    def test_model_a_tx_hand_check_and_reconciliations(self) -> None:
        result = calculate_futures_cost(resolve_cost_snapshot("TX"), "LONG", 100, 110, 2)
        self.assertEqual((result["grossPnl"], result["commissionCost"], result["slippageCost"]), (4000, 180, 800))
        self.assertAlmostEqual(result["taxCost"], 1.68)
        self.assertAlmostEqual(result["totalCost"], 981.68)
        self.assertAlmostEqual(result["netPnl"], 3018.32)
        self.assertEqual(result["totalCost"], result["commissionCost"] + result["taxCost"] + result["slippageCost"])
        self.assertEqual(result["netPnl"], result["grossPnl"] - result["totalCost"])

    def test_explicit_zero_and_fail_closed_required_inputs(self) -> None:
        zero = resolve_cost_snapshot("TX", {"commission": 0, "slippageTicks": 0})
        self.assertEqual(calculate_futures_cost(zero, "LONG", 100, 101, 1)["totalCost"], 0.804)
        self.assertEqual(resolve_cost_snapshot("TX", {"commission": None})["reason"], "MISSING_OR_INVALID_BROKER_COMMISSION_CONFIGURATION")
        self.assertEqual(resolve_cost_snapshot("TX", {"slippageTicks": None})["reason"], "MISSING_OR_INVALID_SLIPPAGE_CONFIGURATION")
        self.assertEqual(resolve_cost_snapshot("TX", {"tickSize": 0})["reason"], "FUTURES_CONTRACT_SPECIFICATION_CONFLICT")


if __name__ == "__main__":
    unittest.main()
