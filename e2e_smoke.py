from __future__ import annotations

import os

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")

import app


def main() -> None:
    client = app.app.test_client()
    pages = [
        "index.html",
        "futures.html",
        "options.html",
        "derivatives-analytics.html",
        "derivatives-ai.html",
        "derivatives-status.html",
    ]
    apis = [
        "/api/derivatives/v1-status",
        "/api/futures?limit=all",
        "/api/options?underlying=STO",
        "/api/options?underlying=ETO",
        "/api/institution?product=TX",
        "/api/basis?future=TX&spot=TAIEX",
        "/api/ai-analysis?target=TX",
    ]
    failures: list[str] = []
    for page in pages:
        response = client.get("/" + page)
        if response.status_code != 200:
            failures.append(f"{page}: HTTP {response.status_code}")
    for api in apis:
        response = client.get(api)
        body = response.get_json(silent=True)
        if response.status_code != 200 or not isinstance(body, dict) or body.get("success") is not True:
            failures.append(f"{api}: HTTP {response.status_code}, body={body}")
    if failures:
        raise SystemExit("\n".join(failures))
    print("E2E_SMOKE_OK")


if __name__ == "__main__":
    main()
