from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import pandas as pd

from src.data.selic_downloader import SelicDownloader
from src.util import Util


@dataclass
class SelicCache:

    @property
    def cache_dir(self) -> Path:
        return Util.get_data_dir("cache/macro")

    @property
    def parquet_path(self) -> Path:
        return self.cache_dir / "selic.parquet"

    def ensure_cache_dir(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> pd.DataFrame:
        path = self.parquet_path
        if not path.exists():
            return pd.DataFrame(columns=["Date", "selic_annual"])

        try:
            df = pd.read_parquet(path)
        except Exception:
            return pd.DataFrame(columns=["Date", "selic_annual"])

        if df.empty:
            return pd.DataFrame(columns=["Date", "selic_annual"])

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["selic_annual"] = pd.to_numeric(df["selic_annual"], errors="coerce")

        df = (
            df[["Date", "selic_annual"]]
            .dropna()
            .drop_duplicates(subset=["Date"])
            .sort_values("Date")
            .reset_index(drop=True)
        )
        return df

    def save(self, df: pd.DataFrame) -> None:
        self.ensure_cache_dir()

        out = df.copy()
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
        out["selic_annual"] = pd.to_numeric(out["selic_annual"], errors="coerce")

        out = (
            out[["Date", "selic_annual"]]
            .dropna()
            .drop_duplicates(subset=["Date"])
            .sort_values("Date")
            .reset_index(drop=True)
        )

        out.to_parquet(self.parquet_path, index=False)

    def update(
            self,
            start_date: date | None = None,
            end_date: date | None = None,
    ) -> pd.DataFrame:
        if end_date is None:
            end_date = date.today()

        if start_date is None:
            start_date = Util.years_ago(end_date)

        old_df = self.load()
        new_df = SelicDownloader.download(start_date=start_date, end_date=end_date)

        if old_df.empty:
            merged = new_df
        elif new_df.empty:
            merged = old_df
        else:
            merged = pd.concat([old_df, new_df], ignore_index=True)
            merged["Date"] = pd.to_datetime(merged["Date"], errors="coerce")
            merged["selic_annual"] = pd.to_numeric(merged["selic_annual"], errors="coerce")
            merged = (
                merged[["Date", "selic_annual"]]
                .dropna()
                .drop_duplicates(subset=["Date"], keep="last")
                .sort_values("Date")
                .reset_index(drop=True)
            )

        cutoff = pd.Timestamp(start_date)
        merged = merged[merged["Date"] >= cutoff].reset_index(drop=True)

        self.save(merged)
        return merged

    def load_indexed(self) -> pd.DataFrame:
        df = self.load()
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
