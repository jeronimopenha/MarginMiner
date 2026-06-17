import pandas as pd
import streamlit as st

from src.data.stocks import daily_stock_history
from src.data.selic import selic_periods_row
from src.data.benchmarks import ibov_history, ifix_history
from src.analytics.stock_metrics import (
    stock_metrics_by_period,
    format_metrics_report,
)


@st.cache_data(show_spinner=False)
def load_stock_history_cached(ticker: str) -> pd.DataFrame:
    return daily_stock_history(ticker)


@st.cache_data(show_spinner=False)
def load_selic_periods_cached() -> pd.DataFrame:
    return selic_periods_row()


@st.cache_data(show_spinner=False)
def load_ibov_cached() -> pd.DataFrame:
    return ibov_history()


@st.cache_data(show_spinner=False)
def load_ifix_cached() -> pd.DataFrame:
    return ifix_history()


def get_risk_free_by_period() -> dict[str, float]:
    selic = load_selic_periods_cached()

    return (
        selic
        .set_index("")
        .loc["SELIC"]
        .to_dict()
    )


def calculate_stock_metrics(
    ticker: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    history = load_stock_history_cached(ticker)

    risk_free_by_period = get_risk_free_by_period()

    metrics = stock_metrics_by_period(
        history,
        risk_free_by_period=risk_free_by_period,
    )

    formatted_metrics = format_metrics_report(metrics)

    return history, metrics, formatted_metrics