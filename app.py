from datetime import date
import pandas as pd
import streamlit as st

from common.core import csv_bytes, parse_csv, history, replay
from common.common import attempt, get_store
from screens.first_access_screen import first_access_screen
from screens.login_screen import login_screen
from screens.assets_screen import assets_screen
from screens.movements import movements_screen
from screens.quotes_screen import quotes_screen


def main():
    st.set_page_config(page_title="Minha carteira", layout="wide")
    st.title("Margin Miner")

    store = get_store()

    # first user access page
    first_access_screen()

    # login page
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
    st.session_state.user["assets"] = store.assets(uid)
    assets = st.session_state.user["assets"]
    
    st.session_state.user["tickers"] =  [a["ticker"] for a in assets]
    tickers =st.session_state.user["tickers"]
    
    st.session_state.user["rows"] = store.movements(uid)
    rows = st.session_state.user["rows"]

    if page == "Ativos":
        assets_screen(uid)

    elif page == "Lançamentos":
        movements_screen()

    elif page == "Cotações":
        quotes_screen()

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
