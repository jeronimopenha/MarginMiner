from datetime import date
import sqlite3
import pandas as pd
import streamlit as st
from core import Store, TYPES, FIELDS, csv_bytes, parse_csv, history, replay

from screens.first_access_screen import first_access_screen
from screens.login_screen import login_screen
from screens.assets_screen import assets_screen


def attempt(fn):
    try:
        fn()
        st.success("Dados salvos.")
    except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        st.error(str(exc))


def main():
    st.set_page_config(page_title="Minha carteira", layout="wide")
    store = Store()
    st.title("Margin Miner")

    first_access_screen(store)
    login_screen()

    uid = st.session_state.user["id"]
    st.sidebar.write(st.session_state.user["name"])
    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()
    page = st.sidebar.radio(
        "Navegação",
        [
            "Resumo e cotização",
            "Ativos",
            "Lançamentos",
            "Cotações",
            "Importar e exportar",
        ],
    )
    assets = store.assets(uid)
    tickers = [a["ticker"] for a in assets]
    rows = store.movements(uid)

    if page == "Ativos":
        assets_screen()

    elif page == "Lançamentos":
        allowed = {
            "COMPRA": {"quantidade", "preco", "taxas"},
            "VENDA": {"quantidade", "preco", "taxas"},
            "BONIFICACAO": {"quantidade"},
            "DESDOBRAMENTO": {"fator"},
            "GRUPAMENTO": {"fator"},
        }
        st.subheader("Novo lançamento")
        st.info(
            "Cadastre os aportes antes das compras. Valor recebido é o total líquido, não por ação. Ordem define a sequência dentro do dia."
        )
        kind = st.selectbox("Tipo", TYPES)
        with st.form("movement"):
            day = st.date_input("Data", max_value=date.today())
            order = st.number_input(
                "Ordem no dia (não repetir)",
                min_value=1,
                value=max([r["ordem"] for r in rows] + [0]) + 1,
            )
            ticker = st.selectbox(
                "Ativo", [""] + tickers, disabled=kind in ("APORTE", "RETIRADA", "TAXA")
            )
            if kind in ("APORTE", "RETIRADA", "TAXA"):
                ticker = ""
            q = st.text_input(
                "Quantidade adicional (compra, venda ou bonificação)", "0"
            )
            p = st.text_input("Preço unitário (compra/venda)", "0")
            vb = st.text_input(
                "Valor total bruto (aportes, retiradas, rendimentos, amortização ou liquidação)",
                "0",
            )
            vl = st.text_input(
                "Valor total líquido (aportes, retiradas, rendimentos, amortização ou liquidação)",
                "0",
            )
            fees = st.text_input("Taxas da compra/venda", "0")
            factor = st.text_input(
                "Fator de quantidade (desdobramento: 2; grupamento 10:1: 0,1)", "1"
            )
            note = st.text_input("Observação")
            if st.form_submit_button("Salvar lançamento"):
                attempt(
                    lambda: store.save_movements(
                        uid,
                        [
                            dict(
                                data=day.isoformat(),
                                ordem=order,
                                tipo=kind,
                                ticker=ticker,
                                quantidade=q,
                                preco=p,
                                valor_bruto=vb,
                                valor_liquido=vl,
                                taxas=fees,
                                fator=factor,
                                observacao=note,
                            )
                        ],
                    )
                )
        st.caption(
            "Liquidação: encerra toda a posição e credita o valor total recebido. Amortização: credita caixa sem alterar a quantidade. Bonificação não calcula custo fiscal nesta versão."
        )
        rows = store.movements(uid)
        st.dataframe(rows, hide_index=True)
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

    elif page == "Cotações":
        st.subheader("Cotações de fechamento")
        st.warning(
            "Use preços históricos sem ajuste por dividendos nem por desdobramentos. Os eventos são registrados separadamente. Séries ajustadas por desdobramentos também distorcem a posição histórica se usadas diretamente."
        )
        if tickers:
            with st.form("quote"):
                ticker = st.selectbox("Ativo", tickers)
                day = st.date_input("Data da cotação", max_value=date.today())
                close = st.text_input("Fechamento em BRL")
                if st.form_submit_button("Salvar / atualizar cotação"):
                    attempt(
                        lambda: store.save_quotes(
                            uid,
                            [dict(ticker=ticker, date=day.isoformat(), close=close)],
                        )
                    )
        st.dataframe(store.quotes(uid), hide_index=True)
        st.caption(
            "Coleta automática via Yahoo ainda não implementada; importe CSV ou cadastre o preço. Histórico maior nunca é apagado ao consultar períodos menores."
        )

    elif page == "Importar e exportar":
        st.subheader("Seus dados")
        st.download_button(
            "Exportar tudo (JSON, sem senha)",
            store.export(uid),
            "carteira.json",
            "application/json",
        )
        st.download_button(
            "Exportar lançamentos CSV", csv_bytes(rows), "movimentacoes.csv", "text/csv"
        )
        st.download_button(
            "Modelo CSV de lançamentos",
            csv_bytes([]),
            "modelo_movimentacoes.csv",
            "text/csv",
        )
        st.download_button(
            "Exportar cotações CSV",
            csv_bytes(store.quotes(uid), ["ticker", "date", "close"]),
            "cotacoes.csv",
            "text/csv",
        )
        st.caption(
            "CSV: UTF-8, separador ponto e vírgula, data AAAA-MM-DD. Use os cabeçalhos dos modelos. IDs vazios geram novos lançamentos; preserve IDs para reimportar sem duplicar. Cadastre os ativos antes de importar CSV."
        )
        kind = st.selectbox(
            "Conteúdo",
            ["Lançamentos CSV", "Cotações CSV", "Restaurar JSON em conta vazia"],
        )
        uploaded = st.file_uploader("Arquivo", type=["csv", "json"])
        if uploaded is not None:
            try:
                content = uploaded.getvalue()
                if kind.endswith("CSV"):
                    st.dataframe(parse_csv(content))
                if st.button("Importar arquivo"):
                    if kind == "Lançamentos CSV":
                        attempt(lambda: store.save_movements(uid, parse_csv(content)))
                    elif kind == "Cotações CSV":
                        attempt(lambda: store.save_quotes(uid, parse_csv(content)))
                    else:
                        attempt(lambda: store.restore(uid, content))
            except (ValueError, UnicodeError) as exc:
                st.error(str(exc))

    else:
        st.subheader("Posição e rentabilidade por cotização")
        st.caption(
            "BRL · posição comprada · sem alavancagem. Sem cálculo de imposto ou custo médio fiscal."
        )
        if not rows:
            st.info(
                "Comece cadastrando um ativo e um aporte. Depois registre compras e cotações."
            )
        else:
            try:
                cash, pos = replay(rows)
                st.metric("Saldo disponível", f"R$ {cash:,.2f}")
                st.dataframe(
                    [{"ativo": a, "quantidade": str(q)} for a, q in pos.items() if q],
                    hide_index=True,
                )
                end = st.date_input(
                    "Calcular até", value=date.today(), max_value=date.today()
                )
                st.info(
                    "Convenção: aportes e retiradas no início do dia, emitindo/resgatando cotas pelo valor da cota anterior. Não representa TWR intradiário exato. Dias sem negociação usam o último preço conhecido."
                )
                hist = history(rows, store.quotes(uid), end)
                if hist:
                    df = pd.DataFrame(hist).set_index("data")
                    st.metric(
                        "Patrimônio no fim do período",
                        f"R$ {df.iloc[-1]['patrimonio']:,.2f}",
                    )
                    st.metric(
                        "Retorno por cotização",
                        f"{df.iloc[-1]['retorno_acumulado_pct']:.2f}%",
                    )
                    st.line_chart(df[["valor_cota"]])
                    if df["cotacao_antiga"].str.len().any():
                        st.warning(
                            "Há dias com cotações de mais de 7 dias atrás. Confira a coluna cotacao_antiga."
                        )
                    st.dataframe(df)
                    st.download_button(
                        "Exportar série diária",
                        df.to_csv(sep=";").encode("utf-8-sig"),
                        "cotizacao.csv",
                        "text/csv",
                    )
                else:
                    st.info("Não há lançamentos até essa data.")
            except ValueError as exc:
                st.warning(str(exc))


if __name__ == "__main__":
    main()
