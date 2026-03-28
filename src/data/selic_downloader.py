from __future__ import annotations

from datetime import date
import pandas as pd
import requests


class SelicDownloader:
    """
    Baixa a série histórica da SELIC anualizada diária a partir do SGS/BCB.

    Saída padrão:
        Date          datetime64[ns]
        selic_annual  float   # ex.: 0.1325 para 13,25%
    """

    SGS_SERIES_ID = 11  # taxa Selic diária anualizada (% a.a.)

    @staticmethod
    def _format_bcb_date(dt: date) -> str:
        return dt.strftime("%d/%m/%Y")

    @classmethod
    def build_url(cls, start_date: date, end_date: date) -> str:
        data_inicial = cls._format_bcb_date(start_date)
        data_final = cls._format_bcb_date(end_date)
        return (
            f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cls.SGS_SERIES_ID}/dados"
            f"?formato=json&dataInicial={data_inicial}&dataFinal={data_final}"
        )

    @classmethod
    def download(
        cls,
        start_date: date,
        end_date: date,
        timeout: int = 30,
    ) -> pd.DataFrame:
        url = cls.build_url(start_date, end_date)
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()

        data = resp.json()
        if not data:
            return pd.DataFrame(columns=["Date", "selic_annual"])

        df = pd.DataFrame(data)

        # Esperado do BCB:
        # data: "31/01/2024"
        # valor: "11.25"
        df["Date"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")

        # Converte para decimal: 11.25 -> 0.1125
        df["selic_annual"] = (
            pd.to_numeric(
                df["valor"].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            ) / 100.0
        )

        df = df[["Date", "selic_annual"]].dropna().sort_values("Date").reset_index(drop=True)
        return df