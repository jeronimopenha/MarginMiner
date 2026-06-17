from datetime import date
from pathlib import Path

import pandas as pd

from src.data.stocks import daily_stock_history
from src.data.selic import selic_periods_row
from src.analytics.stock_metrics import stock_metrics_by_period


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _safe_metric(
    metrics: pd.DataFrame,
    row: str,
    period: str,
):
    if metrics.empty:
        return None

    if row not in metrics.index:
        return None

    if period not in metrics.columns:
        return None

    value = metrics.loc[row, period]

    if pd.isna(value):
        return None

    return value


def load_validated_tickers(
    path: str | Path = PROJECT_ROOT / "storage" / "input" / "validated_tickers.parquet",
    min_lines: int = 500,
    min_liquidity_12m: float = 1_000_000,
) -> pd.DataFrame:
    """
    Carrega tickers já validados e filtra os que possuem histórico e liquidez mínima.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo de tickers validados não encontrado: {path}"
        )

    df = pd.read_parquet(path)

    required_columns = [
        "ticker",
        "status",
        "linhas",
        "liquidez_media_12m",
    ]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente: {col}")

    df = df[
        (df["status"] == "ok")
        & (df["linhas"] >= min_lines)
        & (df["liquidez_media_12m"] >= min_liquidity_12m)
    ].copy()

    df = df.sort_values("liquidez_media_12m", ascending=False).reset_index(drop=True)

    return df


def get_risk_free_by_period() -> dict[str, float]:
    selic = selic_periods_row()

    return (
        selic
        .set_index("")
        .loc["SELIC"]
        .to_dict()
    )


def build_quantitative_ranking(
    tickers: list[str],
    sector: str | None = None,
    company_type: str | None = None,
) -> pd.DataFrame:
    """
    Calcula ranking quantitativo usando preço, dividendos, Selic e métricas de risco.

    Ainda não usa fundamentos como P/L, ROE, FCL etc.
    """

    risk_free_by_period = get_risk_free_by_period()

    rows = []

    for ticker in tickers:
        print(f"Calculando ranking de {ticker}...")

        try:
            history = daily_stock_history(ticker)

            if history.empty:
                rows.append(
                    {
                        "ticker": ticker,
                        "status": "sem histórico",
                    }
                )
                continue

            metrics = stock_metrics_by_period(
                history,
                risk_free_by_period=risk_free_by_period,
            )

            latest_price = history["close"].iloc[-1]
            latest_date = pd.to_datetime(history["date"].iloc[-1]).date()

            row = {
                "date": date.today(),
                "ticker": ticker,
                "sector": sector,
                "company_type": company_type,
                "status": "ok",
                "latest_price": latest_price,
                "latest_date": latest_date,
                "history_rows": len(history),
                "liquidity_12m": history["financial_volume"].tail(252).mean(),
            }

            for period in ["12m", "3A", "5A", "10A"]:
                row[f"return_total_{period}"] = _safe_metric(
                    metrics,
                    "Retorno Total Reinvestido",
                    period,
                )
                row[f"cagr_total_{period}"] = _safe_metric(
                    metrics,
                    "CAGR Total Reinvestido",
                    period,
                )
                row[f"sharpe_total_{period}"] = _safe_metric(
                    metrics,
                    "Sharpe Total",
                    period,
                )
                row[f"sortino_total_{period}"] = _safe_metric(
                    metrics,
                    "Sortino Total",
                    period,
                )
                row[f"calmar_total_{period}"] = _safe_metric(
                    metrics,
                    "Calmar Total",
                    period,
                )
                row[f"drawdown_total_{period}"] = _safe_metric(
                    metrics,
                    "Drawdown Máximo Total",
                    period,
                )
                row[f"vol_total_{period}"] = _safe_metric(
                    metrics,
                    "Volatilidade Total Anualizada",
                    period,
                )
                row[f"positive_days_total_{period}"] = _safe_metric(
                    metrics,
                    "% Dias Positivos Total",
                    period,
                )

            rows.append(row)

        except Exception as exc:
            rows.append(
                {
                    "date": date.today(),
                    "ticker": ticker,
                    "sector": sector,
                    "company_type": company_type,
                    "status": "erro",
                    "error": str(exc),
                }
            )

    ranking = pd.DataFrame(rows)

    ranking = add_quantitative_scores(ranking)

    return ranking


def _rank_percentile(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:
    """
    Retorna score percentil entre 0 e 1.
    """

    series = pd.to_numeric(series, errors="coerce")

    if series.notna().sum() <= 1:
        return pd.Series([None] * len(series), index=series.index)

    return series.rank(
        pct=True,
        ascending=not higher_is_better,
    )


def add_quantitative_scores(ranking: pd.DataFrame) -> pd.DataFrame:
    """
    Cria scores simples para ranking inicial.

    Score ainda é provisório.
    """

    ranking = ranking.copy()

    ok_mask = ranking["status"] == "ok"

    ranking["score_return_5A"] = None
    ranking["score_sharpe_5A"] = None
    ranking["score_sortino_5A"] = None
    ranking["score_drawdown_5A"] = None
    ranking["score_liquidity"] = None
    ranking["score_quant"] = None

    if ok_mask.sum() == 0:
        return ranking

    ok = ranking.loc[ok_mask].copy()

    ok["score_return_5A"] = _rank_percentile(
        ok["cagr_total_5A"],
        higher_is_better=True,
    )

    ok["score_sharpe_5A"] = _rank_percentile(
        ok["sharpe_total_5A"],
        higher_is_better=True,
    )

    ok["score_sortino_5A"] = _rank_percentile(
        ok["sortino_total_5A"],
        higher_is_better=True,
    )

    # Drawdown é negativo. Quanto mais perto de zero, melhor.
    ok["score_drawdown_5A"] = _rank_percentile(
        ok["drawdown_total_5A"],
        higher_is_better=True,
    )

    ok["score_liquidity"] = _rank_percentile(
        ok["liquidity_12m"],
        higher_is_better=True,
    )

    ok["score_quant"] = (
        ok["score_return_5A"] * 0.30
        + ok["score_sharpe_5A"] * 0.25
        + ok["score_sortino_5A"] * 0.20
        + ok["score_drawdown_5A"] * 0.15
        + ok["score_liquidity"] * 0.10
    )

    for col in [
        "score_return_5A",
        "score_sharpe_5A",
        "score_sortino_5A",
        "score_drawdown_5A",
        "score_liquidity",
        "score_quant",
    ]:
        ranking.loc[ok_mask, col] = ok[col]

    ranking = ranking.sort_values(
        ["status", "score_quant"],
        ascending=[True, False],
    ).reset_index(drop=True)

    return ranking


def save_ranking_snapshot(
    ranking: pd.DataFrame,
    output_dir: str | Path = PROJECT_ROOT / "storage" / "rankings",
) -> tuple[Path, Path]:
    """
    Salva ranking do dia e latest.parquet.
    """

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()

    dated_path = output_dir / f"{today}.parquet"
    latest_path = output_dir / "latest.parquet"

    ranking.to_parquet(dated_path, index=False)
    ranking.to_parquet(latest_path, index=False)

    return dated_path, latest_path


def build_and_save_ranking_from_validated_tickers(
    validated_path: str | Path = PROJECT_ROOT / "storage" / "input" / "validated_tickers.parquet",
    sector: str | None = "energia elétrica",
    company_type: str | None = "eletrica",
    min_lines: int = 500,
    min_liquidity_12m: float = 1_000_000,
) -> pd.DataFrame:
    valid = load_validated_tickers(
        path=validated_path,
        min_lines=min_lines,
        min_liquidity_12m=min_liquidity_12m,
    )

    tickers = valid["ticker"].tolist()

    ranking = build_quantitative_ranking(
        tickers=tickers,
        sector=sector,
        company_type=company_type,
    )

    dated_path, latest_path = save_ranking_snapshot(ranking)

    print()
    print(f"Ranking salvo em: {dated_path}")
    print(f"Último ranking salvo em: {latest_path}")
    print()

    return ranking