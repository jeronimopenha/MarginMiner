from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path

import pandas as pd
import requests

BCB_SELIC_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados"


def _fetch_selic_bcb(initial_date: date, final_date: date) -> pd.DataFrame:
    params = {
        "formato": "json",
        "dataInicial": initial_date.strftime("%d/%m/%Y"),
        "dataFinal": final_date.strftime("%d/%m/%Y"),
    }

    response = requests.get(BCB_SELIC_URL, params=params, timeout=30)

    # The Central Bank of Brazil (BCB) returns a 404 error when there are no values in the period.
    # Example: weekend or current day not yet published.
    if response.status_code == 404:
        return pd.DataFrame(columns=["date", "selic_day_pct"])

    if not response.ok:
        raise RuntimeError(
            f"Error BCB {response.status_code}: {response.text}\nURL: {response.url}"
        )

    data = response.json()

    if not data:
        return pd.DataFrame(columns=["date", "selic_day_pct"])

    df = pd.DataFrame(data)

    df["date"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["selic_day_pct"] = (
        df["valor"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    df = df[["date", "selic_day_pct"]]
    df = df.sort_values("date").reset_index(drop=True)

    return df


def daily_selic_10y(
        final_date: date | None = None,
        save_as: str | Path = "storage/selic/daily_selic.parquet",
) -> pd.DataFrame:
    """
    Searches/updates the daily Selic rate for the last 10 years.
    If the Parquet already exists:
        - reads the file;
        - deletes data older than 10 years;
        - searches only for the missing delta;
        - joins everything;
        - removes duplicates;
        - saves again.
    """

    if final_date is None:
        final_date = date.today()

    initial_date = final_date - relativedelta(years=10)

    path = Path(save_as)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        df_old = pd.read_parquet(path)

        df_old["date"] = pd.to_datetime(df_old["date"])

        # Remove data older than the desired window
        df_old = df_old[df_old["date"] >= pd.Timestamp(initial_date)]

        if not df_old.empty:
            last_saved_date = df_old["date"].max().date()
            delta_initial_date = last_saved_date + timedelta(days=1)
        else:
            delta_initial_date = initial_date

        if delta_initial_date <= final_date:
            df_new = _fetch_selic_bcb(delta_initial_date, final_date)
            df = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df = df_old

    else:
        df = _fetch_selic_bcb(initial_date, final_date)

    # Final guarantees
    df["date"] = pd.to_datetime(df["date"])

    df = df[
        (df["date"] >= pd.Timestamp(initial_date))
        & (df["date"] <= pd.Timestamp(final_date))
        ]

    df = (
        df
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date")
        .reset_index(drop=True)
    )

    df.to_parquet(path, index=False)

    return df

def selic_periods_row(
    final_date: date | None = None,
    parquet_path: str | Path = "storage/selic/daily_selic.parquet",
) -> pd.DataFrame:
    """
    Returns the annualized SELIC rate for periods of 12 months, 3 years, 5 years, and 10 years.

    Format:
        12m | 3A | 5A | 10A
    SELIC
    """

    df = daily_selic_10y(
        final_date=final_date,
        save_as=parquet_path,
    )

    if df.empty:
        return pd.DataFrame(
            [["SELIC", None, None, None, None]],
            columns=["", "12m", "3A", "5A", "10A"],
        )

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    if final_date is None:
        effective_final_date = df["date"].max().date()
    else:
        effective_final_date = min(
            pd.Timestamp(final_date).date(),
            df["date"].max().date(),
        )

    periods = [
        ("12m", 1),
        ("3A", 3),
        ("5A", 5),
        ("10A", 10),
    ]

    row = ["SELIC"]

    for label, years in periods:
        initial_date = effective_final_date - relativedelta(years=years)

        df_period = df[
            (df["date"] >= pd.Timestamp(initial_date))
            & (df["date"] <= pd.Timestamp(effective_final_date))
        ]

        if df_period.empty:
            row.append(None)
            continue

        factor = (1 + df_period["selic_day_pct"] / 100).prod()

        annualized = factor ** (1 / years) - 1

        row.append(annualized)

    return pd.DataFrame(
        [row],
        columns=["", "12m", "3A", "5A", "10A"],
    )