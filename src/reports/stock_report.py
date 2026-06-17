import pandas as pd


REPORT_SECTIONS = {
    "Resumo do Histórico": [
        "Histórico Válido",
        "Anos de Histórico no Período",
        "Liquidez Média Diária",
    ],

    "Retorno por Preço": [
        "Retorno Acumulado Preço",
        "CAGR Preço",
        "Volatilidade Preço Anualizada",
        "Volatilidade Negativa Preço Anualizada",
        "Drawdown Máximo Preço",
        "Sharpe Preço",
        "Sortino Preço",
        "Calmar Preço",
        "Retorno/Volatilidade Preço",
    ],

    "Dividendos": [
        "Dividendos Acumulados por Ação",
        "Dividend Yield Histórico Aproximado",
        "Retorno Acumulado com Dividendos Simples",
        "CAGR com Dividendos Simples",
    ],

    "Retorno Total com Dividendos Reinvestidos": [
        "Retorno Total Reinvestido",
        "CAGR Total Reinvestido",
        "Volatilidade Total Anualizada",
        "Volatilidade Negativa Total Anualizada",
        "Drawdown Máximo Total",
        "Sharpe Total",
        "Sortino Total",
        "Calmar Total",
        "Retorno/Volatilidade Total",
    ],

    "Comparação com Renda Fixa": [
        "SELIC Anualizada",
    ],

    "Comportamento Diário": [
        "Melhor Dia Preço",
        "Pior Dia Preço",
        "% Dias Positivos Preço",
        "Melhor Dia Total",
        "Pior Dia Total",
        "% Dias Positivos Total",
    ],
}


def split_metrics_by_section(metrics: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Separa a tabela de métricas em blocos temáticos.
    """

    sections = {}

    for section_name, rows in REPORT_SECTIONS.items():
        existing_rows = [row for row in rows if row in metrics.index]

        if existing_rows:
            sections[section_name] = metrics.loc[existing_rows]

    return sections


def print_metrics_report(
    metrics: pd.DataFrame,
    ticker: str | None = None,
) -> None:
    """
    Imprime o relatório de métricas no terminal em blocos.
    Espera receber a tabela já formatada.
    """

    if ticker is not None:
        print("=" * 120)
        print(f"RELATÓRIO QUANTITATIVO — {ticker.upper()}")
        print("=" * 120)
        print()

    sections = split_metrics_by_section(metrics)

    for section_name, section_df in sections.items():
        print("-" * 120)
        print(section_name)
        print("-" * 120)
        print(section_df)
        print()