import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.data.stocks import daily_stock_history
from src.portfolio.engine import calculate_portfolio
from src.portfolio.income_storage import load_income_events, add_income_event, delete_income_event
from src.portfolio.storage import load_transactions, delete_transaction, add_transaction

st.set_page_config(
    page_title="Carteira cotizada",
    page_icon="📈",
    layout="wide",
)


def format_money(value: float) -> str:
    return (
        f"R$ {value:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


@st.cache_data(
    show_spinner=False,
    ttl=900,
)
def load_market_history(
        ticker: str,
) -> pd.DataFrame:
    return daily_stock_history(ticker)


def calculate_current_portfolio():
    return calculate_portfolio(
        transactions=load_transactions(),
        income_events=load_income_events(),
        history_loader=load_market_history,
    )


def render_summary():
    st.title("Carteira cotizada")

    transactions = load_transactions()

    if transactions.empty:
        st.info(
            "Ainda não existem compras ou vendas cadastradas."
        )
        return

    try:
        with st.spinner(
                "Calculando patrimônio e cotização..."
        ):
            result = calculate_current_portfolio()

    except Exception as error:
        st.error(
            f"Não foi possível calcular a carteira: {error}"
        )
        return

    latest = result.latest

    if latest is None:
        st.info(
            "Não existem dados suficientes para o cálculo."
        )
        return

    columns = st.columns(6)

    columns[0].metric(
        "Patrimônio",
        format_money(latest["equity"]),
    )

    columns[1].metric(
        "Valor da cota",
        f"{latest['quota_value']:.6f}",
    )

    columns[2].metric(
        "Rentabilidade",
        f"{latest['return']:.2%}",
    )

    columns[3].metric(
        "Dinheiro novo",
        format_money(
            latest["external_money_total"]
        ),
    )

    columns[4].metric(
        "A receber",
        format_money(latest["receivables"]),
    )

    columns[5].metric(
        "Caixa disponível",
        format_money(latest["cash"]),
    )

    st.subheader("Evolução da cota")

    quota_history = (
        result.history[
            ["date", "quota_value"]
        ]
        .set_index("date")
    )

    st.line_chart(
        quota_history,
        use_container_width=True,
    )

    st.subheader("Posição atual")

    st.dataframe(
        result.positions,
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Ver movimentações calculadas"):
        st.dataframe(
            result.ledger,
            use_container_width=True,
            hide_index=True,
        )


def parse_optional_money(text: str):
    text = text.strip()

    if not text:
        return None

    if "," in text:
        text = (
            text
            .replace(".", "")
            .replace(",", ".")
        )

    return float(text)


def render_operations():
    st.title("Compras e vendas")

    with st.form(
        "transaction_form",
        clear_on_submit=True,
    ):
        columns = st.columns(3)

        transaction_date = columns[0].date_input(
            "Data da operação",
            value=date.today(),
        )

        transaction_type = columns[1].selectbox(
            "Tipo",
            ["compra", "venda"],
        )

        ticker = columns[2].text_input(
            "Ticker",
            placeholder="ITSA4",
        )

        columns = st.columns(3)

        quantity = columns[0].number_input(
            "Quantidade",
            min_value=1.0,
            step=1.0,
        )

        unit_price = columns[1].number_input(
            "Preço unitário",
            min_value=0.01,
            step=0.01,
        )

        costs = columns[2].number_input(
            "Custos da operação",
            min_value=0.0,
            step=0.01,
        )

        notes = st.text_input(
            "Observação",
        )

        submitted = st.form_submit_button(
            "Salvar operação",
            type="primary",
        )

    if submitted:
        try:
            add_transaction(
                transaction_date=transaction_date,
                transaction_type=transaction_type,
                ticker=ticker,
                quantity=quantity,
                unit_price=unit_price,
                costs=costs,
                notes=notes,
            )

            st.success("Operação salva.")

        except Exception as error:
            st.error(str(error))

    transactions = load_transactions()

    st.subheader("Operações cadastradas")

    if transactions.empty:
        st.info("Nenhuma operação cadastrada.")
        return

    display = transactions.copy()

    display["total"] = (
        display["quantity"]
        * display["unit_price"]
        + display["costs"]
    )

    st.dataframe(
        display[
            [
                "date",
                "type",
                "ticker",
                "quantity",
                "unit_price",
                "costs",
                "total",
                "notes",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    labels = {
        row["id"]: (
            f"{row['date'].date()} | "
            f"{row['type']} | "
            f"{row['ticker']} | "
            f"{row['quantity']:g} ações"
        )
        for _, row in transactions.iterrows()
    }

    selected_id = st.selectbox(
        "Operação para excluir",
        options=list(labels),
        format_func=labels.get,
    )

    if st.button("Excluir operação"):
        delete_transaction(selected_id)
        st.cache_data.clear()
        st.rerun()


def render_income_events():
    st.title("Dividendos e JCP")

    income_type = st.selectbox(
        "Tipo do provento",
        ["dividendo", "jcp"],
    )

    with st.form(
        "income_form",
        clear_on_submit=True,
    ):
        columns = st.columns(2)

        position_date = columns[0].date_input(
            "Data-com",
            value=date.today(),
        )

        payment_date = columns[1].date_input(
            "Data de pagamento",
            value=date.today(),
        )

        columns = st.columns(3)

        ticker = columns[0].text_input(
            "Ticker",
            placeholder="CMIG4",
        )

        quantity = columns[1].number_input(
            "Quantidade de ações",
            min_value=1.0,
            step=1.0,
        )

        gross_amount = columns[2].number_input(
            "Valor bruto total",
            min_value=0.01,
            step=0.01,
        )

        tax_rate = None
        net_amount_text = ""

        if income_type == "jcp":
            columns = st.columns(2)

            tax_percentage = columns[0].selectbox(
                "Alíquota de IR",
                [17.5, 15.0],
            )

            tax_rate = tax_percentage / 100

            net_amount_text = columns[1].text_input(
                "Valor líquido real",
                placeholder="Ex.: 39,46",
                help=(
                    "Deixe vazio para o sistema calcular. "
                    "Informe o valor do extrato para máxima precisão."
                ),
            )

        notes = st.text_input(
            "Observação",
            placeholder="Ex.: primeira parcela",
        )

        submitted = st.form_submit_button(
            "Salvar provento",
            type="primary",
        )

    if submitted:
        try:
            net_amount = parse_optional_money(
                net_amount_text
            )

            add_income_event(
                position_date=position_date,
                payment_date=payment_date,
                ticker=ticker,
                income_type=income_type,
                quantity=quantity,
                gross_amount=gross_amount,
                tax_rate=tax_rate,
                net_amount=net_amount,
                notes=notes,
            )

            st.success("Provento salvo.")

        except Exception as error:
            st.error(str(error))

    events = load_income_events()

    st.subheader("Proventos cadastrados")

    if events.empty:
        st.info("Nenhum provento cadastrado.")
        return

    st.dataframe(
        events[
            [
                "position_date",
                "payment_date",
                "ticker",
                "type",
                "quantity",
                "gross_amount",
                "tax_rate",
                "tax_amount",
                "net_amount",
                "notes",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    labels = {
        row["id"]: (
            f"{row['payment_date'].date()} | "
            f"{row['ticker']} | "
            f"{row['type']} | "
            f"{format_money(row['net_amount'])}"
        )
        for _, row in events.iterrows()
    }

    selected_id = st.selectbox(
        "Provento para excluir",
        options=list(labels),
        format_func=labels.get,
    )

    if st.button("Excluir provento"):
        delete_income_event(selected_id)
        st.cache_data.clear()
        st.rerun()

def main():
    st.sidebar.title("Carteira")

    page = st.sidebar.radio(
        "Menu",
        [
            "Resumo",
            "Compras e vendas",
            "Dividendos e JCP",
        ],
    )

    if st.sidebar.button(
        "Atualizar dados de mercado"
    ):
        st.cache_data.clear()
        st.rerun()

    if page == "Resumo":
        render_summary()

    elif page == "Compras e vendas":
        render_operations()

    elif page == "Dividendos e JCP":
        render_income_events()


if __name__ == "__main__":
    main()