from datetime import date

import streamlit as st
import pandas as pd

from common.core import TYPES
from common.common import attempt, get_store
from common.constants import allowed


def movements_ascreen():
    store = get_store()

    uid = st.session_state.user["id"]
    assets = store.assets(uid)
    tickers = [a["ticker"] for a in assets]
    rows = store.movements(uid)

    st.subheader("Novo lançamento")
    st.info(
        "Cadastre os aportes antes das compras. Valor recebido é o total líquido, não por ação. Ordem define a sequência dentro do dia."
    )
    kind = st.selectbox("Tipo", TYPES)

    fields = allowed[kind]

    # Começa sempre com os defaults dos campos não utilizados.
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

    # Um formulário diferente por tipo evita reaproveitar
    # acidentalmente valores digitados em outra operação.
    with st.form(f"movement_{uid}_{kind}", clear_on_submit=True):
        day = st.date_input(
            "Data",
            max_value=date.today(),
        )

        order = st.number_input(
            "Ordem no dia (não repetir)",
            min_value=1,
            value=max([r["ordem"] for r in rows] + [0]) + 1,
            step=1,
        )

        ticker = ""

        if kind not in ("APORTE", "RETIRADA", "TAXA"):
            ticker = st.selectbox(
                "Ativo",
                [""] + tickers,
            )

        for field, default in values.items():
            if field in fields:
                values[field] = st.text_input(
                    labels[field],
                    value=default,
                )

        if kind == "BONIFICACAO":
            st.caption("Informe a quantidade adicional recebida.")

        elif kind == "DESDOBRAMENTO":
            st.caption("Exemplo: fator 2 dobra a quantidade.")

        elif kind == "GRUPAMENTO":
            st.caption(
                "Exemplo: fator 0,1 transforma 10 unidades em 1."
            )

        note = st.text_input("Observação")

        if st.form_submit_button("Salvar lançamento"):
            attempt(
                lambda: store.save_movements(
                    uid,
                    [
                        {
                            "data": day.isoformat(),
                            "ordem": int(order),
                            "tipo": kind,
                            "ticker": ticker,
                            **values,
                            "observacao": note,
                        }
                    ],
                )
            )
    st.caption(
        "Liquidação: encerra toda a posição e credita o valor total recebido. Amortização: credita caixa sem alterar a quantidade. Bonificação não calcula custo fiscal nesta versão."
    )
    rows = store.movements(uid)
    movements_grid(store, uid, kind, tickers)
    if rows:
        with st.expander("Excluir um lançamento para corrigir"):
            mid = st.selectbox(
                "Lançamento",
                [r["id"] for r in rows],
                format_func=lambda mid: next(
                    f"{r['data']} · {r['tipo']} · {r['ticker'] or 'Caixa'} · {r['id'][:8]}"
                    for r in rows
                    if r["id"] == mid
                ),
            )
            confirm = st.checkbox("Confirmo a exclusão")
            if st.button("Excluir", disabled=not confirm):
                attempt(lambda: store.delete(uid, mid))
                st.caption(
                    "Se a exclusão invalidar lançamentos posteriores, ela será rejeitada. Recarregue a página para atualizar a lista."
                )

def movements_grid(store, uid, kind, tickers):
    st.subheader(f"Editar lançamentos — {kind}")

    state_key = f"movements_grid_{uid}_{kind}"
    saved_key = f"movements_saved_{uid}_{kind}"

    def load_rows():
        return [
            row
            for row in store.movements(uid)
            if row["tipo"] == kind
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

    df["ordem"] = df["ordem"].astype("Int64")

    for column in columns:
        if column != "ordem":
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
        "data": st.column_config.TextColumn(
            "Data (AAAA-MM-DD)",
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
        key=(
            f"movements_editor_{uid}_{kind}_"
            f"{state['revision']}"
        ),
        hide_index=True,
        num_rows="fixed",
        disabled=["id"],
        column_config=config,
    )

    visible_rows = (
        edited_df.astype(object)
        .where(pd.notna(edited_df), None)
        .to_dict("records")
    )

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
            store.update_movements_grid(
                uid, kind, original, edited
            )

        except ValueError as exc:
            st.warning(str(exc))

        else:
            state["original"] = load_rows()
            state["revision"] += 1
            st.session_state[saved_key] = True
            st.rerun()

    if st.session_state.pop(saved_key, False):
        st.success("Lançamentos atualizados.")