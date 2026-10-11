"""Keep parallel pytest workers on independent runtime files."""

import hashlib
import os
from pathlib import Path


def pytest_configure(config):
    worker_id = os.environ.get("PYTEST_XDIST_WORKER")
    if worker_id is None:
        if getattr(config.option, "numprocesses", 0) and config.option.basetemp is None:
            runtime_root = Path(config.rootpath) / "build" / "pytest-runtime"
            runtime_root.mkdir(parents=True, exist_ok=True)
            config.option.basetemp = str(runtime_root / f"run-{os.getpid()}")
        return

    run_id = os.environ["PYTEST_XDIST_TESTRUNUID"]
    directory_name = hashlib.sha256(f"{run_id}:{worker_id}".encode()).hexdigest()[:24]
    runtime_dir = Path(config.rootpath) / "build" / "pytest-workers" / directory_name
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.environ["DERIVATIVES_DB_PATH"] = str(runtime_dir / "derivatives.sqlite3")
    os.environ["MARKET_PULSE_CACHE_FILE"] = str(runtime_dir / "twse-cache.json")
    os.environ["MARKET_PULSE_DISABLE_BACKGROUND"] = "1"
