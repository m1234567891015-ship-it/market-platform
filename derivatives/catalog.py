from __future__ import annotations

TAIWAN_FUTURES_V1 = [
    {
        "symbol": "TX",
        "name": "臺股期貨 TX 未平倉",
        "type": "台灣股指期貨",
        "group": "國內指數期貨",
        "taifexCommodity": "TX",
        "v1Status": "connected",
    },
    {
        "symbol": "MTX",
        "name": "小型臺指期貨 MTX 未平倉",
        "type": "台灣股指期貨",
        "group": "國內指數期貨",
        "taifexCommodity": "MTX",
        "v1Status": "connected",
    },
    {
        "symbol": "TMF",
        "name": "微型臺指期貨 TMF 未平倉",
        "type": "台灣股指期貨",
        "group": "國內指數期貨",
        "taifexCommodity": "TMF",
        "v1Status": "connected",
    },
    {
        "symbol": "TE",
        "name": "電子期貨 TE 未平倉",
        "type": "台灣類股期貨",
        "group": "國內類股期貨",
        "taifexCommodity": "TE",
        "v1Status": "connected",
    },
    {
        "symbol": "TF",
        "name": "金融期貨 TF 未平倉",
        "type": "台灣類股期貨",
        "group": "國內類股期貨",
        "taifexCommodity": "TF",
        "v1Status": "connected",
    },
    {
        "symbol": "SOF",
        "name": "櫃買期貨 SOF",
        "type": "台灣櫃買指數期貨",
        "group": "國內指數期貨",
        "taifexCommodity": "SOF",
        "v1Status": "connected",
    },
    {
        "symbol": "STF",
        "name": "股票期貨",
        "type": "股票期貨",
        "group": "國內股票期貨",
        "taifexCommodity": "STF",
        "v1Status": "connected",
        "dataStatus": "TAIFEX OpenAPI 標的清單 + 每日行情彙總已接入。",
    },
    {
        "symbol": "ETF-F",
        "name": "ETF 期貨",
        "type": "ETF期貨",
        "group": "國內ETF期貨",
        "taifexCommodity": "ETF",
        "v1Status": "connected",
        "dataStatus": "TAIFEX OpenAPI 標的清單 + 每日行情彙總已接入。",
    },
]

TAIWAN_OPTIONS_V1 = [
    {
        "symbol": "TXO",
        "name": "臺指選擇權 TXO",
        "type": "台灣指數選擇權",
        "group": "國內指數選擇權",
        "v1Status": "connected",
    },
    {
        "symbol": "STO",
        "name": "股票選擇權",
        "type": "股票選擇權",
        "group": "國內股票選擇權",
        "v1Status": "connected",
        "dataStatus": "TAIFEX OpenAPI 標的清單 + 每日行情彙總已接入。",
    },
    {
        "symbol": "ETO",
        "name": "ETF 選擇權",
        "type": "ETF選擇權",
        "group": "國內ETF選擇權",
        "v1Status": "connected",
        "dataStatus": "TAIFEX OpenAPI 標的清單 + 每日行情彙總已接入。",
    },
]


def apply_taifex_defaults(item: dict, futures_url: str, options_url: str) -> dict:
    output = {
        **item,
        "region": "台灣",
        "market": "台灣",
        "exchange": "TAIFEX",
        "metricLabel": "未平倉量",
    }
    if "期貨" in str(item.get("type", "")):
        output.setdefault("dataSource", "TAIFEX 官方期貨日報")
        output.setdefault("referenceSource", "TAIFEX 期貨契約規格")
        output.setdefault("sourceUrl", futures_url)
        output.setdefault("dataProvider", "taifex_futures_open_interest")
    else:
        output.setdefault("dataSource", "TAIFEX 官方選擇權日報")
        output.setdefault("referenceSource", "TAIFEX 選擇權契約規格")
        output.setdefault("sourceUrl", options_url)
        output.setdefault("dataProvider", "taifex_option_product_status")
    return output


def v1_product_status(futures_items: list[dict], option_items: list[dict]) -> dict:
    def summarize(items: list[dict]) -> dict:
        connected = [item for item in items if item.get("v1Status") == "connected"]
        pending = [item for item in items if item.get("v1Status") != "connected"]
        return {
            "total": len(items),
            "connected": len(connected),
            "sourcePending": len(pending),
            "items": [
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "group": item.get("group"),
                    "status": item.get("v1Status"),
                    "dataStatus": item.get("dataStatus", "TAIFEX 資料已接入"),
                }
                for item in items
            ],
        }

    return {"futures": summarize(futures_items), "options": summarize(option_items)}
