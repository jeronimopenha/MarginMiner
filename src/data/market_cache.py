from pathlib import Path
import pandas as pd

from src.util import Util


class MarketCache:
    @staticmethod
    def get_base_dir() -> Path:
        path = Path(Util.get_data_dir()) / "cache" / "market"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def normalize_ticker(ticker: str) -> str:
        return str(ticker).upper().strip()

    @staticmethod
    def get_path(ticker: str) -> Path:
        ticker = MarketCache.normalize_ticker(ticker)
        return MarketCache.get_base_dir() / f"{ticker}.parquet"

    @staticmethod
    def exists(ticker: str) -> bool:
        return MarketCache.get_path(ticker).exists()

    @staticmethod
    def load(ticker: str) -> pd.DataFrame:
        path = MarketCache.get_path(ticker)
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(path)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.sort_values("Date").drop_duplicates(subset=["Date"])
        return df

    @staticmethod
    def save(ticker: str, df: pd.DataFrame):
        if df is None or df.empty:
            return

        out = df.copy()

        if "Date" in out.columns:
            out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
            out = out.dropna(subset=["Date"])
            out = out.sort_values("Date").drop_duplicates(subset=["Date"])

        out.to_parquet(MarketCache.get_path(ticker), index=False)

    @staticmethod
    def get_last_date(ticker: str):
        df = MarketCache.load(ticker)
        if df.empty or "Date" not in df.columns:
            return None
        return df["Date"].max()

    def load_indexed(self, ticker: str) -> pd.DataFrame:
        df = self.load(ticker)
        if df.empty:
            try:
                # return pd.DataFrame(columns=["selic_annual"])
                df = self.update()
                return df.set_index("Date").sort_index()
            except Exception as e:
                print(f"Erro ao atualizar SELIC: {e}")
                exit(1)
            # return pd.DataFrame(columns=["selic_annual"])

        return df.set_index("Date").sort_index()