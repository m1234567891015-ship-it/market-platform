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
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


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
                trade_time = str(item.get("date") or updated_at)
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
                    oi_date = str(item.get("date") or updated_at)
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

    def record_ai_report(self, target: str, analysis: dict[str, Any], created_at: str) -> None:
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
