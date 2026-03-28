from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"
CSV_DIR = DATA_DIR / "csv" / "fii"
CACHE_DIR = DATA_DIR / "cache"

PRICES_DIR = CACHE_DIR / "prices"
DIVIDENDS_DIR = CACHE_DIR / "dividends"
BENCHMARK_DIR = CACHE_DIR / "benchmarks"
DERIVED_DIR = CACHE_DIR / "derived"
METRICS_DIR = CACHE_DIR / "metrics"
META_DIR = CACHE_DIR / "meta"

HISTORY_YEARS = 10
RF_DEFAULT = 0.13
TRADING_DAYS = 252
BENCHMARK = "^IFIX"
