import math
import pandas as pd


class FiiMetrics:
    @staticmethod
    def prepare_total_return_df(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        out = df.copy()
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
        out = out.dropna(subset=["Date"]).sort_values("Date").copy()

        for col in ["Close", "Dividends"]:
            if col not in out.columns:
                out[col] = 0.0

        out["Close"] = pd.to_numeric(out["Close"], errors="coerce")
        out["Dividends"] = pd.to_numeric(out["Dividends"], errors="coerce").fillna(0.0)

        out = out.dropna(subset=["Close"]).copy()

        out["cash_return"] = out["Close"].pct_change().fillna(0.0)
        out["div_yield_daily"] = (out["Dividends"] / out["Close"].shift(1)).replace([pd.NA], 0.0)
        out["div_yield_daily"] = out["div_yield_daily"].fillna(0.0)

        out["total_return_daily"] = out["cash_return"] + out["div_yield_daily"]
        out["growth_factor"] = 1.0 + out["total_return_daily"]
        out["cum_total_return"] = out["growth_factor"].cumprod()

        return out

    @staticmethod
    def window_slice(df: pd.DataFrame, years=None, months=None) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        end = df["Date"].max()
        start = end

        if years is not None:
            start = end - pd.DateOffset(years=years)
        elif months is not None:
            start = end - pd.DateOffset(months=months)
        else:
            return df.copy()

        sliced = df[df["Date"] >= start].copy()
        return sliced

    @staticmethod
    def total_return(df: pd.DataFrame):
        if df is None or df.empty or len(df) < 2:
            return None
        start = df["cum_total_return"].iloc[0]
        end = df["cum_total_return"].iloc[-1]
        if pd.isna(start) or pd.isna(end) or start == 0:
            return None
        return (end / start) - 1.0

    @staticmethod
    def cagr(df: pd.DataFrame):
        if df is None or df.empty or len(df) < 2:
            return None

        total_ret = FiiMetrics.total_return(df)
        if total_ret is None:
            return None

        days = (df["Date"].iloc[-1] - df["Date"].iloc[0]).days
        if days <= 0:
            return None

        years = days / 365.25
        if years <= 0:
            return None

        return (1.0 + total_ret) ** (1.0 / years) - 1.0

    @staticmethod
    def volatility_annualized(df: pd.DataFrame):
        if df is None or df.empty or len(df) < 2:
            return None

        r = pd.to_numeric(df["total_return_daily"], errors="coerce").dropna()
        if len(r) < 2:
            return None

        return r.std(ddof=1) * math.sqrt(252)

    @staticmethod
    def sharpe(df: pd.DataFrame, rf_annual=0.0):
        if df is None or df.empty or len(df) < 2:
            return None

        r = pd.to_numeric(df["total_return_daily"], errors="coerce").dropna()
        if len(r) < 2:
            return None

        rf_daily = (1.0 + rf_annual) ** (1.0 / 252.0) - 1.0
        excess = r - rf_daily

        std = excess.std(ddof=1)
        if std == 0 or pd.isna(std):
            return None

        return (excess.mean() / std) * math.sqrt(252)

    @staticmethod
    def max_drawdown(df: pd.DataFrame):
        if df is None or df.empty:
            return None

        curve = pd.to_numeric(df["cum_total_return"], errors="coerce").dropna()
        if curve.empty:
            return None

        running_max = curve.cummax()
        drawdown = (curve / running_max) - 1.0
        return drawdown.min()