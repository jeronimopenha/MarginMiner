import pandas as pd
import streamlit as st

from common.common import get_store
from common.constants import categories


def assets_screen(uid):
    st.subheader("Ativos")

    tabs = st.tabs(categories)

    for category, tab in zip(categories, tabs):
        with tab:
            assets_grid(uid, category)


def assets_grid(uid, category):
    store = get_store()
    
    state_key = f"assets_grid_{uid}_{category}"
    saved_key = f"assets_saved_{uid}_{category}"

    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "original": store.assets_for_edit(uid, category),
            "revision": 0,
        }

    state = st.session_state[state_key]

    if st.button(
        "Recarregar do banco — descarta edições pendentes",
        key=f"reload_assets_{uid}_{category}",
    ):
        state["original"] = store.assets_for_edit(uid, category)
        state["revision"] += 1

    original = state["original"]

    # A categoria não precisa aparecer na grade:
    # ela é determinada pela aba.
    df = pd.DataFrame(
        original,
        columns=["id", "ticker", "name"],
    )

    df["id"] = df["id"].astype("Int64")

    for column in ["ticker", "name"]:
        df[column] = df[column].astype("string")

    edited_df = st.data_editor(
        df,
        key=(f"assets_editor_{uid}_{category}_" f"{state['revision']}"),
        hide_index=True,
        num_rows="dynamic",
        disabled=["id"],
        column_config={
            "id": None,
            "ticker": st.column_config.TextColumn(
                "Ticker / identificador",
                required=True,
            ),
            "name": st.column_config.TextColumn(
                "Nome",
                required=True,
            ),
        },
    )

    st.caption(
        f"Categoria: {category}. Salvamento automático. "
        "Mantenha o ticker dos ativos existentes. "
        "Ativos com lançamentos ou cotações não podem ser excluídos."
    )

    edited = (
        edited_df.astype(object).where(pd.notna(edited_df), None).to_dict("records")
    )

    # Recoloca a categoria para comparar com o estado original.
    edited_with_category = [{**row, "category": category} for row in edited]

    if edited_with_category != original:
        try:
            store.save_assets_grid(
                uid,
                category,
                original,
                edited,
            )

        except ValueError as exc:
            st.warning(str(exc))

        else:
            state["original"] = store.assets_for_edit(uid, category)
            state["revision"] += 1
            st.session_state[saved_key] = True
            st.rerun()

    if st.session_state.pop(saved_key, False):
        st.success("Alterações salvas.")
