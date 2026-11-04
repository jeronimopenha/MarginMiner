from datetime import date

import streamlit as st
import pandas as pd
import sqlite3

from common.core import TYPES
from common.common import attempt, get_store
from common.constants import allowed


def movements_screen():
    uid = st.session_state.user["id"]

    st.subheader("Movimentações")
    st.info(
        "Aportes acrescentam dinheiro à carteira. "
        "Compras utilizam o saldo disponível. "
        "Proventos são registrados pelo total recebido."
    )

    message_key = f"movement_message_{uid}"

    if message := st.session_state.pop(message_key, None):
        st.success(message)

    tabs = st.tabs(list(TYPES))

    for kind, tab in zip(TYPES, tabs):
        with tab:
            movement_tab(kind)


def movement_tab(kind):
    store = get_store()
    uid = st.session_state.user["id"]
    tickers = [a["ticker"] for a in st.session_state.user["assets"]]
    movements = st.session_state.user["movements"]
    prefix = f"movement_{uid}_{kind}"

    def persist(action, message):
        try:
            action()
        except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            st.error(str(exc))
        else:
            # Atualiza a grade deste tipo após incluir ou excluir.
            st.session_state.pop(f"movements_grid_{uid}_{kind}", None)

            st.session_state[f"movement_message_{uid}"] = message
            st.rerun()

    fields = allowed[kind]

    values = {
        "quantidade": "0",
        "preco": "0",
        "valor_bruto": "0",
        "valor_liquido": "0",
        "taxas": "0",
        "fator": "1",
    }

    labels = {
        "quantidade": "Quantidade",
        "preco": "Preço unitário",
        "valor_bruto": "Valor total bruto",
        "valor_liquido": "Valor total líquido",
        "taxas": "Taxas da operação",
        "fator": "Fator de alteração da quantidade",
    }

    st.markdown("**Novo lançamento**")

    with st.form(prefix, clear_on_submit=True):
        day = st.date_input(
            "Data",
            max_value=date.today(),
            key=f"{prefix}_data",
        )

        order = st.number_input(
            "Ordem no dia (não repetir)",
            min_value=1,
            value=max([r["ordem"] for r in movements] + [0]) + 1,
            step=1,
            key=f"{prefix}_ordem",
        )

        ticker = ""

        if kind not in ("APORTE", "RETIRADA", "TAXA"):
            ticker = st.selectbox(
                "Ativo",
                [""] + tickers,
                key=f"{prefix}_ticker",
            )

        for field, default in values.items():
            if field in fields:
                values[field] = st.text_input(
                    labels[field],
                    value=default,
                    key=f"{prefix}_{field}",
                )

        if kind == "BONIFICACAO":
            st.caption("Informe a quantidade adicional recebida.")

        elif kind == "DESDOBRAMENTO":
            st.caption("Exemplo: fator 2 dobra a quantidade.")

        elif kind == "GRUPAMENTO":
            st.caption("Exemplo: fator 0,1 transforma 10 unidades em 1.")

        elif kind == "LIQUIDACAO":
            st.caption("Encerra toda a posição e credita o total recebido.")

        elif kind == "AMORTIZACAO":
            st.caption("Credita caixa sem alterar a quantidade.")

        note = st.text_input(
            "Observação",
            key=f"{prefix}_observacao",
        )

        if st.form_submit_button("Salvar lançamento"):
            movement = {
                "data": day.isoformat(),
                "ordem": int(order),
                "tipo": kind,
                "ticker": ticker,
                **values,
                "observacao": note,
            }

            persist(
                lambda: store.save_movements(uid, [movement]),
                "Lançamento cadastrado.",
            )
            st.session_state.user["movements"] = store.movements(uid)

    movements_grid(kind)

    # A exclusão oferece somente os registros desta aba.
    type_rows = [r for r in movements if r["tipo"] == kind]

    if type_rows:
        with st.expander("Excluir lançamento"):
            rows_by_id = {r["id"]: r for r in type_rows}

            def describe(mid):
                row = rows_by_id[mid]
                return (
                    f"{row['data']} · "
                    f"{row['ticker'] or 'Caixa'} · "
                    f"ordem {row['ordem']} · "
                    f"{mid[:8]}"
                )

            mid = st.selectbox(
                "Lançamento",
                list(rows_by_id),
                format_func=describe,
                key=f"{prefix}_delete_id",
            )

            confirm = st.checkbox(
                "Confirmo a exclusão",
                key=f"{prefix}_delete_confirm_{mid}",
            )

            if st.button(
                "Excluir",
                disabled=not confirm,
                key=f"{prefix}_delete_button",
            ):
                persist(
                    lambda: store.delete(uid, mid),
                    "Lançamento excluído.",
                )
                st.session_state.user["movements"] = store.movements(uid)


