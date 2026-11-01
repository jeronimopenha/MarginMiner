import streamlit as st
from common.common import attempt, get_store


def page_ativos(uid):
    store = get_store()
    
    st.subheader("Cadastrar ativo")
    st.caption(
        "Primeira versão: valores e cotações em BRL. Use o mesmo identificador nos arquivos importados."
    )
    with st.form("asset"):
        ticker = st.text_input("Ticker / identificador")
        name = st.text_input("Nome do ativo")
        category = st.selectbox(
            "Categoria", ["Ação", "FII", "ETF", "Renda fixa", "Cripto", "Outro"]
        )
        if st.form_submit_button("Cadastrar"):
            attempt(lambda: store.asset(uid, ticker, name, category))
    st.dataframe(store.assets(uid), hide_index=True)
