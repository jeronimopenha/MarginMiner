import streamlit as st
import sqlite3

from common.core import Store

store = Store()


def get_store():
    return store


def attempt(fn):
    try:
        fn()
        st.success("Dados salvos.")
    except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        st.error(str(exc))
