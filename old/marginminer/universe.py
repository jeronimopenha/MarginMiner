import pandas as pd
from config import CSV_DIR

def list_sector_files():
    return sorted([f.name for f in CSV_DIR.glob("*.csv")])

def load_sector_tickers(filename):
    path = CSV_DIR / filename
    df = pd.read_csv(path)

    if "TICKER" not in df.columns:
        raise ValueError("Coluna TICKER não encontrada.")

    tickers = (
        df["TICKER"]
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
        .tolist()
    )

    return tickers

def to_yahoo(ticker):
    return f"{ticker}.SA"
