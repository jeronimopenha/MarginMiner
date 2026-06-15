from datetime import date
from pathlib import Path

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"


from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"


def normalize_brazilian_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()

    if ticker.startswith("^"):
        return ticker

    if "." not in ticker:
        ticker = ticker + ".SA"

    return ticker


def _empty_stock_history() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "financial_volume",
            "dividend",
        ]
    )


def _fetch_stock_history_yahoo(
    ticker: str,
    initial_date: date,
    final_date: date,
    interval: str = "1d",
) -> pd.DataFrame:
    ticker = normalize_brazilian_ticker(ticker)

    period1 = int(pd.Timestamp(initial_date).timestamp())

    # Yahoo usa period2 como limite superior.
    # Somar 1 dia ajuda a incluir a data final.
    period2 = int(pd.Timestamp(final_date + timedelta(days=1)).timestamp())

    url = f"{YAHOO_CHART_URL}/{ticker}"

    params = {
        "period1": period1,
        "period2": period2,
        "interval": interval,
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    if not response.ok:
        raise RuntimeError(
            f"Error Yahoo {response.status_code}: {response.text}\nURL: {response.url}"
        )

    data = response.json()

    chart = data.get("chart", {})
    error = chart.get("error")

    if error is not None:
        raise RuntimeError(f"Error Yahoo: {error}")

    result = chart["result"][0]

    timestamps = result.get("timestamp", [])

    if not timestamps:
        return _empty_stock_history()

    quote = result["indicators"]["quote"][0]

    adjclose_data = (
        result
        .get("indicators", {})
        .get("adjclose", [{}])[0]
        .get("adjclose")
    )

    if adjclose_data is None:
        adjclose_data = [None] * len(timestamps)

    def get_quote_column(name: str) -> list:
        values = quote.get(name)

        if values is None:
            return [None] * len(timestamps)

        return values

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(timestamps, unit="s").normalize(),
            "open": get_quote_column("open"),
            "high": get_quote_column("high"),
            "low": get_quote_column("low"),
            "close": get_quote_column("close"),
            "adj_close": adjclose_data,
            "volume": get_quote_column("volume"),
        }
    )

    df = df.dropna(subset=["close"])
    df["financial_volume"] = df["close"] * df["volume"]

    events = result.get("events", {})
    dividends = events.get("dividends", {})

    if dividends:
        df_dividends = pd.DataFrame(
            [
                {
                    "date": pd.to_datetime(int(timestamp), unit="s").normalize(),
                    "dividend": item.get("amount", 0.0),
                }
                for timestamp, item in dividends.items()
            ]
        )

        df_dividends = (
            df_dividends
            .groupby("date", as_index=False)["dividend"]
            .sum()
        )

        df = df.merge(
            df_dividends,
            on="date",
            how="left",
        )

        df["dividend"] = df["dividend"].fillna(0.0)

    else:
        df["dividend"] = 0.0

    df = (
        df[
            [
                "date",
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
                "financial_volume",
                "dividend",
            ]
        ]
        .sort_values("date")
        .reset_index(drop=True)
    )

    return df


def daily_stock_history(
    ticker: str,
    years: int = 10,
    interval: str = "1d",
    final_date: date | None = None,
    storage_dir: str | Path = "storage/stocks",
    overlap_days: int = 15,
) -> pd.DataFrame:
    """
    Busca/atualiza o histórico diário de preço + dividendos do ativo.

    Se o Parquet já existir:
    - lê o arquivo;
    - remove dados mais antigos que a janela desejada;
    - busca apenas o delta;
    - refaz os últimos 'overlap_days' por segurança;
    - remove duplicatas;
    - salva novamente.
    """

    ticker = normalize_brazilian_ticker(ticker)

    if final_date is None:
        final_date = date.today()

    initial_date = final_date - relativedelta(years=years)

    path = Path(storage_dir) / ticker / "price_history.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        df_old = pd.read_parquet(path)

        df_old["date"] = pd.to_datetime(df_old["date"])

        # Compatibilidade caso o Parquet antigo não tenha alguma coluna nova.
        for col in _empty_stock_history().columns:
            if col not in df_old.columns:
                if col == "dividend":
                    df_old[col] = 0.0
                else:
                    df_old[col] = None

        # Remove dados antigos fora da janela.
        df_old = df_old[df_old["date"] >= pd.Timestamp(initial_date)]

        if df_old.empty:
            delta_initial_date = initial_date
        else:
            last_saved_date = df_old["date"].max().date()

            # Rebusca alguns dias antes para pegar possíveis ajustes/dividendos.
            delta_initial_date = last_saved_date - timedelta(days=overlap_days)

            if delta_initial_date < initial_date:
                delta_initial_date = initial_date

        if delta_initial_date <= final_date:
            df_new = _fetch_stock_history_yahoo(
                ticker=ticker,
                initial_date=delta_initial_date,
                final_date=final_date,
                interval=interval,
            )

            df = pd.concat([df_old, df_new], ignore_index=True)

        else:
            df = df_old

    else:
        df = _fetch_stock_history_yahoo(
            ticker=ticker,
            initial_date=initial_date,
            final_date=final_date,
            interval=interval,
        )

    if df.empty:
        df.to_parquet(path, index=False)
        return df

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

    df = df[
        [
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "financial_volume",
            "dividend",
        ]
    ]

    df.to_parquet(path, index=False)

    return df
