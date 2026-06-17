import pandas as pd
import streamlit as st

from src.web.common import (
    format_money,
    format_percent,
    latest_close,
)
from src.web.loaders import calculate_stock_metrics


def render_valuation_page(ticker: str):
    st.title(f"🧮 Valuation — {ticker}")

    st.write(
        "Primeira versão do valuation. Por enquanto, alguns dados ainda são manuais. "
        "A ideia é descobrir quais campos precisam ser automatizados."
    )

    try:
        history, metrics, formatted_metrics = calculate_stock_metrics(ticker)
        current_price = latest_close(history)

    except Exception:
        history = pd.DataFrame()
        metrics = pd.DataFrame()
        formatted_metrics = pd.DataFrame()
        current_price = None

    st.subheader("Dados de mercado")

    col1, col2 = st.columns(2)

    price_used = col1.number_input(
        "Preço usado",
        min_value=0.0,
        value=float(current_price) if current_price else 0.0,
        step=0.01,
    )

    margin_of_safety = col2.number_input(
        "Margem de segurança desejada",
        min_value=0.0,
        max_value=0.9,
        value=0.15,
        step=0.01,
        format="%.2f",
    )

    st.subheader("Dados fundamentalistas")

    col1, col2, col3 = st.columns(3)

    base_value_type = col1.selectbox(
        "Base do valuation",
        [
            "LPA",
            "FCL por ação",
            "Dividendo por ação",
        ],
    )

    base_value = col2.number_input(
        f"Valor base ({base_value_type})",
        min_value=0.0,
        value=1.50,
        step=0.01,
    )

    payout = col3.number_input(
        "Payout estimado",
        min_value=0.0,
        max_value=1.5,
        value=0.50,
        step=0.01,
        format="%.2f",
    )

    st.subheader("Premissas")

    col1, col2, col3 = st.columns(3)

    growth_1_3 = col1.number_input(
        "Crescimento anos 1 a 3",
        min_value=-0.50,
        max_value=1.00,
        value=0.05,
        step=0.01,
        format="%.2f",
    )

    perpetual_growth = col2.number_input(
        "Crescimento perpetuidade",
        min_value=-0.10,
        max_value=0.10,
        value=0.02,
        step=0.01,
        format="%.2f",
    )

    discount_rate = col3.number_input(
        "Taxa de desconto",
        min_value=0.01,
        max_value=0.50,
        value=0.16,
        step=0.01,
        format="%.2f",
    )

    st.subheader("Cálculo provisório")

    if discount_rate <= perpetual_growth:
        st.error(
            "A taxa de desconto precisa ser maior que o crescimento na perpetuidade."
        )
        return

    projected_1 = base_value * (1 + growth_1_3)
    projected_2 = projected_1 * (1 + growth_1_3)
    projected_3 = projected_2 * (1 + growth_1_3)

    terminal_cash_flow = projected_3 * (1 + perpetual_growth)
    terminal_value = terminal_cash_flow / (discount_rate - perpetual_growth)

    present_value = (
        projected_1 / ((1 + discount_rate) ** 1)
        + projected_2 / ((1 + discount_rate) ** 2)
        + projected_3 / ((1 + discount_rate) ** 3)
        + terminal_value / ((1 + discount_rate) ** 3)
    )

    fair_price = present_value
    target_price = fair_price * (1 - margin_of_safety)

    upside_to_fair = (
        fair_price / price_used - 1
        if price_used > 0
        else None
    )

    upside_to_target = (
        target_price / price_used - 1
        if price_used > 0
        else None
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Preço justo", format_money(fair_price))
    col2.metric("Preço teto", format_money(target_price))
    col3.metric("Margem até valor justo", format_percent(upside_to_fair))
    col4.metric("Margem até preço teto", format_percent(upside_to_target))

    valuation_table = pd.DataFrame(
        [
            {
                "Ano": "1",
                "Fluxo projetado": projected_1,
                "Valor presente": projected_1 / ((1 + discount_rate) ** 1),
            },
            {
                "Ano": "2",
                "Fluxo projetado": projected_2,
                "Valor presente": projected_2 / ((1 + discount_rate) ** 2),
            },
            {
                "Ano": "3",
                "Fluxo projetado": projected_3,
                "Valor presente": projected_3 / ((1 + discount_rate) ** 3),
            },
            {
                "Ano": "Terminal",
                "Fluxo projetado": terminal_value,
                "Valor presente": terminal_value / ((1 + discount_rate) ** 3),
            },
        ]
    )

    st.dataframe(
        valuation_table,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Notas pessoais")

    notes = st.text_area(
        "Anotações sobre a tese",
        height=150,
        placeholder="Ex: empresa excelente, mas quero margem maior; risco regulatório; payout alto; crescimento limitado...",
    )

    if st.button("Salvar valuation"):
        st.warning(
            "Ainda não implementamos SQLite de valuations. "
            "Esta tela serve primeiro para validar os campos necessários."
        )

    with st.expander("Métricas quantitativas usadas como apoio"):
        if formatted_metrics.empty:
            st.info("Sem métricas carregadas.")
        else:
            st.dataframe(
                formatted_metrics,
                use_container_width=True,
            )