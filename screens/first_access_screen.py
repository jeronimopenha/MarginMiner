import sqlite3
import streamlit as st

from common.common import get_store


def first_access_screen():
    store = get_store()
    
    if store.rows("SELECT id FROM users LIMIT 1"):
        return

    st.subheader("Primeiro acesso — crie sua conta")

    with st.form("setup"):
        name = st.text_input("Nome")
        login = st.text_input("Login")
        password = st.text_input(
            "Senha (mínimo 10 caracteres)",
            type="password",
        )
        repeat = st.text_input("Repita a senha", type="password")

        if st.form_submit_button("Criar conta"):
            if password != repeat:
                st.error("As senhas não coincidem.")
            else:
                try:
                    store.create_user(login, name, password)
                    st.rerun()
                except (ValueError, sqlite3.Error) as exc:
                    st.error(str(exc))

    st.stop()
