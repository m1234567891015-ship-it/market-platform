"""Portable persistence for the futures and options information platform.

The application currently runs without a managed PostgreSQL service.  This
SQLite implementation keeps the schema, snapshot boundaries, and indexes
defined by the project documents while remaining portable.  Set
DERIVATIVES_DB_PATH to move the file to a managed volume; the repository API
is intentionally independent from Flask and can later be replaced by a
PostgreSQL adapter.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
import sqlite3
import threading
from datetime import datetime
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from derivatives.execution_costs import CONTRACT_VERSION as P0B_COST_VERSION, calculate_futures_cost, resolve_cost_snapshot


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS market_index (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    last_price REAL,
    change_value REAL,
    change_pct REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS futures_product (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    contract_month TEXT,
    tick_size REAL,
    exchange_name TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS futures_contract (
    contract_key TEXT PRIMARY KEY,
    product_symbol TEXT NOT NULL,
    contract_month TEXT,
    expiry_date TEXT,
    FOREIGN KEY(product_symbol) REFERENCES futures_product(symbol)
);

CREATE TABLE IF NOT EXISTS futures_quote (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    last_price REAL,
    bid REAL,
    ask REAL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    volume REAL,
    open_interest REAL,
    trade_time TEXT NOT NULL,
    source TEXT,
    FOREIGN KEY(symbol) REFERENCES futures_product(symbol)
);

CREATE TABLE IF NOT EXISTS options_product (
    symbol TEXT PRIMARY KEY,
    underlying TEXT NOT NULL,
    name TEXT,
    exchange_name TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS options_contract (
    contract_key TEXT PRIMARY KEY,
    product_symbol TEXT NOT NULL,
    underlying TEXT NOT NULL,
    expiry_date TEXT,
    strike_price REAL NOT NULL,
    option_type TEXT NOT NULL,
    FOREIGN KEY(product_symbol) REFERENCES options_product(symbol)
);

CREATE TABLE IF NOT EXISTS options_quote (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_key TEXT NOT NULL,
    last_price REAL,
    bid REAL,
    ask REAL,
    volume REAL,
    open_interest REAL,
    implied_volatility REAL,
    trade_time TEXT NOT NULL,
    FOREIGN KEY(contract_key) REFERENCES options_contract(contract_key)
);

CREATE TABLE IF NOT EXISTS option_chain_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    underlying TEXT NOT NULL,
    expiry_date TEXT,
    trade_date TEXT,
    put_call_ratio REAL,
    volume_put_call_ratio REAL,
    max_pain REAL,
    spot_price REAL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS open_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    market_type TEXT NOT NULL,
    long_oi REAL,
    short_oi REAL,
    net_oi REAL,
    trade_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS institutional_position (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    institution TEXT NOT NULL,
    product_code TEXT NOT NULL,
    long_contracts REAL,
    short_contracts REAL,
    net_contracts REAL,
    trade_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT,
    url TEXT,
    summary TEXT,
    published_at TEXT,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_analysis_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_symbol TEXT NOT NULL,
    bias TEXT,
    support_level REAL,
    resistance_level REAL,
    risk_level TEXT,
    summary TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_ledger (
    decision_id TEXT PRIMARY KEY,
    target_symbol TEXT NOT NULL,
    decision_time TEXT NOT NULL,
    market_as_of TEXT,
    instrument TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    input_snapshot_hash TEXT NOT NULL,
    input_snapshot_json TEXT NOT NULL,
    decision_output_json TEXT NOT NULL,
    evidence_score REAL,
    data_quality_score REAL,
    reference_price REAL,
    execution_cost_assumptions_json TEXT NOT NULL,
    source_metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_outcome (
    decision_id TEXT NOT NULL,
    evaluation_horizon TEXT NOT NULL,
    evaluation_time TEXT NOT NULL,
    status TEXT NOT NULL,
    gross_return REAL,
    execution_cost REAL,
    net_return REAL,
    mfe REAL,
    mae REAL,
    target_hit TEXT NOT NULL,
    stop_hit TEXT NOT NULL,
    unavailable_reason TEXT,
    data_quality_status TEXT NOT NULL,
    market_observations_json TEXT NOT NULL,
    cost_adjusted_result_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(decision_id, evaluation_horizon),
    FOREIGN KEY(decision_id) REFERENCES decision_ledger(decision_id)
);

CREATE TABLE IF NOT EXISTS system_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    module TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_futures_quote_symbol_trade_time
    ON futures_quote(symbol, trade_time);
CREATE INDEX IF NOT EXISTS idx_options_contract_lookup
    ON options_contract(underlying, expiry_date, strike_price, option_type);
CREATE INDEX IF NOT EXISTS idx_options_quote_contract_trade_time
    ON options_quote(contract_key, trade_time);
CREATE INDEX IF NOT EXISTS idx_open_interest_symbol_trade_date
    ON open_interest(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_institutional_position_product_trade_date
    ON institutional_position(product_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_market_news_published_category
    ON market_news(published_at, category);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_target_created
    ON ai_analysis_report(target_symbol, created_at);
CREATE INDEX IF NOT EXISTS idx_decision_ledger_market_created
    ON decision_ledger(market_as_of, created_at, decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_outcome_evaluated
    ON decision_outcome(evaluation_time, decision_id, evaluation_horizon);
"""


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in {"", "--", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class DerivativesStore:
    OPTION_SNAPSHOT_RETENTION = 180
    AI_REPORT_RETENTION = 180
    FUTURES_QUOTE_RETENTION = 360
    OPTIONS_QUOTE_RETENTION = 360
    OPEN_INTEREST_RETENTION = 360
    INSTITUTIONAL_POSITION_RETENTION = 500
    MARKET_NEWS_RETENTION = 240
    SYSTEM_LOG_RETENTION = 500
    _PRUNE_ALLOWLIST = {
        ("option_chain_snapshot", "underlying"),
        ("ai_analysis_report", "target_symbol"),
        ("futures_quote", "symbol"),
        ("options_quote", "contract_key"),
        ("open_interest", "symbol"),
        ("institutional_position", "product_code"),
        ("market_news", "category"),
        ("system_log", "module"),
    }

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._initialized = False
        self._initialize_lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._initialize_lock:
            if self._initialized:
                return
            with self._connection() as connection:
                connection.executescript(SCHEMA_SQL)
                columns = {row[1] for row in connection.execute("PRAGMA table_info(decision_outcome)")}
                if "cost_adjusted_result_json" not in columns:
                    connection.execute("ALTER TABLE decision_outcome ADD COLUMN cost_adjusted_result_json TEXT NOT NULL DEFAULT '{}' ")
            self._initialized = True

    @staticmethod
    def _canonical_option_chain(data: dict[str, Any]) -> dict[str, Any]:
        """Remove fetch-runtime markers before comparing/persisting a snapshot."""
        canonical = dict(data)
        for key in ("cached", "stale", "staleAt"):
            canonical.pop(key, None)
        return canonical

    @classmethod
    def _same_json(cls, left: str | None, right: dict[str, Any]) -> bool:
        if not left:
            return False
        try:
            stored = json.loads(left)
            if not isinstance(stored, dict):
                return False
            return cls._canonical_option_chain(stored) == cls._canonical_option_chain(right)
        except (TypeError, json.JSONDecodeError):
            return False

    @staticmethod
    def _prune_to_limit(connection: sqlite3.Connection, table: str, where_field: str, value: str, limit: int) -> None:
        if (table, where_field) not in DerivativesStore._PRUNE_ALLOWLIST:
            raise ValueError(f"Unsupported prune target: {table}.{where_field}")
        connection.execute(
            f"""
            DELETE FROM {table}
            WHERE {where_field} = ?
              AND id NOT IN (
                  SELECT id FROM {table}
                  WHERE {where_field} = ?
                  ORDER BY id DESC
                  LIMIT ?
              )
            """,
            (value, value, limit),
        )

    def log(self, level: str, module: str, message: str, created_at: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO system_log(level, module, message, created_at) VALUES (?, ?, ?, ?)",
                (level, module, message, created_at),
            )
            self._prune_to_limit(connection, "system_log", "module", module, self.SYSTEM_LOG_RETENTION)

    def record_futures_payload(self, payload: dict[str, Any]) -> None:
        updated_at = str(payload.get("updatedAt") or "")
        source = str(payload.get("source") or "")
        items = payload.get("items") or []
        touched_symbols: set[str] = set()
        with self._connection() as connection:
            for item in items:
                if item.get("error") or item.get("status") in {"source_pending", "source_unavailable"}:
                    continue
                symbol = str(item.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                touched_symbols.add(symbol)
                connection.execute(
                    """
                    INSERT INTO futures_product(symbol, name, category, contract_month, tick_size, exchange_name, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        name=excluded.name, category=excluded.category, exchange_name=excluded.exchange_name,
                        updated_at=excluded.updated_at
                    """,
                    (
                        symbol,
                        str(item.get("name") or symbol),
                        str(item.get("type") or item.get("group") or ""),
                        str(item.get("contractMonth") or ""),
                        _number(item.get("tickSize")),
                        str(item.get("exchange") or ""),
                        updated_at,
                    ),
                )
                market_date_value = item.get("marketAsOf") if "marketAsOf" in item else item.get("date")
                market_date = str(market_date_value or "").strip()
                try:
                    market_date = datetime.strptime(market_date, "%Y-%m-%d").strftime("%Y-%m-%d")
                except ValueError:
                    continue
                trade_time = market_date
                quote_values = (
                    symbol, _number(item.get("close")), _number(item.get("bid")), _number(item.get("ask")),
                    _number(item.get("open")), _number(item.get("high")), _number(item.get("low")),
                    _number(item.get("volume")), _number(item.get("openInterest")), trade_time, source,
                )
                if quote_values[1] is None and quote_values[8] is None:
                    continue
                existing_quote = connection.execute(
                    """
                    SELECT last_price, bid, ask, open_price, high_price, low_price, volume, open_interest
                    FROM futures_quote
                    WHERE symbol = ? AND trade_time = ? AND source = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (symbol, trade_time, source),
                ).fetchone()
                if existing_quote != quote_values[1:9]:
                    connection.execute(
                        """
                        INSERT INTO futures_quote(symbol, last_price, bid, ask, open_price, high_price, low_price, volume, open_interest, trade_time, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        quote_values,
                    )
                open_interest = _number(item.get("openInterest"))
                if open_interest is not None:
                    oi_date = market_date
                    existing_oi = connection.execute(
                        """
                        SELECT net_oi FROM open_interest
                        WHERE symbol = ? AND market_type = ? AND trade_date = ?
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (symbol, "futures", oi_date),
                    ).fetchone()
                    if not existing_oi or existing_oi[0] != open_interest:
                        connection.execute(
                            "INSERT INTO open_interest(symbol, market_type, net_oi, trade_date) VALUES (?, ?, ?, ?)",
                            (symbol, "futures", open_interest, oi_date),
                        )
            for symbol in touched_symbols:
                self._prune_to_limit(connection, "futures_quote", "symbol", symbol, self.FUTURES_QUOTE_RETENTION)
                self._prune_to_limit(connection, "open_interest", "symbol", symbol, self.OPEN_INTEREST_RETENTION)

    def record_option_chain(self, data: dict[str, Any], created_at: str) -> None:
        if data.get("error"):
            return
        underlying = str(data.get("underlying") or "TXO").upper()
        expiry = str(data.get("selectedExpiry") or "")
        summary = data.get("summary") or {}
        trade_date = str(data.get("tradeDate") or created_at)
        source = data.get("source") or {}
        canonical_data = self._canonical_option_chain(data)
        payload_json = json.dumps(canonical_data, ensure_ascii=False, sort_keys=True)
        touched_contracts: set[str] = set()
        with self._connection() as connection:
            # Serialize the read/check/write sequence across app processes.
            # The existing identity intentionally permits conflicting payloads,
            # so a database-wide UNIQUE constraint cannot replace this guard.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO options_product(symbol, underlying, name, exchange_name, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET name=excluded.name, exchange_name=excluded.exchange_name, updated_at=excluded.updated_at
                """,
                (underlying, underlying, str(data.get("name") or underlying), str(data.get("exchange") or "TAIFEX"), created_at),
            )
            existing_snapshots = connection.execute(
                """
                SELECT payload_json
                FROM option_chain_snapshot
                WHERE underlying = ? AND expiry_date = ? AND trade_date = ?
                ORDER BY id DESC
                """,
                (underlying, expiry, trade_date),
            ).fetchall()
            if any(self._same_json(row[0], canonical_data) for row in existing_snapshots):
                return
            connection.execute(
                """
                INSERT INTO option_chain_snapshot(underlying, expiry_date, trade_date, put_call_ratio, volume_put_call_ratio, max_pain, spot_price, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    underlying, expiry, trade_date, _number(summary.get("putCallRatio")),
                    _number(summary.get("volumePutCallRatio")), _number(summary.get("maxPain")),
                    _number((data.get("spot") or {}).get("value")), payload_json, created_at,
                ),
            )
            for row in data.get("chain") or []:
                strike = _number(row.get("strike"))
                if strike is None:
                    continue
                for option_type, quote in (("CALL", row.get("call") or {}), ("PUT", row.get("put") or {})):
                    contract_key = f"{underlying}:{expiry}:{strike:g}:{option_type}"
                    touched_contracts.add(contract_key)
                    connection.execute(
                        """
                        INSERT INTO options_contract(contract_key, product_symbol, underlying, expiry_date, strike_price, option_type)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(contract_key) DO NOTHING
                        """,
                        (contract_key, underlying, underlying, expiry, strike, option_type),
                    )
                    quote_values = (
                        contract_key, _number(quote.get("last") or quote.get("settlement")), _number(quote.get("bid")),
                        _number(quote.get("ask")), _number(quote.get("volume")), _number(quote.get("openInterest")),
                        _number(quote.get("impliedVolatility")), trade_date,
                    )
                    existing_quotes = connection.execute(
                        """
                        SELECT last_price, bid, ask, volume, open_interest, implied_volatility
                        FROM options_quote
                        WHERE contract_key = ? AND trade_time = ?
                        """,
                        (contract_key, trade_date),
                    ).fetchall()
                    if not any(existing_quote == quote_values[1:7] for existing_quote in existing_quotes):
                        connection.execute(
                            """
                            INSERT INTO options_quote(contract_key, last_price, bid, ask, volume, open_interest, implied_volatility, trade_time)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            quote_values,
                        )
            self._prune_to_limit(
                connection,
                "option_chain_snapshot",
                "underlying",
                underlying,
                self.OPTION_SNAPSHOT_RETENTION,
            )
            self._prune_to_limit(connection, "open_interest", "symbol", underlying, self.OPEN_INTEREST_RETENTION)
            for contract_key in touched_contracts:
                self._prune_to_limit(
                    connection,
                    "options_quote",
                    "contract_key",
                    contract_key,
                    self.OPTIONS_QUOTE_RETENTION,
                )

    def record_ai_report(
        self,
        target: str,
        analysis: dict[str, Any],
        created_at: str,
        input_snapshot: dict[str, Any] | None = None,
        reference_price: Any = None,
    ) -> None:
        if input_snapshot is not None and analysis.get("decision_id"):
            self.record_decision({
                "decision_id": analysis.get("decision_id"),
                "symbol": analysis.get("symbol") or target,
                "instrument": target,
                "decision_time": analysis.get("decision_time") or created_at,
                "market_as_of": analysis.get("market_as_of"),
                "strategy_id": analysis.get("strategy_version"),
                "strategy_version": analysis.get("strategy_version"),
                "model_version": analysis.get("model_version"),
                "input_snapshot_hash": analysis.get("input_snapshot_hash"),
                "input_snapshot": input_snapshot,
                "decision_output": analysis.get("decision_output"),
                "executionDirection": analysis.get("executionDirection"),
                "executionDirectionStatus": analysis.get("executionDirectionStatus"),
                "executionDirectionReason": analysis.get("executionDirectionReason"),
                "executionDirectionContractVersion": analysis.get("executionDirectionContractVersion"),
                "evidence_score": analysis.get("evidence_score", analysis.get("evidenceScore")),
                "data_quality_score": analysis.get("data_quality_score", analysis.get("dataQualityScore")),
                "reference_price": reference_price,
                "execution_cost_assumptions": {"status": "UNAVAILABLE", "reason": "NO_DECISION_TIME_COST_CONTRACT"},
                "source_updated_at": analysis.get("source_updated_at"),
                "confidence_method": analysis.get("confidence_method"),
                "data_quality_status": analysis.get("dataQualityStatus"),
                "created_at": created_at,
            })
        summary = "；".join(str(item) for item in (analysis.get("reasons") or [])[:5])
        with self._connection() as connection:
            latest = connection.execute(
                """
                SELECT bias, support_level, resistance_level, risk_level, summary
                FROM ai_analysis_report
                WHERE target_symbol = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (target,),
            ).fetchone()
            values = (
                str(analysis.get("bias") or ""),
                _number(analysis.get("supportLevel")),
                _number(analysis.get("resistanceLevel")),
                str(analysis.get("riskLevel") or ""),
                summary,
            )
            if latest == values:
                return
            connection.execute(
                """
                INSERT INTO ai_analysis_report(target_symbol, bias, support_level, resistance_level, risk_level, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target, str(analysis.get("bias") or ""), _number(analysis.get("supportLevel")),
                    _number(analysis.get("resistanceLevel")), str(analysis.get("riskLevel") or ""),
                    summary, created_at,
                ),
            )
            self._prune_to_limit(
                connection,
                "ai_analysis_report",
                "target_symbol",
                target,
                self.AI_REPORT_RETENTION,
            )

    @staticmethod
    def _ledger_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    def record_decision(self, decision: dict[str, Any]) -> bool:
        """Append an immutable, reconstructable decision snapshot.

        Returns False for an exact replay. Reusing an ID for different content is
        rejected rather than silently replacing the historical decision.
        """
        decision_id = str(decision.get("decision_id") or "").strip()
        snapshot = decision.get("input_snapshot")
        if not decision_id or not isinstance(snapshot, dict):
            raise ValueError("decision_id and input_snapshot are required")
        snapshot_json = self._ledger_json(snapshot)
        snapshot_hash = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        expected_hash = str(decision.get("input_snapshot_hash") or "")
        if not expected_hash or snapshot_hash != expected_hash:
            raise ValueError("input_snapshot_hash does not match the canonical input snapshot")
        output = decision.get("decision_output")
        if not isinstance(output, dict):
            raise ValueError("decision_output must be an object")
        output = dict(output)
        allowed_directions = {"LONG", "SHORT", "NO_POSITION", "UNAVAILABLE"}
        execution_direction = str(decision.get("executionDirection") or "UNAVAILABLE").strip().upper()
        if execution_direction not in allowed_directions:
            raise ValueError("executionDirection must use a canonical P1-D value")
        direction_status = "UNAVAILABLE" if execution_direction == "UNAVAILABLE" else "AVAILABLE"
        default_reasons = {
            "LONG": "EXPLICIT_LONG_DECISION",
            "SHORT": "EXPLICIT_SHORT_DECISION",
            "NO_POSITION": "EXPLICIT_NO_POSITION_DECISION",
            "UNAVAILABLE": "LEGACY_DIRECTION_UNAVAILABLE",
        }
        direction_reason = str(decision.get("executionDirectionReason") or default_reasons[execution_direction]).strip().upper()
        allowed_reasons = {
            "EXPLICIT_LONG_DECISION", "EXPLICIT_SHORT_DECISION", "EXPLICIT_NO_POSITION_DECISION",
            "INSUFFICIENT_DECISION_DATA", "ANALYSIS_ONLY", "NO_EXECUTABLE_POSITION_CONTRACT",
            "INVALID_EXECUTION_DIRECTION", "LEGACY_DIRECTION_UNAVAILABLE",
        }
        if direction_reason not in allowed_reasons:
            raise ValueError("executionDirectionReason must use a canonical P1-D reason")
        required_reason = {
            "LONG": "EXPLICIT_LONG_DECISION",
            "SHORT": "EXPLICIT_SHORT_DECISION",
            "NO_POSITION": "EXPLICIT_NO_POSITION_DECISION",
        }.get(execution_direction)
        if required_reason and direction_reason != required_reason:
            raise ValueError("executionDirectionReason conflicts with executionDirection")
        direction_contract_version = str(
            decision.get("executionDirectionContractVersion") or "P1D_DIRECTION_V1"
        ).strip()
        if output.get("executionDirection") not in {None, execution_direction}:
            raise ValueError("decision_output executionDirection conflicts with the authoritative contract")
        output.update({
            "executionDirection": execution_direction,
            "executionDirectionStatus": direction_status,
            "executionDirectionReason": direction_reason,
            "executionDirectionContractVersion": direction_contract_version,
        })
        quantity_value = decision.get("executionQuantity", output.get("executionQuantity"))
        quantity = _number(quantity_value)
        if quantity_value is not None and (quantity is None or not math.isfinite(quantity) or quantity <= 0):
            raise ValueError("executionQuantity must be positive and finite")
        if output.get("executionQuantity") is not None and output.get("executionQuantity") != quantity_value:
            raise ValueError("decision_output executionQuantity conflicts with the authoritative contract")
        output["executionQuantity"] = quantity
        symbol = str(decision.get("symbol") or "").strip()
        instrument = str(decision.get("instrument") or symbol).strip()
        model_version = str(decision.get("model_version") or "").strip()
        strategy_version = str(decision.get("strategy_version") or "").strip()
        strategy_id = str(decision.get("strategy_id") or strategy_version).strip()
        decision_time = str(decision.get("decision_time") or "").strip()
        if not all((symbol, instrument, model_version, strategy_version, strategy_id, decision_time)):
            raise ValueError("decision provenance fields are incomplete")

        # Keep only explicitly supplied, non-secret provenance. Confidence is
        # deliberately excluded because this strategy is not calibrated.
        source_metadata = {
            key: decision.get(key)
            for key in ("source_updated_at", "confidence_method", "data_quality_status")
            if decision.get(key) is not None
        }
        supplied_cost = decision.get("execution_cost_assumptions")
        cost_assumptions = resolve_cost_snapshot(
            instrument, supplied_cost if isinstance(supplied_cost, dict) else None
        )
        output["executionCostContractVersion"] = cost_assumptions.get("contractVersion")
        record = (
            decision_id,
            symbol,
            decision_time,
            str(decision.get("market_as_of") or "") or None,
            instrument,
            strategy_id,
            model_version,
            strategy_version,
            snapshot_hash,
            snapshot_json,
            self._ledger_json(output),
            _number(decision.get("evidence_score")),
            _number(decision.get("data_quality_score")),
            _number(decision.get("reference_price")),
            self._ledger_json(cost_assumptions),
            self._ledger_json(source_metadata),
            str(decision.get("created_at") or decision_time),
        )
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM decision_ledger WHERE decision_id = ?", (decision_id,)
            ).fetchone()
            if existing is not None:
                existing_record = tuple(existing)
                # decision_id is intentionally stable across replay timestamps;
                # preserve the first accepted timestamp when the logical
                # decision payload is otherwise identical.
                if existing_record[:2] + existing_record[3:16] != record[:2] + record[3:16]:
                    raise ValueError("conflicting payload for existing decision_id")
                return False
            connection.execute(
                """INSERT INTO decision_ledger(
                    decision_id, target_symbol, decision_time, market_as_of, instrument,
                    strategy_id, model_version, strategy_version, input_snapshot_hash,
                    input_snapshot_json, decision_output_json, evidence_score, data_quality_score,
                    reference_price, execution_cost_assumptions_json, source_metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                record,
            )
        return True

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM decision_ledger WHERE decision_id = ?", (str(decision_id),)
            ).fetchone()
            columns = [column[0] for column in connection.execute("SELECT * FROM decision_ledger LIMIT 0").description]
        if row is None:
            return None
        result = dict(zip(columns, row))
        for field in ("input_snapshot_json", "decision_output_json", "execution_cost_assumptions_json", "source_metadata_json"):
            result[field.removesuffix("_json")] = json.loads(result.pop(field))
        output = result["decision_output"]
        direction = str(output.get("executionDirection") or "UNAVAILABLE").upper()
        if direction not in {"LONG", "SHORT", "NO_POSITION", "UNAVAILABLE"}:
            direction = "UNAVAILABLE"
        result["executionDirection"] = direction
        result["executionDirectionStatus"] = "UNAVAILABLE" if direction == "UNAVAILABLE" else "AVAILABLE"
        default_direction_reasons = {
            "LONG": "EXPLICIT_LONG_DECISION",
            "SHORT": "EXPLICIT_SHORT_DECISION",
            "NO_POSITION": "EXPLICIT_NO_POSITION_DECISION",
            "UNAVAILABLE": "LEGACY_DIRECTION_UNAVAILABLE",
        }
        result["executionDirectionReason"] = str(
            output.get("executionDirectionReason") or default_direction_reasons[direction]
        )
        result["executionDirectionContractVersion"] = str(output.get("executionDirectionContractVersion") or "LEGACY")
        return result

    def list_decisions(self, target_symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 1000))
        query = "SELECT decision_id FROM decision_ledger"
        params: tuple[Any, ...] = ()
        if target_symbol:
            query += " WHERE target_symbol = ?"
            params = (str(target_symbol),)
        query += " ORDER BY COALESCE(market_as_of, ''), decision_time, decision_id LIMIT ?"
        params += (bounded_limit,)
        with self._connection() as connection:
            identifiers = connection.execute(query, params).fetchall()
        return [item for (decision_id,) in identifiers if (item := self.get_decision(decision_id)) is not None]

    def record_decision_outcome(self, decision_id: str, evaluation_horizon: str, result: dict[str, Any]) -> None:
        horizon = str(evaluation_horizon or "").strip().upper()
        if not re.fullmatch(r"T\+[1-9][0-9]*", horizon):
            raise ValueError("evaluation_horizon must use the canonical T+N form")
        evaluation_time = str(result.get("evaluation_time") or "").strip()
        status = str(result.get("status") or "").strip().upper()
        if not evaluation_time or status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE", "NOT_APPLICABLE"}:
            raise ValueError("evaluation_time and a valid outcome status are required")
        target_hit = str(result.get("target_hit") or "NOT_APPLICABLE").upper()
        stop_hit = str(result.get("stop_hit") or "NOT_APPLICABLE").upper()
        valid_hits = {"HIT", "NOT_HIT", "NOT_APPLICABLE", "UNAVAILABLE"}
        if target_hit not in valid_hits or stop_hit not in valid_hits:
            raise ValueError("target_hit and stop_hit must use explicit ledger states")
        observations = result.get("market_observations") or []
        if not isinstance(observations, list):
            raise ValueError("market_observations must be a list")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM decision_ledger WHERE decision_id = ?", (decision_id,)).fetchone() is None:
                raise ValueError("outcome decision_id does not exist")
            connection.execute(
                """INSERT INTO decision_outcome(
                    decision_id, evaluation_horizon, evaluation_time, status, gross_return,
                    execution_cost, net_return, mfe, mae, target_hit, stop_hit,
                    unavailable_reason, data_quality_status, market_observations_json
                    , cost_adjusted_result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id, evaluation_horizon) DO UPDATE SET
                    evaluation_time=excluded.evaluation_time, status=excluded.status,
                    gross_return=excluded.gross_return, execution_cost=excluded.execution_cost,
                    net_return=excluded.net_return, mfe=excluded.mfe, mae=excluded.mae,
                    target_hit=excluded.target_hit, stop_hit=excluded.stop_hit,
                    unavailable_reason=excluded.unavailable_reason,
                    data_quality_status=excluded.data_quality_status,
                    market_observations_json=excluded.market_observations_json,
                    cost_adjusted_result_json=excluded.cost_adjusted_result_json""",
                (
                    decision_id, horizon, evaluation_time, status,
                    _number(result.get("gross_return")), _number(result.get("execution_cost")),
                    _number(result.get("net_return")), _number(result.get("mfe")), _number(result.get("mae")),
                    target_hit, stop_hit, result.get("unavailable_reason"),
                    str(result.get("data_quality_status") or status), self._ledger_json(observations),
                    self._ledger_json(result.get("costAdjustedResult") or {}),
                ),
            )

    def evaluate_decision_outcome(
        self,
        decision_id: str,
        evaluation_horizon: str,
        evaluation_time: str,
        market_observations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Evaluate an explicit T+N market-session window without look-ahead.

        Gross return, directional excursions, and cost-adjusted returns use
        only the immutable direction, quantity, and cost snapshot.
        """
        horizon = str(evaluation_horizon or "").strip().upper()
        match = re.fullmatch(r"T\+([1-9][0-9]*)", horizon)
        if not match:
            raise ValueError("evaluation_horizon must use the canonical T+N form")
        decision = self.get_decision(decision_id)
        if decision is None:
            raise ValueError("decision_id does not exist")
        try:
            as_of = datetime.strptime(str(decision.get("market_as_of") or ""), "%Y-%m-%d").date()
            evaluation_at = datetime.fromisoformat(str(evaluation_time))
            decision_at = datetime.fromisoformat(str(decision["decision_time"]))
            if evaluation_at.tzinfo is None or decision_at.tzinfo is None or evaluation_at < decision_at:
                raise ValueError("timestamps must be timezone-aware and evaluation must follow decision")
            evaluation_date = evaluation_at.date()
        except ValueError:
            result = {
                "evaluation_time": evaluation_time,
                "status": "UNAVAILABLE",
                "unavailable_reason": "INVALID_MARKET_CHRONOLOGY",
                "data_quality_status": "UNAVAILABLE",
                "market_observations": [],
            }
            self.record_decision_outcome(decision_id, horizon, result)
            return result

        execution_direction = decision["executionDirection"]
        if execution_direction == "NO_POSITION":
            result = {
                "evaluation_time": evaluation_time,
                "status": "NOT_APPLICABLE",
                "gross_return": None,
                "execution_cost": None,
                "net_return": None,
                "mfe": None,
                "mae": None,
                "target_hit": "NOT_APPLICABLE",
                "stop_hit": "NOT_APPLICABLE",
                "unavailable_reason": None,
                "data_quality_status": "AVAILABLE",
                "market_observations": [],
                "costAdjustedResult": {"status": "NOT_APPLICABLE", "reason": "NO_POSITION"},
            }
            self.record_decision_outcome(decision_id, horizon, result)
            return result
        if execution_direction == "UNAVAILABLE":
            result = {
                "evaluation_time": evaluation_time,
                "status": "UNAVAILABLE",
                "unavailable_reason": decision["executionDirectionReason"],
                "data_quality_status": "UNAVAILABLE",
                "market_observations": [],
                "costAdjustedResult": {"status": "UNAVAILABLE", "reason": decision["executionDirectionReason"]},
            }
            self.record_decision_outcome(decision_id, horizon, result)
            return result

        normalized: list[tuple[Any, dict[str, Any]]] = []
        seen_dates: set[Any] = set()
        for row in market_observations or []:
            try:
                market_date = datetime.strptime(str(row.get("market_as_of") or row.get("date") or ""), "%Y-%m-%d").date()
            except (TypeError, ValueError):
                continue
            if market_date <= as_of or market_date > evaluation_date:
                continue
            try:
                observed_at = datetime.fromisoformat(str(row.get("observed_at") or ""))
                if observed_at.tzinfo is None or observed_at > evaluation_at:
                    continue
            except ValueError:
                continue
            if market_date in seen_dates:
                result = {
                    "evaluation_time": evaluation_time,
                    "status": "UNAVAILABLE",
                    "unavailable_reason": "DUPLICATE_MARKET_DATE",
                    "data_quality_status": "UNAVAILABLE",
                    "market_observations": [],
                }
                self.record_decision_outcome(decision_id, horizon, result)
                return result
            seen_dates.add(market_date)
            normalized.append((market_date, row))
        normalized.sort(key=lambda pair: pair[0])
        required_bars = int(match.group(1))
        window = normalized[:required_bars]
        if len(window) < required_bars:
            result = {
                "evaluation_time": evaluation_time,
                "status": "UNAVAILABLE",
                "unavailable_reason": "MISSING_FUTURE_MARKET_PRICE",
                "data_quality_status": "UNAVAILABLE",
                "market_observations": [row for _, row in window],
            }
            self.record_decision_outcome(decision_id, horizon, result)
            return result

        output = decision["decision_output"]
        direction = execution_direction
        reference_price = _number(decision.get("reference_price"))
        if direction not in {"LONG", "SHORT"} or reference_price is None or reference_price <= 0:
            result = {
                "evaluation_time": evaluation_time,
                "status": "UNAVAILABLE",
                "unavailable_reason": "REFERENCE_PRICE_UNAVAILABLE",
                "data_quality_status": "UNAVAILABLE",
                "market_observations": [row for _, row in window],
            }
            self.record_decision_outcome(decision_id, horizon, result)
            return result

        bars: list[dict[str, float]] = []
        for _, row in window:
            values = {key: _number(row.get(key)) for key in ("high", "low", "close")}
            if any(value is None or value <= 0 for value in values.values()):
                result = {
                    "evaluation_time": evaluation_time,
                    "status": "UNAVAILABLE",
                    "unavailable_reason": "INVALID_FUTURE_OHLC",
                    "data_quality_status": "UNAVAILABLE",
                    "market_observations": [item for _, item in window],
                }
                self.record_decision_outcome(decision_id, horizon, result)
                return result
            bars.append({key: float(value) for key, value in values.items() if value is not None})

        if direction == "LONG":
            favorable = [bar["high"] / reference_price - 1 for bar in bars]
            adverse = [bar["low"] / reference_price - 1 for bar in bars]
            gross_return = bars[-1]["close"] / reference_price - 1
            target_price = _number(output.get("target_price", output.get("targetPrice")))
            stop_price = _number(output.get("stop_price", output.get("stopPrice")))
            target_hit = "NOT_APPLICABLE" if target_price is None else "HIT" if any(bar["high"] >= target_price for bar in bars) else "NOT_HIT"
            stop_hit = "NOT_APPLICABLE" if stop_price is None else "HIT" if any(bar["low"] <= stop_price for bar in bars) else "NOT_HIT"
        else:
            favorable = [reference_price / bar["low"] - 1 for bar in bars]
            adverse = [reference_price / bar["high"] - 1 for bar in bars]
            gross_return = (reference_price - bars[-1]["close"]) / reference_price
            target_price = _number(output.get("target_price", output.get("targetPrice")))
            stop_price = _number(output.get("stop_price", output.get("stopPrice")))
            target_hit = "NOT_APPLICABLE" if target_price is None else "HIT" if any(bar["low"] <= target_price for bar in bars) else "NOT_HIT"
            stop_hit = "NOT_APPLICABLE" if stop_price is None else "HIT" if any(bar["high"] >= stop_price for bar in bars) else "NOT_HIT"
        cost_snapshot = decision.get("execution_cost_assumptions")
        quantity = decision.get("decision_output", {}).get("executionQuantity")
        cost_result = calculate_futures_cost(cost_snapshot, direction, reference_price, bars[-1]["close"], quantity)
        if cost_result.get("supported"):
            status = "AVAILABLE"
            unavailable_reason = None
            execution_cost = cost_result["totalCost"]
            net_return = cost_result["costAdjustedReturnPct"] / 100
            adjusted = {
                "status": "AVAILABLE", "contractVersion": P0B_COST_VERSION,
                "grossPnl": cost_result["grossPnl"], "commissionCost": cost_result["commissionCost"],
                "taxCost": cost_result["taxCost"], "slippageCost": cost_result["slippageCost"],
                "otherCost": 0, "totalCost": cost_result["totalCost"], "netPnl": cost_result["netPnl"],
                "normalizedCostPct": cost_result["normalizedCostPct"],
                "grossDirectionalReturnPct": cost_result["grossDirectionalReturnPct"],
                "costAdjustedReturnPct": cost_result["costAdjustedReturnPct"], "currency": cost_result["currency"],
            }
        else:
            status = "PARTIAL"
            execution_cost = None
            net_return = None
            if not isinstance(cost_snapshot, dict) or cost_snapshot.get("contractVersion") != P0B_COST_VERSION:
                unavailable_reason = "LEGACY_DECISION_MISSING_P0B_COST_CONTRACT"
            else:
                unavailable_reason = cost_result.get("reason") or cost_snapshot.get("reason") or "INVALID_DECISION_TIME_COST_CONTRACT"
            adjusted = {"status": "UNAVAILABLE", "reason": unavailable_reason}
        result = {
            "evaluation_time": evaluation_time,
            "status": status,
            "gross_return": gross_return,
            "execution_cost": execution_cost,
            "net_return": net_return,
            "mfe": max(favorable),
            "mae": min(adverse),
            "target_hit": target_hit,
            "stop_hit": stop_hit,
            "unavailable_reason": unavailable_reason,
            "data_quality_status": status,
            "market_observations": [row for _, row in window],
            "costAdjustedResult": adjusted,
        }
        self.record_decision_outcome(decision_id, horizon, result)
        return result

    def get_decision_outcome(self, decision_id: str, evaluation_horizon: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT decision_id, evaluation_horizon, evaluation_time, status, gross_return,
                          execution_cost, net_return, mfe, mae, target_hit, stop_hit,
                          unavailable_reason, data_quality_status, market_observations_json,
                          cost_adjusted_result_json
                   FROM decision_outcome WHERE decision_id = ? AND evaluation_horizon = ?""",
                (str(decision_id), str(evaluation_horizon).upper()),
            ).fetchone()
        if row is None:
            return None
        fields = (
            "decision_id", "evaluation_horizon", "evaluation_time", "status", "gross_return",
            "execution_cost", "net_return", "mfe", "mae", "target_hit", "stop_hit",
            "unavailable_reason", "data_quality_status", "market_observations", "cost_adjusted_result",
        )
        result = dict(zip(fields, row))
        result["market_observations"] = json.loads(result["market_observations"])
        result["cost_adjusted_result"] = json.loads(result["cost_adjusted_result"])
        return result

    def list_decision_outcomes(self, decision_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            horizons = connection.execute(
                "SELECT evaluation_horizon FROM decision_outcome WHERE decision_id = ? ORDER BY evaluation_horizon",
                (str(decision_id),),
            ).fetchall()
        return [item for (horizon,) in horizons if (item := self.get_decision_outcome(decision_id, horizon)) is not None]

    def record_institutional_positions(self, rows: Iterable[dict[str, Any]]) -> int:
        inserted = 0
        touched_products: set[str] = set()
        with self._connection() as connection:
            for row in rows:
                institution = str(row.get("institution") or "").strip()
                product_code = str(row.get("product_code") or row.get("product") or "").strip().upper()
                trade_date = str(row.get("trade_date") or row.get("date") or "").strip()
                if not institution or not product_code or not trade_date:
                    continue
                touched_products.add(product_code)
                connection.execute(
                    """
                    INSERT INTO institutional_position(
                        institution, product_code, long_contracts, short_contracts, net_contracts, trade_date
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        institution,
                        product_code,
                        _number(row.get("long_contracts")),
                        _number(row.get("short_contracts")),
                        _number(row.get("net_contracts")),
                        trade_date,
                    ),
                )
                inserted += 1
            for product_code in touched_products:
                self._prune_to_limit(
                    connection,
                    "institutional_position",
                    "product_code",
                    product_code,
                    self.INSTITUTIONAL_POSITION_RETENTION,
                )
        return inserted

    def institutional_positions(self, product_code: str, limit: int = 40) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT institution, product_code, long_contracts, short_contracts, net_contracts, trade_date
                FROM institutional_position
                WHERE product_code = ?
                ORDER BY trade_date DESC, id DESC
                LIMIT ?
                """,
                (product_code.upper(), max(1, min(int(limit), 200))),
            ).fetchall()
        return [
            {
                "institution": row[0],
                "product_code": row[1],
                "long_contracts": row[2],
                "short_contracts": row[3],
                "net_contracts": row[4],
                "trade_date": row[5],
            }
            for row in rows
        ]

    def option_pcr_history(self, underlying: str = "TXO", limit: int = 60) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT trade_date, expiry_date, put_call_ratio, volume_put_call_ratio, max_pain, spot_price
                FROM option_chain_snapshot
                WHERE underlying = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (underlying, max(1, min(int(limit), 240))),
            ).fetchall()
        history = [
            {
                "tradeDate": row[0],
                "expiry": row[1],
                "putCallRatio": row[2],
                "volumePutCallRatio": row[3],
                "maxPain": row[4],
                "spot": row[5],
            }
            for row in reversed(rows)
        ]
        return history

    def record_news(self, category: str, items: Iterable[dict[str, Any]]) -> None:
        with self._connection() as connection:
            # Prevent equivalent concurrent GET refreshes from inserting the
            # same bounded-cache event more than once.
            connection.execute("BEGIN IMMEDIATE")
            for item in items:
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                values = (
                    title,
                    str(item.get("source") or ""),
                    str(item.get("link") or item.get("url") or ""),
                    str(item.get("summary") or ""),
                    str(item.get("publishedAt") or ""),
                    category,
                )
                existing = connection.execute(
                    """
                    SELECT 1
                    FROM market_news
                    WHERE title = ? AND source = ? AND url = ? AND summary = ?
                      AND published_at = ? AND category = ?
                    LIMIT 1
                    """,
                    values,
                ).fetchone()
                if existing:
                    continue
                connection.execute(
                    "INSERT INTO market_news(title, source, url, summary, published_at, category) VALUES (?, ?, ?, ?, ?, ?)",
                    values,
                )
            self._prune_to_limit(connection, "market_news", "category", category, self.MARKET_NEWS_RETENTION)
