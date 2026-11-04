from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from datetime import datetime

import pandas as pd
import yfinance as yf
import streamlit as st

from common.common import get_store

SUPPORTED_CATEGORIES = {"Ação", "FII", "ETF"}


def fetch_missing_quotes(
    asset,
    movements,
    saved_quotes,
    review=False,
):
    store = get_store()
    uid = st.session_state.user["id"]
    
    ticker = asset["ticker"]

    dates = [
        date.fromisoformat(row["data"]) for row in movements if row["ticker"] == ticker
    ]

    if not dates:
        return 0, "Sem movimentações; coleta não iniciada."

    first_date = min(dates)

    # Usa dias completos. Não grava uma cotação intradiária
    # como se ela já fosse o fechamento definitivo.
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    last_date = today - timedelta(days=1)

    if first_date > last_date:
        return 0, "Ainda não há dia encerrado para buscar."

    existing = {
        date.fromisoformat(row["date"])
        for row in saved_quotes
        if row["ticker"] == ticker
        and first_date <= date.fromisoformat(row["date"]) <= last_date
    }

    if review or not existing:
        start = first_date

    elif first_date < min(existing):
        # Uma movimentação retroativa ampliou o histórico.
        start = first_date

    else:
        start = max(existing) + timedelta(days=1)

    if start > last_date:
        return 0, "Sem período novo para consultar."

    symbol = ticker if ticker.endswith(".SA") else f"{ticker}.SA"
    instrument = yf.Ticker(symbol)

    # Inclui hoje na consulta para considerar eventual
    # desdobramento de hoje, mas não salva o preço de hoje.
    # O parâmetro end é exclusivo.
    frame = instrument.history(
        start=start.isoformat(),
        end=(today + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=False,
        actions=True,
        keepna=True,
        raise_errors=True,
    )

    if frame.empty:
        return 0, "Yahoo não retornou dados para o período."

    if "Close" not in frame or "Stock Splits" not in frame:
        raise ValueError(
            "Yahoo não retornou fechamento e eventos "
            "necessários para tratar os desdobramentos."
        )

    metadata = instrument.get_history_metadata()

    if metadata.get("currency") != "BRL":
        raise ValueError(
            f"A moeda retornada para {symbol} não foi confirmada "
            "como BRL. Nenhuma cotação foi salva."
        )

    frame = frame.sort_index()

    factor = Decimal("1")
    quotes = []

    # Percorre do dia mais recente para o mais antigo.
    # O fator de um split vale para os dias anteriores ao evento.
    for timestamp, row in frame.iloc[::-1].iterrows():
        day = timestamp.date()
        close = row["Close"]

        if first_date <= day <= last_date and day not in existing and pd.notna(close):
            price = Decimal(str(close)) * factor

            if price.is_finite() and price > 0:
                quotes.append(
                    {
                        "ticker": ticker,
                        "date": day.isoformat(),
                        "close": str(price),
                    }
                )

        split = row["Stock Splits"]

        if pd.notna(split):
            split_factor = Decimal(str(split))

            if not split_factor.is_finite() or split_factor < 0:
                raise ValueError(f"Fator de desdobramento inválido em {day}.")

            if split_factor > 0:
                factor *= split_factor

    if quotes:
        store.save_quotes(uid, quotes)

    return len(quotes), (f"{len(quotes)} fechamento(s) novo(s) salvo(s).")
