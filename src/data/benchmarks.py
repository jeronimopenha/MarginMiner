from datetime import date, timedelta
from pathlib import Path
import base64
import io
import json
import re
import unicodedata

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

B3_INDEX_DOWNLOAD_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "indexStatisticsProxy/IndexCall/GetDownloadPortfolioDay"
)

BENCHMARK_TICKERS = {
    "IBOV": "^BVSP",
}


B3_MONTHS = {
    "JAN": 1,
    "JANEIRO": 1,

    "FEB": 2,
    "FEV": 2,
    "FEVEREIRO": 2,

    "MAR": 3,
    "MARCO": 3,
    "MARÇO": 3,

    "APR": 4,
    "ABR": 4,
    "ABRIL": 4,

    "MAY": 5,
    "MAI": 5,
    "MAIO": 5,

    "JUN": 6,
    "JUNHO": 6,

    "JUL": 7,
    "JULHO": 7,

    "AUG": 8,
    "AGO": 8,
    "AGOSTO": 8,

    "SEP": 9,
    "SET": 9,
    "SETEMBRO": 9,

    "OCT": 10,
    "OUT": 10,
    "OUTUBRO": 10,

    "NOV": 11,
    "NOVEMBRO": 11,

    "DEC": 12,
    "DEZ": 12,
    "DEZEMBRO": 12,
}


def normalize_benchmark_ticker(benchmark: str) -> str:
    benchmark = benchmark.strip().upper()
    return BENCHMARK_TICKERS.get(benchmark, benchmark)


def _empty_benchmark_history() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
        ]
    )


def _standardize_benchmark_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_benchmark_history()

    df = df.copy()

    for col in _empty_benchmark_history().columns:
        if col not in df.columns:
            df[col] = None

    df = df[
        [
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
        ]
    ]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "close"])

    df = (
        df
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date")
        .reset_index(drop=True)
    )

    return df


# ==========================================================
# YAHOO — IBOV
# ==========================================================