def movements_grid(kind):
    store = get_store()
    uid = st.session_state.user["id"]
    tickers = [a["ticker"] for a in st.session_state.user["assets"]]

    st.subheader(f"Editar lançamentos — {kind}")

    state_key = f"movements_grid_{uid}_{kind}"
    saved_key = f"movements_saved_{uid}_{kind}"

    def load_rows():
        return [
            row for row in st.session_state.user["movements"] if row["tipo"] == kind
        ]

    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "original": load_rows(),
            "revision": 0,
        }

    state = st.session_state[state_key]

    if st.button(
        "Recarregar lançamentos — descarta edições pendentes",
        key=f"reload_movements_{uid}_{kind}",
    ):
        state["original"] = load_rows()
        state["revision"] += 1

    original = state["original"]

    if not original:
        st.info("Não há lançamentos deste tipo.")
        return

    columns = ["id", "data", "ordem"]

    if kind not in ("APORTE", "RETIRADA", "TAXA"):
        columns.append("ticker")

    numeric_fields = [
        field
        for field in (
            "quantidade",
            "preco",
            "valor_bruto",
            "valor_liquido",
            "taxas",
            "fator",
        )
        if field in allowed[kind]
    ]

    columns.extend(numeric_fields)
    columns.append("observacao")

    df = pd.DataFrame(original)[columns].copy()

    df["data"] = pd.to_datetime(df["data"]).dt.date
    df["ordem"] = df["ordem"].astype("Int64")

    for column in columns:
        if column not in ("data", "ordem"):
            df[column] = df[column].astype("string")

    labels = {
        "quantidade": "Quantidade",
        "preco": "Preço unitário",
        "valor_bruto": "Valor bruto",
        "valor_liquido": "Valor líquido",
        "taxas": "Taxas",
        "fator": "Fator",
    }

    config = {
        "id": None,
        "data": st.column_config.DateColumn(
            "Data",
            format="DD/MM/YYYY",
            max_value=date.today(),
            required=True,
        ),
        "ordem": st.column_config.NumberColumn(
            "Ordem",
            min_value=1,
            step=1,
            required=True,
        ),
        "ticker": st.column_config.SelectboxColumn(
            "Ativo",
            options=tickers,
            required=True,
        ),
        "observacao": st.column_config.TextColumn("Observação"),
    }

    for field in numeric_fields:
        config[field] = st.column_config.TextColumn(
            labels[field],
            required=True,
        )

    edited_df = st.data_editor(
        df,
        key=(f"movements_editor_{uid}_{kind}_" f"{state['revision']}"),
        hide_index=True,
        num_rows="fixed",
        disabled=["id"],
        column_config=config,
    )

    visible_rows = (
        edited_df.astype(object).where(pd.notna(edited_df), None).to_dict("records")
    )

    for row in visible_rows:
        if row["data"] is not None:
            row["data"] = row["data"].isoformat()

    original_by_id = {row["id"]: row for row in original}

    # Recupera os campos que não são exibidos na grade.
    edited = [
        {
            **original_by_id[row["id"]],
            **row,
        }
        for row in visible_rows
    ]

    if edited != original:
        try:
            store.update_movements_grid(uid, kind, original, edited)
            st.session_state.user["movements"] = store.movements(uid)

        except ValueError as exc:
            st.warning(str(exc))

        else:
            state["original"] = load_rows()
            state["revision"] += 1
            st.session_state[saved_key] = True
            st.rerun()

    if st.session_state.pop(saved_key, False):
        st.success("Lançamentos atualizados.")
