from pathlib import Path
from config import (
    PRICES_DIR,
    DIVIDENDS_DIR,
    BENCHMARK_DIR,
    DERIVED_DIR,
    METRICS_DIR,
    META_DIR,
)

def ensure_dirs():
    for path in [
        PRICES_DIR,
        DIVIDENDS_DIR,
        BENCHMARK_DIR,
        DERIVED_DIR / "total_return",
        METRICS_DIR,
        META_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)

def prices_path(ticker):
    return PRICES_DIR / f"{ticker}.parquet"

def dividends_path(ticker):
    return DIVIDENDS_DIR / f"{ticker}.parquet"

def metrics_path(ticker):
    return METRICS_DIR / f"{ticker}.json"
