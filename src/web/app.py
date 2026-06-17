import streamlit as st

from src.web.common import PROJECT_ROOT
from src.web.pages.dashboard import render_dashboard_page
from src.web.pages.ranking import render_ranking_page
from src.web.pages.asset import render_asset_page
from src.web.pages.valuation import render_valuation_page
from src.web.pages.local_data import render_local_data_page


st.set_page_config(
    page_title="Margin Miner",
    page_icon="📊",
    layout="wide",
)


def render_sidebar():
    st.sidebar.title("Margin Miner")

    page = st.sidebar.radio(
        "Menu",
        [
            "Dashboard",
            "Ranking",
            "Ativo",
            "Valuation",
            "Dados locais",
        ],
    )

    st.sidebar.divider()

    ticker = st.sidebar.text_input(
        "Ticker para análise",
        value="ITSA4",
    ).strip().upper()

    return page, ticker


def main():
    page, ticker = render_sidebar()

    if page == "Dashboard":
        render_dashboard_page()

    elif page == "Ranking":
        render_ranking_page()

    elif page == "Ativo":
        render_asset_page(ticker)

    elif page == "Valuation":
        render_valuation_page(ticker)

    elif page == "Dados locais":
        render_local_data_page()


if __name__ == "__main__":
    main()