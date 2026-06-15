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

        out["growth_factor"] = ((out["Close"] + out["Dividends"]) / out["Close"].shift(1)).fillna(1.0)
        out["total_return_daily"] = out["growth_factor"] - 1.0
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

        gf = pd.to_numeric(df["growth_factor"], errors="coerce").dropna()
        if len(gf) < 2:
            return None

        return gf.prod() - 1.0
        '''if df is None or df.empty or len(df) < 2:
            return None
        start = df["cum_total_return"].iloc[0]
        end = df["cum_total_return"].iloc[-1]
        if pd.isna(start) or pd.isna(end) or start == 0:
            return None
        return (end / start) - 1.0'''

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

        # print("rf_annual:", rf_annual)
        # print("mean r:", r.mean())
        # print("rf_daily:", rf_daily)
        # print("mean excess:", excess.mean())

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

    @staticmethod
    def average_rf_annual_for_window(wdf: pd.DataFrame, selic_df: pd.DataFrame) -> float:
        if wdf is None or wdf.empty or len(wdf) < 2:
            return 0.0

        if selic_df is None or selic_df.empty:
            return 0.0

        start = pd.to_datetime(wdf["Date"].min(), errors="coerce")
        end = pd.to_datetime(wdf["Date"].max(), errors="coerce")

        if pd.isna(start) or pd.isna(end):
            return 0.0

        sdf = selic_df.copy()

        if "Date" in sdf.columns:
            sdf["Date"] = pd.to_datetime(sdf["Date"], errors="coerce")
        else:
            sdf = sdf.reset_index()
            sdf["Date"] = pd.to_datetime(sdf["Date"], errors="coerce")

        if "selic_annual" not in sdf.columns:
            return 0.0

        sdf["selic_annual"] = pd.to_numeric(sdf["selic_annual"], errors="coerce")

        sdf = sdf.dropna(subset=["Date", "selic_annual"])
        sdf = sdf[(sdf["Date"] >= start) & (sdf["Date"] <= end)]

        if sdf.empty:
            return 0.0

        daily = pd.to_numeric(sdf["selic_annual"], errors="coerce").dropna()

        if len(daily) < 2:
            return 0.0

        growth = (1.0 + daily).prod()
        eq_daily = growth ** (1.0 / len(daily)) - 1.0
        eq_annual = (1.0 + eq_daily) ** 252.0 - 1.0

        if pd.isna(eq_annual) or eq_annual <= 0:
            return 0.0

        return float(eq_annual)

    @staticmethod
    def calmar(cagr, mdd):
        if cagr is None or mdd is None or mdd == 0:
            return None

        return cagr / abs(mdd)

    @staticmethod
    def sortino(df: pd.DataFrame, rf_annual=0.0):
        if df is None or df.empty or len(df) < 2:
            return None

        r = pd.to_numeric(df["total_return_daily"], errors="coerce").dropna()
        if len(r) < 2:
            return None

        # converte RF anual -> diário
        rf_daily = (1.0 + rf_annual) ** (1.0 / 252.0) - 1.0

        excess = r - rf_daily

        # 🔥 só downside
        downside = excess[excess < 0]

        if len(downside) < 2:
            return None

        downside_std = downside.std(ddof=1)

        if downside_std == 0 or pd.isna(downside_std):
            return None

        return (excess.mean() / downside_std) * (252 ** 0.5)

    @staticmethod
    def beta(asset_df: pd.DataFrame, market_df: pd.DataFrame):
        if asset_df is None or market_df is None:
            return None

        if asset_df.empty or market_df.empty:
            return None

        # alinhar datas
        a = asset_df[["Date", "total_return_daily"]].copy()
        m = market_df[["Date", "total_return_daily"]].copy()

        a["Date"] = pd.to_datetime(a["Date"], errors="coerce")
        m["Date"] = pd.to_datetime(m["Date"], errors="coerce")

        merged = pd.merge(a, m, on="Date", how="inner", suffixes=("_a", "_m"))

        if merged.empty or len(merged) < 2:
            return None

        ra = pd.to_numeric(merged["total_return_daily_a"], errors="coerce")
        rm = pd.to_numeric(merged["total_return_daily_m"], errors="coerce")

        ra = ra.dropna()
        rm = rm.dropna()

        if len(ra) < 2 or len(rm) < 2:
            return None

        cov = ra.cov(rm)
        var = rm.var()

        if var == 0 or pd.isna(var):
            return None

        return cov / var

    @staticmethod
    def alpha(asset_df: pd.DataFrame, market_df: pd.DataFrame, rf_annual):
        if asset_df is None or market_df is None or rf_annual is None:
            return None

        if asset_df.empty or market_df.empty:
            return None

        asset_return = FiiMetrics.cagr(asset_df)
        market_return = FiiMetrics.cagr(market_df)
        beta = FiiMetrics.beta(asset_df, market_df)

        if asset_return is None or market_return is None or beta is None:
            return None

        if pd.isna(asset_return) or pd.isna(market_return) or pd.isna(beta):
            return None

        return asset_return - (rf_annual + beta * (market_return - rf_annual))

    @staticmethod
    def tracking_error(asset_df: pd.DataFrame, market_df: pd.DataFrame):
        if asset_df is None or market_df is None:
            return None
        if asset_df.empty or market_df.empty:
            return None

        a = asset_df[["Date", "total_return_daily"]].copy()
        m = market_df[["Date", "total_return_daily"]].copy()

        a["Date"] = pd.to_datetime(a["Date"], errors="coerce")
        m["Date"] = pd.to_datetime(m["Date"], errors="coerce")

        merged = pd.merge(a, m, on="Date", how="inner", suffixes=("_a", "_m"))
        if len(merged) < 2:
            return None

        ra = pd.to_numeric(merged["total_return_daily_a"], errors="coerce")
        rm = pd.to_numeric(merged["total_return_daily_m"], errors="coerce")

        diff = (ra - rm).dropna()
        if len(diff) < 2:
            return None

        return diff.std(ddof=1) * (252 ** 0.5)

    @staticmethod
    def information_ratio(asset_df: pd.DataFrame, market_df: pd.DataFrame):
        if asset_df is None or market_df is None:
            return None
        if asset_df.empty or market_df.empty:
            return None

        a = asset_df[["Date", "total_return_daily"]].copy()
        m = market_df[["Date", "total_return_daily"]].copy()

        a["Date"] = pd.to_datetime(a["Date"], errors="coerce")
        m["Date"] = pd.to_datetime(m["Date"], errors="coerce")

        merged = pd.merge(a, m, on="Date", how="inner", suffixes=("_a", "_m"))
        if len(merged) < 2:
            return None

        ra = pd.to_numeric(merged["total_return_daily_a"], errors="coerce")
        rm = pd.to_numeric(merged["total_return_daily_m"], errors="coerce")

        diff = (ra - rm).dropna()
        if len(diff) < 2:
            return None

        te = diff.std(ddof=1)
        if te == 0 or pd.isna(te):
            return None

        return (diff.mean() / te) * (252 ** 0.5)

    @staticmethod
    def treynor(asset_df: pd.DataFrame, rf_annual: float, beta: float):
        if asset_df is None or asset_df.empty:
            return None
        if beta is None or beta == 0 or pd.isna(beta):
            return None

        cagr = FiiMetrics.cagr(asset_df)
        if cagr is None or pd.isna(cagr):
            return None

        return (cagr - rf_annual) / beta

    @staticmethod
    def jensen_alpha(asset_df: pd.DataFrame, market_df: pd.DataFrame, rf_annual: float, beta: float):
        if asset_df is None or market_df is None:
            return None
        if asset_df.empty or market_df.empty:
            return None
        if beta is None or pd.isna(beta):
            return None

        ra = FiiMetrics.cagr(asset_df)
        rm = FiiMetrics.cagr(market_df)

        if ra is None or rm is None:
            return None

        return ra - (rf_annual + beta * (rm - rf_annual))