def _fetch_benchmark_history_yahoo(
    benchmark: str,
    initial_date: date,
    final_date: date,
    interval: str = "1d",
) -> pd.DataFrame:
    ticker = normalize_benchmark_ticker(benchmark)

    period1 = int(pd.Timestamp(initial_date).timestamp())

    # Yahoo usa period2 como limite superior.
    # Somar 1 dia ajuda a incluir a data final.
    period2 = int(pd.Timestamp(final_date + timedelta(days=1)).timestamp())

    url = f"{YAHOO_CHART_URL}/{ticker}"

    params = {
        "period1": period1,
        "period2": period2,
        "interval": interval,
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
        return _empty_benchmark_history()

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

    return _standardize_benchmark_df(df)


# ==========================================================
# B3 — IFIX
# ==========================================================

def _normalize_text(text: str) -> str:
    text = str(text).strip().upper()

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    return text


def _parse_b3_number(value) -> float | None:
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()

    if text in {"", "-", "--", "nan", "NaN", "None"}:
        return None

    # B3 geralmente vem como 3.860,37.
    # Também trata 3860.37 se vier em formato americano.
    if "," in text:
        text = text.replace(".", "").replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def _encode_b3_payload(index: str, year: int, language: str = "pt-br") -> str:
    payload = {
        "index": index.upper(),
        "language": language,
        "year": str(year),
    }

    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def _decode_b3_response(response: requests.Response) -> str:
    content = response.content

    for encoding in ["utf-8-sig", "latin1", "cp1252"]:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    return content.decode("utf-8", errors="replace")


def _read_b3_csv_like_text(text: str) -> pd.DataFrame:
    text = text.lstrip("\ufeff").strip()

    if not text:
        return pd.DataFrame()

    # Se vier JSON com campo interno.
    if text.startswith("{"):
        try:
            data = json.loads(text)

            if isinstance(data, dict):
                for key in ["data", "content", "file", "result"]:
                    value = data.get(key)

                    if isinstance(value, str):
                        text = value.lstrip("\ufeff").strip()
                        break

        except json.JSONDecodeError:
            pass

    # Proteção: se veio HTML/Angular/Cloudflare, não é a tabela.
    lowered = text.lower()

    if "<html" in lowered or "<!doctype" in lowered or "<app-root" in lowered:
        return pd.DataFrame()

    # Tenta separadores comuns.
    for sep in [";", "\t", ","]:
        try:
            df = pd.read_csv(
                io.StringIO(text),
                sep=sep,
                dtype=str,
                engine="python",
            )

            if df.shape[1] > 1:
                return df

        except Exception:
            continue

    return pd.DataFrame()


def _parse_ifix_download_table(df: pd.DataFrame, year: int) -> pd.DataFrame:
    if df.empty:
        return _empty_benchmark_history()

    df = df.copy()

    # Remove colunas completamente vazias.
    df = df.dropna(axis=1, how="all")

    df.columns = [str(col).strip() for col in df.columns]

    rows = []

    normalized_columns = {
        _normalize_text(col): col
        for col in df.columns
    }

    # ======================================================
    # Caso 1: formato longo
    # Ex:
    # Data | Fechamento
    # Date | Close
    # ======================================================

    date_col = None
    value_col = None

    for candidate in [
        "DATA",
        "DATE",
        "DT_REFER",
        "DT_PREGAO",
    ]:
        if candidate in normalized_columns:
            date_col = normalized_columns[candidate]
            break

    for candidate in [
        "FECHAMENTO",
        "CLOSE",
        "VALOR",
        "PONTUACAO",
        "PONTUACAO DE FECHAMENTO",
        "CLOSING",
        "CLOSING VALUE",
    ]:
        if candidate in normalized_columns:
            value_col = normalized_columns[candidate]
            break

    if date_col is not None and value_col is not None:
        out = pd.DataFrame()
        out["date"] = pd.to_datetime(
            df[date_col],
            dayfirst=True,
            errors="coerce",
        )
        out["close"] = df[value_col].map(_parse_b3_number)

        out = out.dropna(subset=["date", "close"])

        out["open"] = out["close"]
        out["high"] = out["close"]
        out["low"] = out["close"]
        out["adj_close"] = out["close"]
        out["volume"] = 0.0

        return _standardize_benchmark_df(out)

    # ======================================================
    # Caso 2: formato matriz
    # Ex:
    # Dia | Jan | Fev | Mar | ...
    # ======================================================

    day_col = None

    for col in df.columns:
        norm = _normalize_text(col)

        if norm in {"DIA", "DAY"}:
            day_col = col
            break

    if day_col is None:
        day_col = df.columns[0]

    for _, row in df.iterrows():
        day_raw = str(row[day_col]).strip()

        # Pode vir como "1", "01", "1.0".
        day_raw = day_raw.replace(".0", "")

        if not re.fullmatch(r"\d{1,2}", day_raw):
            continue

        day = int(day_raw)

        for col in df.columns:
            if col == day_col:
                continue

            month = B3_MONTHS.get(_normalize_text(col))

            if month is None:
                continue

            close = _parse_b3_number(row[col])

            if close is None:
                continue

            try:
                current_date = date(year, month, day)
            except ValueError:
                continue

            rows.append(
                {
                    "date": pd.Timestamp(current_date),
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "adj_close": close,
                    "volume": 0.0,
                }
            )

    if not rows:
        return _empty_benchmark_history()

    return _standardize_benchmark_df(pd.DataFrame(rows))


def _save_b3_debug_response(
    year: int,
    text: str,
    debug_dir: str | Path = "storage/debug",
) -> Path:
    path = Path(debug_dir)
    path.mkdir(parents=True, exist_ok=True)

    file_path = path / f"b3_ifix_raw_{year}.txt"
    file_path.write_text(text, encoding="utf-8", errors="replace")

    return file_path


def _fetch_ifix_b3_year(year: int) -> pd.DataFrame:
    """
    Busca a evolução diária anual do IFIX pelo endpoint de download da B3.
    """

    encoded = _encode_b3_payload("IFIX", year, language="pt-br")
    url = f"{B3_INDEX_DOWNLOAD_URL}/{encoded}"

    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/plain,text/csv,application/json,*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://sistemaswebb3-listados.b3.com.br/indexStatisticsPage/daily-evolution/IFIX?language=pt-br",
        },
    )

    if not response.ok:
        raise RuntimeError(
            f"Error B3 {response.status_code}: {response.text[:500]}\nURL: {response.url}"
        )

    text = _decode_b3_response(response)

    table = _read_b3_csv_like_text(text)

    df = _parse_ifix_download_table(table, year)

    if df.empty:
        debug_file = _save_b3_debug_response(year, text)

        raise RuntimeError(
            "A B3 respondeu, mas não consegui transformar a resposta em tabela do IFIX.\n"
            f"Salvei a resposta bruta em: {debug_file}\n"
            "Abra esse arquivo e veja se veio CSV, JSON, HTML ou mensagem de bloqueio."
        )

    return df


def _fetch_ifix_history_b3(
    initial_date: date,
    final_date: date,
) -> pd.DataFrame:
    frames = []
    errors = []

    for year in range(initial_date.year, final_date.year + 1):
        try:
            df_year = _fetch_ifix_b3_year(year)

            if not df_year.empty:
                frames.append(df_year)

        except Exception as exc:
            errors.append(f"{year}: {exc}")

    if not frames:
        print()
        print("AVISO: não foi possível carregar o IFIX pela B3.")
        print("O IBOV continua funcionando normalmente.")
        print("Erros encontrados:")
        for error in errors[:5]:
            print("-", error)
        print()

        return _empty_benchmark_history()

    df = pd.concat(frames, ignore_index=True)
    df = _standardize_benchmark_df(df)

    df = df[
        (df["date"] >= pd.Timestamp(initial_date))
        & (df["date"] <= pd.Timestamp(final_date))
    ]

    return _standardize_benchmark_df(df)

