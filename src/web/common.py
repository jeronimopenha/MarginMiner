from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


def format_percent(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"

    return f"{value:.2%}"


def format_money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"

    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def path_exists(path: str | Path) -> bool:
    return Path(path).exists()


def latest_close(df: pd.DataFrame) -> float | None:
    if df.empty or "close" not in df.columns:
        return None

    return float(df["close"].iloc[-1])


def latest_date(df: pd.DataFrame):
    if df.empty or "date" not in df.columns:
        return None

    return pd.to_datetime(df["date"].iloc[-1]).date()