from __future__ import annotations

import os
import tempfile
from pathlib import Path

ISOLATED_ENV_KEYS = (
    "MARKET_PULSE_DISABLE_BACKGROUND",
    "DERIVATIVES_DB_PATH",
    "MARKET_PULSE_CACHE_FILE",
)


def main() -> None:
    previous_env = {key: os.environ.get(key) for key in ISOLATED_ENV_KEYS}
    try:
        with tempfile.TemporaryDirectory(prefix="market_pulse_e2e_smoke_") as temp_dir:
            isolated_root = Path(temp_dir)
            os.environ["MARKET_PULSE_DISABLE_BACKGROUND"] = "1"
            os.environ["DERIVATIVES_DB_PATH"] = str(isolated_root / "derivatives.sqlite3")
            os.environ["MARKET_PULSE_CACHE_FILE"] = str(isolated_root / "market-cache.json")

            import app

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
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    main()
