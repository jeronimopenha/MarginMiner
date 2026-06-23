import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from datetime import date

from src.portfolio.corporate_actions_storage import load_corporate_actions, save_corporate_actions, add_corporate_action

from src.data.stocks import daily_stock_history
from src.portfolio.engine import calculate_portfolio
from src.portfolio.income_storage import load_income_events, add_income_event, delete_income_event, save_income_events

from src.portfolio.storage import load_transactions, delete_transaction, add_transaction, save_transactions

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

st.set_page_config(
    page_title="Carteira cotizada",
    page_icon="📈",
    layout="wide",
)

def build_consolidated_operations_table(
    transactions: pd.DataFrame,
    corporate_actions: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    if transactions is not None and not transactions.empty:
        for _, transaction in transactions.iterrows():
            rows.append(
                {
                    "id": transaction["id"],
                    "date": pd.to_datetime(transaction["date"]).normalize(),
                    "created_at": transaction.get("created_at"),
                    "source": "lançamento",
                    "type": transaction["type"],
                    "ticker": transaction["ticker"],
                    "target_ticker": transaction["ticker"],
                    "quantity": float(transaction["quantity"]),
                    "unit_price": float(transaction["unit_price"]),
                    "costs": float(transaction["costs"]),
                    "factor": None,
                    "cash_amount": 0.0,
                    "notes": transaction.get("notes", ""),
                }
            )

    if corporate_actions is not None and not corporate_actions.empty:
        for _, action in corporate_actions.iterrows():
            rows.append(
                {
                    "id": action["id"],
                    "date": pd.to_datetime(action["credit_date"]).normalize(),
                    "created_at": action.get("created_at"),
                    "source": "evento corporativo",
                    "type": action["action_type"],
                    "ticker": action["source_ticker"],
                    "target_ticker": action["target_ticker"],
                    "quantity": None,
                    "unit_price": 0.0,
                    "costs": 0.0,
                    "factor": float(action["factor"]),
                    "cash_amount": float(action.get("cash_amount", 0.0)),
                    "notes": action.get("notes", ""),
                }
            )

    if not rows:
        return pd.DataFrame()

    events = pd.DataFrame(rows)

    events["created_at"] = pd.to_datetime(
        events["created_at"],
        errors="coerce",
    )

    events = events.sort_values(
        ["date", "created_at", "id"],
        na_position="last",
    ).reset_index(drop=True)

    positions: dict[str, float] = {}
    cost_basis: dict[str, float] = {}

    output_rows = []

    for _, event in events.iterrows():
        event_type = str(event["type"]).strip().lower()
        ticker = str(event["ticker"]).strip().upper()
        target_ticker = str(event["target_ticker"]).strip().upper()

        positions.setdefault(ticker, 0.0)
        cost_basis.setdefault(ticker, 0.0)

        previous_quantity = positions[ticker]
        previous_cost = cost_basis[ticker]

        previous_average_price = (
            previous_cost / previous_quantity
            if previous_quantity > 0
            else 0.0
        )

        quantity = (
            float(event["quantity"])
            if pd.notna(event["quantity"])
            else 0.0
        )

        unit_price = float(event["unit_price"])
        costs = float(event["costs"])
        cash_amount = float(event["cash_amount"])

        total = 0.0
        quantity_change = 0.0
        realized_result = 0.0

        if event_type == "compra":
            total = quantity * unit_price + costs

            positions[ticker] += quantity
            cost_basis[ticker] += total
            quantity_change = quantity

        elif event_type == "venda":
            if quantity > previous_quantity:
                raise ValueError(
                    f"Venda de {quantity:g} {ticker} maior que a posição "
                    f"anterior de {previous_quantity:g}."
                )

            sale_value = quantity * unit_price - costs
            sold_cost = previous_average_price * quantity
            realized_result = sale_value - sold_cost

            positions[ticker] -= quantity
            cost_basis[ticker] -= sold_cost

            quantity_change = -quantity
            total = sale_value

            if abs(positions[ticker]) < 1e-9:
                positions[ticker] = 0.0
                cost_basis[ticker] = 0.0

        elif event_type in {"bonificação", "bonificacao", "desdobramento", "grupamento"}:
            factor = float(event["factor"])

            new_quantity = previous_quantity * factor
            quantity_change = new_quantity - previous_quantity

            positions[ticker] = new_quantity

            total = cash_amount

            if abs(positions[ticker]) < 1e-9:
                positions[ticker] = 0.0
                cost_basis[ticker] = 0.0

        elif event_type in {"mudança de ticker", "mudanca de ticker", "conversão", "conversao"}:
            factor = float(event["factor"])

            positions.setdefault(target_ticker, 0.0)
            cost_basis.setdefault(target_ticker, 0.0)

            new_quantity = previous_quantity * factor
            moved_cost = previous_cost

            positions[ticker] = 0.0
            cost_basis[ticker] = 0.0

            positions[target_ticker] += new_quantity
            cost_basis[target_ticker] += moved_cost

            quantity_change = -previous_quantity
            total = cash_amount

        current_quantity = positions.get(ticker, 0.0)
        current_cost = cost_basis.get(ticker, 0.0)

        current_average_price = (
            current_cost / current_quantity
            if current_quantity > 0
            else 0.0
        )

        output_rows.append(
            {
                "date": event["date"],
                "source": event["source"],
                "type": event["type"],
                "ticker": ticker,
                "target_ticker": target_ticker,
                "quantity_change": quantity_change,
                "quantity_total": current_quantity,
                "unit_price": unit_price,
                "total": total,
                "cost_basis": current_cost,
                "average_price": current_average_price,
                "realized_result": realized_result,
                "factor": event["factor"],
                "notes": event["notes"],
            }
        )

    return pd.DataFrame(output_rows)


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
    transactions = load_transactions()
    income_events = load_income_events()
    corporate_actions = load_corporate_actions()

    return calculate_portfolio(
        transactions=transactions,
        income_events=income_events,
        corporate_actions=corporate_actions,
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

    equity = float(latest["equity"])
    external_money = float(
        latest["external_money_total"]
    )

    financial_result = (
            equity - external_money
    )

    simple_return = (
        financial_result / external_money
        if external_money > 0
        else 0.0
    )

    columns = st.columns(4)

    columns[0].metric(
        "Patrimônio",
        format_money(equity),
    )

    columns[1].metric(
        "Dinheiro novo",
        format_money(external_money),
    )

    columns[2].metric(
        "Resultado financeiro",
        format_money(financial_result),
    )

    columns[3].metric(
        "Retorno simples",
        f"{simple_return:.2%}",
    )

    columns = st.columns(4)

    columns[0].metric(
        "Valor da cota",
        f"{latest['quota_value']:.6f}",
    )

    columns[1].metric(
        "Retorno cotizado",
        f"{latest['return']:.2%}",
    )

    columns[2].metric(
        "A receber",
        format_money(latest["receivables"]),
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

    message = st.session_state.pop(
        "operations_message",
        None,
    )

    if message:
        st.success(message)

    with st.form(
            "transaction_form",
            clear_on_submit=True,
            enter_to_submit=False,
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
            "Custos",
            min_value=0.0,
            step=0.01,
        )

        notes = st.text_input("Observação")

        submitted = st.form_submit_button(
            "Adicionar operação",
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

            st.session_state["operations_message"] = (
                "Operação adicionada."
            )

            st.cache_data.clear()
            st.rerun()

        except Exception as error:
            st.error(str(error))

    transactions = load_transactions()
    corporate_actions = load_corporate_actions()

    stored_columns = list(transactions.columns)

    transactions = transactions.sort_values(
        ["date", "created_at", "id"]
    ).reset_index(drop=True)

    transactions["quantity_change"] = (
        transactions["quantity"]
        .where(
            transactions["type"] == "compra",
            -transactions["quantity"],
        )
    )

    transactions["total_quantity"] = (
        transactions
        .groupby("ticker")["quantity_change"]
        .cumsum()
    )

    transactions = transactions.drop(
        columns="quantity_change"
    )

    st.subheader("Operações cadastradas")

    if transactions.empty:
        st.info("Nenhuma operação cadastrada.")
        return

    editor_data = transactions[
        [
            "id",
            "date",
            "type",
            "ticker",
            "quantity",
            "total_quantity",
            "unit_price",
            "costs",
            "notes",
        ]
    ].copy()

    editor_data["total"] = (
            editor_data["quantity"]
            * editor_data["unit_price"]
            + editor_data["costs"]
    ).round(2)

    editor_data["total"] = (
            editor_data["quantity"]
            * editor_data["unit_price"]
            + editor_data["costs"]
    )

    editor_data.insert(
        0,
        "Selecionar",
        False,
    )

    editor_data = editor_data.set_index("id")

    edited = st.data_editor(
        editor_data,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=[
            "total",
            "total_quantity",
        ],
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(
                "Selecionar",
                help="Marque as operações que deseja excluir.",
            ),
            "date": st.column_config.DateColumn(
                "Data",
                format="DD/MM/YYYY",
            ),
            "type": st.column_config.SelectboxColumn(
                "Tipo",
                options=["compra", "venda"],
                required=True,
            ),
            "ticker": st.column_config.TextColumn(
                "Ticker",
                required=True,
            ),
            "quantity": st.column_config.NumberColumn(
                "Quantidade",
                min_value=0.000001,
                format="%.6f",
                required=True,
            ),
            "unit_price": st.column_config.NumberColumn(
                "Preço unitário",
                min_value=0.01,
                format="R$ %.2f",
                required=True,
            ),
            "costs": st.column_config.NumberColumn(
                "Custos",
                min_value=0.0,
                format="R$ %.2f",
                required=True,
            ),
            "notes": st.column_config.TextColumn(
                "Observação",
            ),
            "total": st.column_config.NumberColumn(
                "Total",
                format="R$ %.2f",
            ),
            "total_quantity": st.column_config.NumberColumn(
                "Quantidade total",
                format="%.6f",
            ),
        },
        key="transactions_editor",
    )

    selected_ids = edited.index[
        edited["Selecionar"]
    ].tolist()

    button_columns = st.columns(2)

    save_changes = button_columns[0].button(
        "Salvar alterações",
        type="primary",
        use_container_width=True,
    )

    confirm_delete = st.checkbox(
        "Confirmo a exclusão das operações selecionadas",
        disabled=not selected_ids,
    )

    delete_selected = button_columns[1].button(
        "Excluir selecionadas",
        use_container_width=True,
        disabled=(
                not selected_ids
                or not confirm_delete
        ),
    )

    if save_changes:
        try:
            updated = (
                edited
                .drop(
                    columns=[
                        "Selecionar",
                        "total",
                        "total_quantity",
                    ]
                )
                .reset_index()
            )

            updated["ticker"] = (
                updated["ticker"]
                .astype(str)
                .str.strip()
                .str.upper()
                .str.removesuffix(".SA")
            )

            updated["notes"] = (
                updated["notes"]
                .fillna("")
                .astype(str)
            )

            if (
                    updated["ticker"].eq("").any()
            ):
                raise ValueError(
                    "Existem operações sem ticker."
                )

            if (
                    updated["quantity"] <= 0
            ).any():
                raise ValueError(
                    "As quantidades precisam ser positivas."
                )

            if (
                    updated["unit_price"] <= 0
            ).any():
                raise ValueError(
                    "Os preços precisam ser positivos."
                )

            if (
                    updated["costs"] < 0
            ).any():
                raise ValueError(
                    "Os custos não podem ser negativos."
                )

            updated = updated.merge(
                transactions[
                    ["id", "created_at"]
                ],
                on="id",
                how="left",
            )

            updated = updated[
                stored_columns
            ]

            save_transactions(updated)

            st.session_state["operations_message"] = (
                "Alterações salvas. "
                "A cotização foi recalculada."
            )

            st.cache_data.clear()
            st.rerun()

        except Exception as error:
            st.error(str(error))

    if delete_selected:
        remaining = transactions[
            ~transactions["id"].isin(
                selected_ids
            )
        ].copy()

        save_transactions(remaining)

        st.session_state["operations_message"] = (
            f"{len(selected_ids)} operação(ões) excluída(s)."
        )

        st.cache_data.clear()
        st.rerun()
    st.divider()

    st.subheader("Histórico consolidado")

    consolidated = build_consolidated_operations_table(
        transactions=load_transactions(),
        corporate_actions=load_corporate_actions(),
    )

    if consolidated.empty:
        st.info("Nenhum lançamento consolidado encontrado.")
    else:
        st.dataframe(
            consolidated[
                [
                    "date",
                    "source",
                    "type",
                    "ticker",
                    "target_ticker",
                    "quantity_change",
                    "quantity_total",
                    "unit_price",
                    "total",
                    "average_price",
                    "cost_basis",
                    "realized_result",
                    "factor",
                    "notes",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn(
                    "Data",
                    format="DD/MM/YYYY",
                ),
                "source": st.column_config.TextColumn("Fonte"),
                "type": st.column_config.TextColumn("Tipo"),
                "ticker": st.column_config.TextColumn("Ativo"),
                "target_ticker": st.column_config.TextColumn("Ativo destino"),
                "quantity_change": st.column_config.NumberColumn(
                    "Quantidade",
                    format="%.6f",
                ),
                "quantity_total": st.column_config.NumberColumn(
                    "Quantidade total",
                    format="%.6f",
                ),
                "unit_price": st.column_config.NumberColumn(
                    "Preço unitário",
                    format="R$ %.2f",
                ),
                "total": st.column_config.NumberColumn(
                    "Total",
                    format="R$ %.2f",
                ),
                "average_price": st.column_config.NumberColumn(
                    "Preço médio",
                    format="R$ %.4f",
                ),
                "cost_basis": st.column_config.NumberColumn(
                    "Custo acumulado",
                    format="R$ %.2f",
                ),
                "realized_result": st.column_config.NumberColumn(
                    "Resultado realizado",
                    format="R$ %.2f",
                ),
                "factor": st.column_config.NumberColumn(
                    "Fator",
                    format="%.6f",
                ),
                "notes": st.column_config.TextColumn("Observação"),
            },
        )




def render_income_events():
    st.title("Proventos")

    message = st.session_state.pop(
        "income_message",
        None,
    )

    if message:
        st.success(message)

    with st.form(
            "income_form",
            clear_on_submit=True,
            enter_to_submit=False,
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

        net_amount = columns[2].number_input(
            "Valor total líquido",
            min_value=0.01,
            step=0.01,
        )

        notes = st.text_input("Observação")

        submitted = st.form_submit_button(
            "Adicionar provento",
            type="primary",
        )

    if submitted:
        try:
            add_income_event(
                position_date=position_date,
                payment_date=payment_date,
                ticker=ticker,
                quantity=quantity,
                net_amount=net_amount,
                notes=notes,
            )

            st.session_state["income_message"] = (
                "Provento adicionado."
            )

            st.cache_data.clear()
            st.rerun()

        except Exception as error:
            st.error(str(error))

    events = load_income_events()

    st.subheader("Proventos cadastrados")

    if events.empty:
        st.info("Nenhum provento cadastrado.")
        return

    stored_columns = list(events.columns)

    editor_data = events[
        [
            "id",
            "position_date",
            "payment_date",
            "ticker",
            "quantity",
            "net_amount",
            "notes",
        ]
    ].copy()

    editor_data.insert(
        0,
        "Selecionar",
        False,
    )

    editor_data = editor_data.set_index("id")

    edited = st.data_editor(
        editor_data,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(
                "Selecionar",
            ),
            "position_date": st.column_config.DateColumn(
                "Data-com",
                format="DD/MM/YYYY",
                required=True,
            ),
            "payment_date": st.column_config.DateColumn(
                "Pagamento",
                format="DD/MM/YYYY",
                required=True,
            ),
            "ticker": st.column_config.TextColumn(
                "Ticker",
                required=True,
            ),
            "quantity": st.column_config.NumberColumn(
                "Quantidade",
                min_value=0.000001,
                format="%.6f",
                required=True,
            ),
            "net_amount": st.column_config.NumberColumn(
                "Total líquido",
                min_value=0.01,
                format="R$ %.2f",
                required=True,
            ),
            "notes": st.column_config.TextColumn(
                "Observação",
            ),
        },
        key="income_editor",
    )

    selected_ids = edited.index[
        edited["Selecionar"]
    ].tolist()

    columns = st.columns(2)

    save_changes = columns[0].button(
        "Salvar alterações",
        type="primary",
        use_container_width=True,
    )

    confirm_delete = st.checkbox(
        "Confirmo a exclusão dos proventos selecionados",
        disabled=not selected_ids,
    )

    delete_selected = columns[1].button(
        "Excluir selecionados",
        use_container_width=True,
        disabled=(
                not selected_ids
                or not confirm_delete
        ),
    )

    if save_changes:
        try:
            updated = (
                edited
                .drop(columns="Selecionar")
                .reset_index()
            )

            updated["ticker"] = (
                updated["ticker"]
                .astype(str)
                .str.strip()
                .str.upper()
                .str.removesuffix(".SA")
            )

            updated["notes"] = (
                updated["notes"]
                .fillna("")
                .astype(str)
            )

            invalid_dates = (
                    pd.to_datetime(updated["payment_date"])
                    < pd.to_datetime(updated["position_date"])
            )

            if invalid_dates.any():
                raise ValueError(
                    "Existem pagamentos anteriores à data-com."
                )

            if updated["ticker"].eq("").any():
                raise ValueError(
                    "Existem proventos sem ticker."
                )

            if (updated["quantity"] <= 0).any():
                raise ValueError(
                    "As quantidades precisam ser positivas."
                )

            if (updated["net_amount"] <= 0).any():
                raise ValueError(
                    "Os valores precisam ser positivos."
                )

            updated = updated.merge(
                events[
                    ["id", "created_at"]
                ],
                on="id",
                how="left",
            )

            updated = updated[stored_columns]

            save_income_events(updated)

            st.session_state["income_message"] = (
                "Alterações salvas e cotização recalculada."
            )

            st.cache_data.clear()
            st.rerun()

        except Exception as error:
            st.error(str(error))

    if delete_selected:
        remaining = events[
            ~events["id"].isin(selected_ids)
        ].copy()

        save_income_events(remaining)

        st.session_state["income_message"] = (
            f"{len(selected_ids)} provento(s) excluído(s)."
        )

        st.cache_data.clear()
        st.rerun()


def render_corporate_actions_page() -> None:
    st.title("Eventos corporativos")

    st.caption(
        "Use esta tela para bonificações, desdobramentos, grupamentos e conversões. "
        "Esses eventos alteram quantidade de ações, mas não entram como dinheiro novo."
    )

    action_type_options = [
        "bonificação",
        "desdobramento",
        "grupamento",
        "mudança de ticker",
        "conversão",
    ]

    with st.form(
            "corporate_action_form",
            clear_on_submit=True,
            enter_to_submit=False,
    ):
        col1, col2, col3 = st.columns(3)

        ex_date = col1.date_input("Data ex")
        credit_date = col2.date_input("Data de crédito")
        action_type = col3.selectbox("Tipo", action_type_options)

        col1, col2, col3 = st.columns(3)

        source_ticker = col1.text_input(
            "Ativo de origem",
            placeholder="BEES3",
        ).strip().upper()

        needs_target = action_type in {"mudança de ticker", "conversão"}

        target_ticker = col2.text_input(
            "Ativo de destino",
            placeholder="PCIP11",
            disabled=not needs_target,
        ).strip().upper()

        factor = col3.number_input(
            "Fator",
            min_value=0.000001,
            value=1.0,
            step=0.01,
            format="%.6f",
            help=(
                "Bonificação de 10%: 1.10. "
                "Desdobramento 1 para 2: 2.00. "
                "Grupamento 10 para 1: 0.10. "
                "Mudança simples de ticker: 1.00."
            ),
        )

        cash_amount = st.number_input(
            "Valor em dinheiro recebido",
            min_value=0.0,
            value=0.0,
            step=0.01,
            help="Use para sobras/frações pagas em dinheiro, se houver.",
        )

        notes = st.text_input("Observação")

        submitted = st.form_submit_button(
            "Salvar evento corporativo",
            type="primary",
        )

    if submitted:
        try:
            final_target = target_ticker if needs_target else source_ticker

            add_corporate_action(
                ex_date=ex_date,
                credit_date=credit_date,
                action_type=action_type,
                source_ticker=source_ticker,
                target_ticker=final_target,
                factor=factor,
                cash_amount=cash_amount,
                notes=notes,
            )

            st.cache_data.clear()
            st.success("Evento corporativo salvo.")
            st.rerun()

        except Exception as exc:
            st.error(str(exc))

    st.subheader("Eventos cadastrados")

    events = load_corporate_actions()

    if events.empty:
        st.info("Nenhum evento corporativo cadastrado.")
        return

    editor_data = events.copy()
    editor_data.insert(0, "Selecionar", False)

    edited = st.data_editor(
        editor_data,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["id", "created_at"],
        column_config={
            "Selecionar": st.column_config.CheckboxColumn("Selecionar"),
            "ex_date": st.column_config.DateColumn("Data ex"),
            "credit_date": st.column_config.DateColumn("Data de crédito"),
            "action_type": st.column_config.SelectboxColumn(
                "Tipo",
                options=action_type_options,
            ),
            "source_ticker": st.column_config.TextColumn("Ativo origem"),
            "target_ticker": st.column_config.TextColumn("Ativo destino"),
            "factor": st.column_config.NumberColumn("Fator", format="%.6f"),
            "cash_amount": st.column_config.NumberColumn(
                "Dinheiro recebido",
                format="R$ %.2f",
            ),
            "notes": st.column_config.TextColumn("Observação"),
        },
    )

    col1, col2 = st.columns(2)

    if col1.button("Salvar alterações da tabela", type="primary"):
        updated = edited.drop(columns=["Selecionar"]).copy()
        save_corporate_actions(updated)

        st.cache_data.clear()
        st.success("Eventos corporativos atualizados.")
        st.rerun()

    selected_ids = edited.loc[edited["Selecionar"], "id"].tolist()

    if col2.button("Excluir selecionados", disabled=not selected_ids):
        remaining = events[~events["id"].isin(selected_ids)].copy()
        save_corporate_actions(remaining)

        st.cache_data.clear()
        st.success("Eventos selecionados excluídos.")
        st.rerun()


def main():
    st.sidebar.title("Carteira")

    page = st.sidebar.radio(
        "Menu",
        [
            "Resumo",
            "Compras e vendas",
            "Proventos",
            "Eventos corporativos",
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

    elif page == "Proventos":
        render_income_events()

    elif page == "Eventos corporativos":
        render_corporate_actions_page()


if __name__ == "__main__":
    main()
