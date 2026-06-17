import pandas as pd
import streamlit as st

from src.web.common import (
    format_percent,
    path_exists,
    latest_close,
    latest_date,
)
from src.web.loaders import (
    load_ibov_cached,
    load_ifix_cached,
    load_selic_periods_cached,
)


def render_dashboard_page():
    st.title("📊 Margin Miner")

    st.write(
        "Painel inicial do Margin Miner. A ideia aqui é enxergar rapidamente "
        "o estado dos dados locais e entrar nos módulos de ranking, ativo e valuation."
    )

    st.subheader("Status dos dados principais")

    status_rows = [
        {
            "Base": "Selic",
            "Arquivo esperado": "storage/selic/daily_selic.parquet",
            "Existe?": path_exists("storage/selic/daily_selic.parquet"),
        },
        {
            "Base": "IBOV",
            "Arquivo esperado": "storage/benchmarks/IBOV/history.parquet",
            "Existe?": path_exists("storage/benchmarks/IBOV/history.parquet"),
        },
        {
            "Base": "IFIX",
            "Arquivo esperado": "storage/benchmarks/IFIX/history.parquet",
            "Existe?": path_exists("storage/benchmarks/IFIX/history.parquet"),
        },
        {
            "Base": "Ranking",
            "Arquivo esperado": "storage/rankings/latest.parquet",
            "Existe?": path_exists("storage/rankings/latest.parquet"),
        },
        {
            "Base": "Fundamentos",
            "Arquivo esperado": "storage/fundamentus/latest.parquet",
            "Existe?": path_exists("storage/fundamentus/latest.parquet"),
        },
    ]

    st.dataframe(
        pd.DataFrame(status_rows),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Resumo dos benchmarks")

    col1, col2, col3 = st.columns(3)

    try:
        ibov = load_ibov_cached()
        col1.metric(
            "IBOV",
            f"{latest_close(ibov):,.0f}".replace(",", "."),
            f"Última data: {latest_date(ibov)}",
        )
    except Exception as exc:
        col1.error(f"Erro IBOV: {exc}")

    try:
        ifix = load_ifix_cached()
        col2.metric(
            "IFIX",
            f"{latest_close(ifix):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"Última data: {latest_date(ifix)}",
        )
    except Exception as exc:
        col2.error(f"Erro IFIX: {exc}")

    try:
        selic = load_selic_periods_cached()
        selic_12m = selic.set_index("").loc["SELIC", "12m"]
        col3.metric(
            "Selic 12m anualizada",
            format_percent(selic_12m),
        )
    except Exception as exc:
        col3.error(f"Erro Selic: {exc}")