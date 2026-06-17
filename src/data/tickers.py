from pathlib import Path

import pandas as pd


POSSIBLE_TICKER_COLUMNS = [
    "ticker",
    "papel",
    "ativo",
    "codigo",
    "código",
    "symbol",
    "acao",
    "ação",
]


def normalize_ticker(ticker: str, add_sa: bool = False) -> str:
    ticker = str(ticker).strip().upper()

    if not ticker:
        return ""

    ticker = ticker.replace(".SA", "")

    if add_sa:
        ticker = ticker + ".SA"

    return ticker


def load_tickers_from_csv(
    csv_path: str | Path,
    add_sa: bool = False,
) -> list[str]:
    """
    Lê um CSV exportado de algum site e retorna apenas os tickers.

    Tenta detectar automaticamente:
    - separador ;
    - separador ,
    - encoding utf-8
    - encoding latin1
    """

    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {csv_path}")

    last_error = None

    for encoding in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
        for sep in [";", ",", "\t"]:
            try:
                df = pd.read_csv(
                    csv_path,
                    sep=sep,
                    encoding=encoding,
                    dtype=str,
                )

                if df.shape[1] > 1:
                    return extract_tickers_from_dataframe(
                        df,
                        add_sa=add_sa,
                    )

            except Exception as exc:
                last_error = exc

    raise RuntimeError(
        f"Não consegui ler o CSV: {csv_path}. Último erro: {last_error}"
    )


def extract_tickers_from_dataframe(
    df: pd.DataFrame,
    add_sa: bool = False,
) -> list[str]:
    columns_normalized = {
        str(col).strip().lower(): col
        for col in df.columns
    }

    ticker_column = None

    for possible_name in POSSIBLE_TICKER_COLUMNS:
        if possible_name in columns_normalized:
            ticker_column = columns_normalized[possible_name]
            break

    if ticker_column is None:
        # fallback: usa a primeira coluna
        ticker_column = df.columns[0]

    tickers = []

    for value in df[ticker_column].dropna():
        ticker = normalize_ticker(value, add_sa=add_sa)

        if ticker:
            tickers.append(ticker)

    tickers = sorted(set(tickers))

    return tickers

def filter_common_brazilian_tickers(tickers: list[str]) -> list[str]:
    """
    Remove tickers com formatos muito incomuns para a primeira versão.

    Mantém:
    - ON/PN comuns: ABCD3, ABCD4
    - Units comuns: ABCD11

    Remove, por enquanto:
    - tickers com B no final, tipo ENMA3B
    - tickers muito estranhos
    """

    filtered = []

    for ticker in tickers:
        ticker = normalize_ticker(ticker, add_sa=False)

        if not ticker:
            continue

        # Mantém tickers do tipo ABCD3, ABCD4, ABCD11
        if len(ticker) >= 5 and ticker[-1].isdigit():
            filtered.append(ticker)

    return sorted(set(filtered))