def _benchmark_history_ifix_b3(
    years: int = 10,
    final_date: date | None = None,
    storage_dir: str | Path = "storage/benchmarks",
    overlap_days: int = 15,
) -> pd.DataFrame:
    if final_date is None:
        final_date = date.today()

    initial_date = final_date - relativedelta(years=years)

    path = Path(storage_dir) / "IFIX" / "history.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        df_old = pd.read_parquet(path)
        df_old = _standardize_benchmark_df(df_old)

        df_old = df_old[df_old["date"] >= pd.Timestamp(initial_date)]

        # Se veio aquele arquivo ruim com uma ou poucas linhas, refaz tudo.
        if len(df_old) < 200:
            df_old = _empty_benchmark_history()
            delta_initial_date = initial_date

        elif df_old.empty:
            delta_initial_date = initial_date

        else:
            last_saved_date = df_old["date"].max().date()
            delta_initial_date = last_saved_date - timedelta(days=overlap_days)

            if delta_initial_date < initial_date:
                delta_initial_date = initial_date

        if delta_initial_date <= final_date:
            df_new = _fetch_ifix_history_b3(
                initial_date=delta_initial_date,
                final_date=final_date,
            )

            df = pd.concat([df_old, df_new], ignore_index=True)

        else:
            df = df_old

    else:
        df = _fetch_ifix_history_b3(
            initial_date=initial_date,
            final_date=final_date,
        )

    if df.empty:
        df.to_parquet(path, index=False)
        return df

    df = _standardize_benchmark_df(df)

    df = df[
        (df["date"] >= pd.Timestamp(initial_date))
        & (df["date"] <= pd.Timestamp(final_date))
    ]

    df = _standardize_benchmark_df(df)

    df.to_parquet(path, index=False)

    return df


# ==========================================================
# Função pública genérica
# ==========================================================

def benchmark_history(
    benchmark: str,
    years: int = 10,
    interval: str = "1d",
    final_date: date | None = None,
    storage_dir: str | Path = "storage/benchmarks",
    overlap_days: int = 15,
) -> pd.DataFrame:
    benchmark_name = benchmark.strip().upper()

    if benchmark_name == "IFIX":
        return _benchmark_history_ifix_b3(
            years=years,
            final_date=final_date,
            storage_dir=storage_dir,
            overlap_days=overlap_days,
        )

    ticker = normalize_benchmark_ticker(benchmark_name)

    if final_date is None:
        final_date = date.today()

    initial_date = final_date - relativedelta(years=years)

    path = Path(storage_dir) / benchmark_name / "history.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        df_old = pd.read_parquet(path)
        df_old = _standardize_benchmark_df(df_old)

        df_old = df_old[df_old["date"] >= pd.Timestamp(initial_date)]

        if df_old.empty:
            delta_initial_date = initial_date
        else:
            last_saved_date = df_old["date"].max().date()

            delta_initial_date = last_saved_date - timedelta(days=overlap_days)

            if delta_initial_date < initial_date:
                delta_initial_date = initial_date

        if delta_initial_date <= final_date:
            df_new = _fetch_benchmark_history_yahoo(
                benchmark=ticker,
                initial_date=delta_initial_date,
                final_date=final_date,
                interval=interval,
            )

            df = pd.concat([df_old, df_new], ignore_index=True)

        else:
            df = df_old

    else:
        df = _fetch_benchmark_history_yahoo(
            benchmark=ticker,
            initial_date=initial_date,
            final_date=final_date,
            interval=interval,
        )

    if df.empty:
        df.to_parquet(path, index=False)
        return df

    df = _standardize_benchmark_df(df)

    df = df[
        (df["date"] >= pd.Timestamp(initial_date))
        & (df["date"] <= pd.Timestamp(final_date))
    ]

    df = _standardize_benchmark_df(df)

    df.to_parquet(path, index=False)

    return df


def ibov_history(
    years: int = 10,
    final_date: date | None = None,
) -> pd.DataFrame:
    return benchmark_history(
        benchmark="IBOV",
        years=years,
        final_date=final_date,
    )


def ifix_history(
    years: int = 10,
    final_date: date | None = None,
) -> pd.DataFrame:
    return benchmark_history(
        benchmark="IFIX",
        years=years,
        final_date=final_date,
    )