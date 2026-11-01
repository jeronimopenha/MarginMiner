import streamlit as st

from common.common import get_store

def login_screen():
    if "user" not in st.session_state:
        store = get_store()
        with st.form("login"):
            login = st.text_input("Login")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                user = store.authenticate(login, password)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Login ou senha incorretos.")
        st.stop()
