import pandas as pd
import streamlit as st

from common.common import get_store
from common.constants import categories
from common.market_data import (
    SUPPORTED_CATEGORIES,
    fetch_missing_quotes,
)


def quotes_screen():
    store = get_store()
    uid = st.session_state.user["id"]

    assets = store.assets(uid)
    movements = store.movements(uid)

    st.subheader("Cotações de fechamento")
    st.caption(
        "Atualização até o último dia encerrado. "
        "Datas sem fechamento válido não são gravadas."
    )

    tabs = st.tabs(list(categories))

    for category, tab in zip(categories, tabs):
        with tab:
            category_assets = [
                asset for asset in assets if asset["category"] == category
            ]

            if not category_assets:
                st.info("Nenhum ativo cadastrado nesta categoria.")
                continue

            if category in SUPPORTED_CATEGORIES:
                review = st.checkbox(
                    "Revisar lacunas desde a primeira movimentação",
                    key=f"review_quotes_{uid}_{category}",
                    help=(
                        "Consulta novamente o período completo, "
                        "mas salva apenas datas ainda ausentes."
                    ),
                )

                if st.button(
                    "Atualizar cotações desta categoria",
                    key=f"update_quotes_{uid}_{category}",
                ):
                    saved = store.quotes(uid)

                    with st.spinner("Consultando Yahoo Finance..."):
                        for asset in category_assets:
                            ticker = asset["ticker"]

                            try:
                                count, message = fetch_missing_quotes(
                                    store=store,
                                    uid=uid,
                                    asset=asset,
                                    movements=movements,
                                    saved_quotes=saved,
                                    review=review,
                                )

                            except Exception as exc:
                                # Uma falha de rede ou de um ativo
                                # não impede atualizar os demais.
                                st.error(f"{ticker}: {exc}")

                            else:
                                st.write(f"{ticker}: {message}")

            else:
                st.info(
                    "Coleta automática ainda não implementada " "para esta categoria."
                )

            tickers = {asset["ticker"] for asset in category_assets}

            quotes = [row for row in store.quotes(uid) if row["ticker"] in tickers]

            df = pd.DataFrame(
                quotes,
                columns=["ticker", "date", "close"],
            )

            st.dataframe(df, hide_index=True)
