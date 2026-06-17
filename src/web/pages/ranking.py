from pathlib import Path

import pandas as pd
import streamlit as st


def render_ranking_page():
    st.title("🏆 Rankings")

    st.info(
        "Por enquanto este ranking é apenas quantitativo. "
        "Depois vamos separar ranking Joel e ranking próprio."
    )

    ranking_type = st.selectbox(
        "Tipo de ranking",
        [
            "Quantitativo provisório",
            "Joel Greenblatt",
            "Meu ranking",
        ],
    )

    if ranking_type != "Quantitativo provisório":
        st.warning(
            "Esse ranking ainda não foi implementado. Amanhã definiremos as regras."
        )
        st.stop()

    ranking_path = Path("storage/rankings/latest.parquet")

    if not ranking_path.exists():
        st.warning(
            "Ainda não existe ranking salvo em `storage/rankings/latest.parquet`."
        )

        st.write("Rode primeiro no terminal:")

        st.code("python main.py")

        st.stop()

    ranking = pd.read_parquet(ranking_path)

    st.success("Ranking local encontrado.")

    st.subheader("Filtros")

    col1, col2, col3 = st.columns(3)

    only_ok = col1.checkbox(
        "Mostrar apenas ativos válidos",
        value=True,
    )

    min_liquidity = col2.number_input(
        "Liquidez mínima 12m",
        min_value=0.0,
        value=1_000_000.0,
        step=1_000_000.0,
    )

    min_score = col3.slider(
        "Score mínimo",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.05,
    )

    filtered = ranking.copy()

    if only_ok and "status" in filtered.columns:
        filtered = filtered[filtered["status"] == "ok"]

    if "liquidity_12m" in filtered.columns:
        filtered = filtered[
            filtered["liquidity_12m"].fillna(0) >= min_liquidity
        ]

    if "score_quant" in filtered.columns:
        filtered = filtered[
            filtered["score_quant"].fillna(0) >= min_score
        ]

    st.subheader("Ranking quantitativo")

    display_columns = [
        "ticker",
        "sector",
        "company_type",
        "latest_price",
        "latest_date",
        "liquidity_12m",

        "cagr_total_5A",
        "sharpe_total_5A",
        "sortino_total_5A",
        "calmar_total_5A",
        "drawdown_total_5A",
        "vol_total_5A",

        "score_return_5A",
        "score_sharpe_5A",
        "score_sortino_5A",
        "score_drawdown_5A",
        "score_liquidity",
        "score_quant",
    ]

    existing_columns = [
        col for col in display_columns
        if col in filtered.columns
    ]

    st.dataframe(
        filtered[existing_columns],
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Ranking provisório usando apenas preço, dividendos, Selic e risco. "
        "Ainda não inclui P/L, P/VP, ROE, FCL, dívida ou valuation."
    )

    with st.expander("Ver dados brutos completos"):
        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )