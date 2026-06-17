from pathlib import Path

import pandas as pd

from src.data.tickers import (
    load_tickers_from_csv,
    filter_common_brazilian_tickers,
)
from src.data.stocks import daily_stock_history
from src.analytics.ranking import build_and_save_ranking_from_validated_tickers


PROJECT_ROOT = Path(__file__).resolve().parent


def validate_tickers_from_csv():
    csv_path = PROJECT_ROOT / "storage" / "input" / "statusinvest_acoes.csv"

    tickers = load_tickers_from_csv(csv_path)
    tickers = filter_common_brazilian_tickers(tickers)

    rows = []

    for ticker in tickers:
        print(f"Validando {ticker}...")

        try:
            df = daily_stock_history(ticker)

            if df.empty:
                rows.append(
                    {
                        "ticker": ticker,
                        "status": "sem histórico",
                        "linhas": 0,
                        "primeira_data": None,
                        "ultima_data": None,
                        "liquidez_media_12m": None,
                        "erro": None,
                    }
                )
                continue

            liquidity = df["financial_volume"].tail(252).mean()

            rows.append(
                {
                    "ticker": ticker,
                    "status": "ok",
                    "linhas": len(df),
                    "primeira_data": df["date"].min(),
                    "ultima_data": df["date"].max(),
                    "liquidez_media_12m": liquidity,
                    "erro": None,
                }
            )

        except Exception as exc:
            rows.append(
                {
                    "ticker": ticker,
                    "status": "erro",
                    "linhas": None,
                    "primeira_data": None,
                    "ultima_data": None,
                    "liquidez_media_12m": None,
                    "erro": str(exc),
                }
            )

    result = pd.DataFrame(rows)

    output_path = PROJECT_ROOT / "storage" / "input" / "validated_tickers.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result.to_parquet(output_path, index=False)

    print(result)
    print(result["status"].value_counts())

    valid = result[
        (result["status"] == "ok")
        & (result["linhas"] >= 500)
        & (result["liquidez_media_12m"] >= 1_000_000)
    ]

    print()
    print("Tickers válidos para ranking:")
    print(valid[["ticker", "linhas", "liquidez_media_12m"]])

    return result


if __name__ == "__main__":
    # Rode esta linha quando quiser revalidar a lista do CSV.
    validate_tickers_from_csv()

    # Gera ranking usando apenas os tickers válidos.
    ranking = build_and_save_ranking_from_validated_tickers(
        sector="energia elétrica",
        company_type="eletrica",
        min_lines=500,
        min_liquidity_12m=1_000_000,
    )

    print(ranking)