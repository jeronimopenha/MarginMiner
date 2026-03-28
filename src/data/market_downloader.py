from datetime import timedelta
import pandas as pd
import yfinance as yf

from src.data.market_cache import MarketCache
from src.util import Util


class MarketDownloader:
    @staticmethod
    def yahoo_ticker(ticker: str) -> str:
        ticker = str(ticker).upper().strip()
        if not ticker.endswith(".SA"):
            ticker += ".SA"
        return ticker

    @staticmethod
    def download_full_history(ticker: str) -> pd.DataFrame:
        yticker = MarketDownloader.yahoo_ticker(ticker)
        df = yf.download(
            yticker,
            period="10y",
            # "max",
            auto_adjust=False,
            actions=True,
            progress=False
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.reset_index()

        # achata colunas se vier MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        wanted = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]
        for col in wanted:
            if col not in df.columns:
                if col in ("Dividends", "Stock Splits"):
                    df[col] = 0.0
                else:
                    df[col] = pd.NA

        df = df[wanted].copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        cutoff = pd.Timestamp(Util.years_ago())
        df = df[df["Date"] >= cutoff].reset_index(drop=True)

        return df[wanted].copy()

    @staticmethod
    def update_history(ticker: str) -> pd.DataFrame:
        cached = MarketCache.load(ticker)

        if cached.empty:
            fresh = MarketDownloader.download_full_history(ticker)
            if not fresh.empty:
                MarketCache.save(ticker, fresh)
            return fresh

        last_date = cached["Date"].max()
        if pd.isna(last_date):
            fresh = MarketDownloader.download_full_history(ticker)
            if not fresh.empty:
                MarketCache.save(ticker, fresh)
            return fresh

        start = (pd.Timestamp(last_date) - timedelta(days=5)).date()
        yticker = MarketDownloader.yahoo_ticker(ticker)

        df_new = yf.download(
            yticker,
            start=str(start),
            auto_adjust=False,
            actions=True,
            progress=False
        )

        if df_new is None or df_new.empty:
            return cached

        df_new = df_new.reset_index()

        if isinstance(df_new.columns, pd.MultiIndex):
            df_new.columns = [c[0] if isinstance(c, tuple) else c for c in df_new.columns]

        wanted = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]
        for col in wanted:
            if col not in df_new.columns:
                if col in ("Dividends", "Stock Splits"):
                    df_new[col] = 0.0
                else:
                    df_new[col] = pd.NA

        merged = pd.concat([cached, df_new[wanted]], ignore_index=True)
        merged["Date"] = pd.to_datetime(merged["Date"], errors="coerce")
        merged = merged.dropna(subset=["Date"])
        merged = merged.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")

        MarketCache.save(ticker, merged)
        return merged
