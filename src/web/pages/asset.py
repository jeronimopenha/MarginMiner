import streamlit as st

from src.web.common import (
    format_money,
    latest_close,
    latest_date,
)
from src.web.loaders import calculate_stock_metrics


def render_asset_page(ticker: str):
    st.title(f"📈 Ativo — {ticker}")

    try:
        history, metrics, formatted_metrics = calculate_stock_metrics(ticker)

        current_price = latest_close(history)
        current_date = latest_date(history)

        col1, col2, col3 = st.columns(3)

        col1.metric("Preço atual", format_money(current_price))
        col2.metric("Última data", str(current_date))
        col3.metric("Linhas históricas", len(history))

        st.subheader("Histórico de preço")

        chart_df = history[["date", "close"]].copy()
        chart_df = chart_df.set_index("date")

        st.line_chart(chart_df)

        st.subheader("Dividendos registrados")

        dividends = history[history["dividend"] > 0][["date", "dividend"]].copy()

        if dividends.empty:
            st.info("Nenhum dividendo encontrado no histórico local.")
        else:
            st.dataframe(
                dividends.tail(30),
                use_container_width=True,
                hide_index=True,
            )

        st.subheader("Métricas quantitativas")

        st.dataframe(
            formatted_metrics,
            use_container_width=True,
        )

        st.caption(
            "Essas métricas vêm dos dados históricos locais: preço, dividendos e Selic."
        )

    except Exception as exc:
        st.error(f"Erro ao carregar {ticker}: {exc}")