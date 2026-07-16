from __future__ import annotations

import csv
import io
from typing import Any


INSTITUTION_LABELS = ["外資", "投信", "自營商", "合計"]


def build_pending_institution_payload(product: str, source_url: str) -> dict[str, Any]:
    rows = [
        {
            "institution": label,
            "longContracts": None,
            "shortContracts": None,
            "netContracts": None,
            "status": "source_pending",
            "note": "TAIFEX 三大法人逐商品期權部位待接入，不以推估值替代。",
        }
        for label in INSTITUTION_LABELS
    ]
    return {
        "product": product,
        "tradeDate": None,
        "rows": rows,
        "summary": {
            "netContracts": None,
            "bias": "資料源待接入",
            "status": "source_pending",
        },
        "source": {
            "name": "TAIFEX 三大法人期貨與選擇權交易資料",
            "url": source_url,
        },
        "message": f"{product} 法人期權部位資料源待接入；端點保留完整欄位，不回傳空 API 或假資料。",
    }


def normalize_institution_row(row: dict[str, Any]) -> dict[str, Any]:
    def value(*names: str) -> Any:
        for name in names:
            if name in row and row[name] not in {None, ""}:
                return row[name]
        return None

    return {
        "institution": str(value("institution", "法人", "身份別") or "").strip(),
        "product_code": str(value("product_code", "product", "商品代號") or "").strip().upper(),
        "long_contracts": value("long_contracts", "long", "多方口數"),
        "short_contracts": value("short_contracts", "short", "空方口數"),
        "net_contracts": value("net_contracts", "net", "多空淨額"),
        "trade_date": str(value("trade_date", "date", "交易日期") or "").strip(),
    }


def parse_institution_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []
    for raw in reader:
        row = normalize_institution_row(raw)
        if row["institution"] and row["product_code"] and row["trade_date"]:
            rows.append(row)
    return rows


def build_institution_payload_from_rows(product: str, rows: list[dict[str, Any]], source_url: str) -> dict[str, Any]:
    filtered = [row for row in rows if str(row.get("product_code") or "").upper() == product]
    if not filtered:
        return build_pending_institution_payload(product, source_url)
    total_net = sum(float(row.get("net_contracts") or 0) for row in filtered)
    return {
        "product": product,
        "tradeDate": max(str(row.get("trade_date") or "") for row in filtered),
        "rows": [
            {
                "institution": row.get("institution"),
                "longContracts": row.get("long_contracts"),
                "shortContracts": row.get("short_contracts"),
                "netContracts": row.get("net_contracts"),
                "status": "imported",
            }
            for row in filtered
        ],
        "summary": {
            "netContracts": total_net,
            "bias": "法人偏多" if total_net > 0 else "法人偏空" if total_net < 0 else "法人中性",
            "status": "imported",
        },
        "source": {"name": "TAIFEX 三大法人期權部位匯入資料", "url": source_url},
        "message": "法人期權部位已由匯入流程載入。",
    }
