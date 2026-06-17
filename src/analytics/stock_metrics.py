from dataclasses import dataclass
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass
class PeriodConfig:
    label: str
    years: int


DEFAULT_PERIODS = [
    PeriodConfig("12m", 1),
    PeriodConfig("3A", 3),
    PeriodConfig("5A", 5),
    PeriodConfig("10A", 10),
]


def _empty_metrics_result() -> dict:
    return {
        "valid": False,
        "history_years": None,

        "Retorno Acumulado Preço": None,
        "CAGR Preço": None,
        "Volatilidade Preço Anualizada": None,
        "Volatilidade Negativa Preço Anualizada": None,
        "Drawdown Máximo Preço": None,

        "Liquidez Média Diária": None,

        "Dividendos Acumulados por Ação": None,
        "Dividend Yield Histórico Aproximado": None,

        "Retorno Acumulado com Dividendos Simples": None,
        "CAGR com Dividendos Simples": None,

        "Retorno Total Reinvestido": None,
        "CAGR Total Reinvestido": None,
        "Volatilidade Total Anualizada": None,
        "Volatilidade Negativa Total Anualizada": None,
        "Drawdown Máximo Total": None,

        "SELIC Anualizada": None,

        "Sharpe Preço": None,
        "Sortino Preço": None,
        "Calmar Preço": None,
        "Retorno/Volatilidade Preço": None,

        "Sharpe Total": None,
        "Sortino Total": None,
        "Calmar Total": None,
        "Retorno/Volatilidade Total": None,

        "Melhor Dia Preço": None,
        "Pior Dia Preço": None,
        "% Dias Positivos Preço": None,

        "Melhor Dia Total": None,
        "Pior Dia Total": None,
        "% Dias Positivos Total": None,
    }

def _max_drawdown_from_series(series: pd.Series) -> float | None:
    series = series.dropna()

    if series.empty:
        return None

    running_max = series.cummax()
    drawdown = series / running_max - 1

    return drawdown.min()

def _prepare_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    needed_columns = [
        "close",
        "financial_volume",
        "dividend",
    ]

    for col in needed_columns:
        if col not in df.columns:
            df[col] = 0.0

    df["dividend"] = df["dividend"].fillna(0.0)
    df["financial_volume"] = df["financial_volume"].fillna(0.0)

    df = df.dropna(subset=["close"])

    return df


def _slice_period(
        df: pd.DataFrame,
        years: int,
        tolerance_days: int = 10,
) -> pd.DataFrame:
    final_date = df["date"].max()
    target_initial_date = final_date - relativedelta(years=years)

    df_period = df[df["date"] >= target_initial_date].copy()

    if df_period.empty:
        return df_period

    first_available_date = df_period["date"].min()

    maximum_accepted_initial_date = target_initial_date + pd.Timedelta(
        days=tolerance_days
    )

    if first_available_date > maximum_accepted_initial_date:
        return pd.DataFrame(columns=df.columns)

    return df_period.reset_index(drop=True)


def calculate_metrics_for_period(
    df: pd.DataFrame,
    years: int,
    risk_free_rate: float | None = None,
) -> dict:
    df = _prepare_history(df)
    df_period = _slice_period(df, years)

    result = _empty_metrics_result()

    if len(df_period) < 2:
        return result

    initial_date = df_period["date"].iloc[0]
    final_date = df_period["date"].iloc[-1]

    actual_years = (final_date - initial_date).days / 365.25

    if actual_years <= 0:
        return result

    initial_close = df_period["close"].iloc[0]
    final_close = df_period["close"].iloc[-1]

    if initial_close <= 0:
        return result

    # =========================
    # Preço
    # =========================

    price_accumulated_return = final_close / initial_close - 1
    price_cagr = (final_close / initial_close) ** (1 / actual_years) - 1

    price_returns = df_period["close"].pct_change().dropna()

    price_max_drawdown = _max_drawdown_from_series(df_period["close"])

    price_risk = _risk_metrics_from_returns(
        returns=price_returns,
        annual_return=price_cagr,
        risk_free_rate=risk_free_rate,
        max_drawdown=price_max_drawdown,
    )

    # =========================
    # Liquidez
    # =========================

    average_daily_liquidity = df_period["financial_volume"].mean()

    # =========================
    # Dividendos simples
    # =========================

    accumulated_dividends = df_period["dividend"].sum()

    historical_dividend_yield = accumulated_dividends / initial_close

    simple_total_return = (
        final_close + accumulated_dividends
    ) / initial_close - 1

    simple_total_cagr = (
        (final_close + accumulated_dividends) / initial_close
    ) ** (1 / actual_years) - 1

    # =========================
    # Retorno total reinvestido
    # =========================
    #
    # Aproximação:
    # retorno_total_dia = (preço_hoje + dividendo_hoje) / preço_ontem - 1
    #
    # Isso simula o efeito econômico do dividendo no retorno diário.

    total_returns = (
        (df_period["close"] + df_period["dividend"])
        / df_period["close"].shift(1)
        - 1
    ).dropna()

    if total_returns.empty:
        total_accumulated_return = None
        total_cagr = None
        total_max_drawdown = None

        total_risk = {
            "volatility": None,
            "downside_volatility": None,
            "sharpe": None,
            "sortino": None,
            "calmar": None,
            "return_volatility": None,
            "best_day": None,
            "worst_day": None,
            "positive_days_ratio": None,
        }

    else:
        total_factor = (1 + total_returns).prod()

        total_accumulated_return = total_factor - 1
        total_cagr = total_factor ** (1 / actual_years) - 1

        total_index = (1 + total_returns).cumprod()

        total_max_drawdown = _max_drawdown_from_series(total_index)

        total_risk = _risk_metrics_from_returns(
            returns=total_returns,
            annual_return=total_cagr,
            risk_free_rate=risk_free_rate,
            max_drawdown=total_max_drawdown,
        )

    result.update(
        {
            "valid": True,
            "history_years": actual_years,

            "Retorno Acumulado Preço": price_accumulated_return,
            "CAGR Preço": price_cagr,
            "Volatilidade Preço Anualizada": price_risk["volatility"],
            "Volatilidade Negativa Preço Anualizada": price_risk["downside_volatility"],
            "Drawdown Máximo Preço": price_max_drawdown,

            "Liquidez Média Diária": average_daily_liquidity,

            "Dividendos Acumulados por Ação": accumulated_dividends,
            "Dividend Yield Histórico Aproximado": historical_dividend_yield,

            "Retorno Acumulado com Dividendos Simples": simple_total_return,
            "CAGR com Dividendos Simples": simple_total_cagr,

            "Retorno Total Reinvestido": total_accumulated_return,
            "CAGR Total Reinvestido": total_cagr,
            "Volatilidade Total Anualizada": total_risk["volatility"],
            "Volatilidade Negativa Total Anualizada": total_risk["downside_volatility"],
            "Drawdown Máximo Total": total_max_drawdown,

            "SELIC Anualizada": risk_free_rate,

            "Sharpe Preço": price_risk["sharpe"],
            "Sortino Preço": price_risk["sortino"],
            "Calmar Preço": price_risk["calmar"],
            "Retorno/Volatilidade Preço": price_risk["return_volatility"],

            "Sharpe Total": total_risk["sharpe"],
            "Sortino Total": total_risk["sortino"],
            "Calmar Total": total_risk["calmar"],
            "Retorno/Volatilidade Total": total_risk["return_volatility"],

            "Melhor Dia Preço": price_risk["best_day"],
            "Pior Dia Preço": price_risk["worst_day"],
            "% Dias Positivos Preço": price_risk["positive_days_ratio"],

            "Melhor Dia Total": total_risk["best_day"],
            "Pior Dia Total": total_risk["worst_day"],
            "% Dias Positivos Total": total_risk["positive_days_ratio"],
        }
    )

    return result


def stock_metrics_by_period(
    df: pd.DataFrame,
    periods: list[PeriodConfig] | None = None,
    risk_free_by_period: dict[str, float] | None = None,
) -> pd.DataFrame:
    if periods is None:
        periods = DEFAULT_PERIODS

    metrics_by_period = {}

    for period in periods:
        risk_free_rate = None

        if risk_free_by_period is not None:
            risk_free_rate = risk_free_by_period.get(period.label)

        metrics_by_period[period.label] = calculate_metrics_for_period(
            df=df,
            years=period.years,
            risk_free_rate=risk_free_rate,
        )

    rows = [
        "Histórico Válido",
        "Anos de Histórico no Período",

        "Retorno Acumulado Preço",
        "CAGR Preço",
        "Volatilidade Preço Anualizada",
        "Volatilidade Negativa Preço Anualizada",
        "Drawdown Máximo Preço",

        "Liquidez Média Diária",

        "Dividendos Acumulados por Ação",
        "Dividend Yield Histórico Aproximado",

        "Retorno Acumulado com Dividendos Simples",
        "CAGR com Dividendos Simples",

        "Retorno Total Reinvestido",
        "CAGR Total Reinvestido",
        "Volatilidade Total Anualizada",
        "Volatilidade Negativa Total Anualizada",
        "Drawdown Máximo Total",

        "SELIC Anualizada",

        "Sharpe Preço",
        "Sortino Preço",
        "Calmar Preço",
        "Retorno/Volatilidade Preço",

        "Sharpe Total",
        "Sortino Total",
        "Calmar Total",
        "Retorno/Volatilidade Total",

        "Melhor Dia Preço",
        "Pior Dia Preço",
        "% Dias Positivos Preço",

        "Melhor Dia Total",
        "Pior Dia Total",
        "% Dias Positivos Total",
    ]

    output = pd.DataFrame(index=rows)

    for label, metrics in metrics_by_period.items():
        output.loc["Histórico Válido", label] = metrics["valid"]
        output.loc["Anos de Histórico no Período", label] = metrics["history_years"]

        for row in rows[2:]:
            output.loc[row, label] = metrics[row]

    return output

def _risk_metrics_from_returns(
    returns: pd.Series,
    annual_return: float,
    risk_free_rate: float | None,
    max_drawdown: float | None,
) -> dict:
    returns = returns.dropna()

    if returns.empty:
        return {
            "volatility": None,
            "downside_volatility": None,
            "sharpe": None,
            "sortino": None,
            "calmar": None,
            "return_volatility": None,
            "best_day": None,
            "worst_day": None,
            "positive_days_ratio": None,
        }

    volatility = returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)

    best_day = returns.max()
    worst_day = returns.min()
    positive_days_ratio = (returns > 0).mean()

    if risk_free_rate is not None:
        daily_risk_free = (1 + risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
        downside_returns = returns - daily_risk_free
    else:
        downside_returns = returns.copy()

    downside_returns = downside_returns[downside_returns < 0]

    if len(downside_returns) >= 2:
        downside_volatility = downside_returns.std(ddof=1) * np.sqrt(
            TRADING_DAYS_PER_YEAR
        )
    else:
        downside_volatility = None

    if risk_free_rate is not None and volatility is not None and volatility != 0:
        sharpe = (annual_return - risk_free_rate) / volatility
    else:
        sharpe = None

    if (
        risk_free_rate is not None
        and downside_volatility is not None
        and downside_volatility != 0
    ):
        sortino = (annual_return - risk_free_rate) / downside_volatility
    else:
        sortino = None

    if max_drawdown is not None and max_drawdown < 0:
        calmar = annual_return / abs(max_drawdown)
    else:
        calmar = None

    if volatility is not None and volatility != 0:
        return_volatility = annual_return / volatility
    else:
        return_volatility = None

    return {
        "volatility": volatility,
        "downside_volatility": downside_volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "return_volatility": return_volatility,
        "best_day": best_day,
        "worst_day": worst_day,
        "positive_days_ratio": positive_days_ratio,
    }

def format_metrics_report(metrics: pd.DataFrame) -> pd.DataFrame:
    formatted = metrics.copy()

    percent_rows = [
        "Retorno Acumulado Preço",
        "CAGR Preço",
        "Volatilidade Anualizada",
        "Volatilidade Negativa Anualizada",
        "Drawdown Máximo",
        "Dividend Yield Histórico Aproximado",
        "Retorno Acumulado com Dividendos Simples",
        "CAGR com Dividendos Simples",
        "SELIC Anualizada",
        "Melhor Dia",
        "Pior Dia",
        "% Dias Positivos",
    ]

    money_rows = [
        "Liquidez Média Diária",
    ]

    number_rows = [
        "Anos de Histórico no Período",
        "Dividendos Acumulados por Ação",
        "Sharpe Preço",
        "Sortino Preço",
        "Calmar Preço",
        "Retorno/Risco Preço",
    ]

    for row in formatted.index:
        for col in formatted.columns:
            value = formatted.loc[row, col]

            if pd.isna(value):
                formatted.loc[row, col] = ""
                continue

            if row == "Histórico Válido":
                formatted.loc[row, col] = "Sim" if value else "Não"

            elif row in percent_rows:
                formatted.loc[row, col] = f"{value:.2%}"

            elif row in money_rows:
                formatted.loc[row, col] = f"R$ {value:,.0f}".replace(",", ".")

            elif row in number_rows:
                formatted.loc[row, col] = f"{value:.2f}"

            else:
                formatted.loc[row, col] = value

    return formatted


'''
Histórico Válido: indica se o ativo possui dados suficientes para calcular o período analisado. Se estiver como “Não”, os indicadores daquele período devem ser ignorados ou vistos com cautela.

Anos de Histórico no Período: mostra quantos anos efetivos de dados foram usados no cálculo. Pode ser menor que 10 anos para empresas que abriram capital recentemente ou ativos com histórico incompleto.

Retorno Acumulado Preço: mede quanto o preço do ativo subiu ou caiu no período, ignorando dividendos. É calculado pela relação entre o preço final e o preço inicial.

CAGR Preço: retorno anual composto do preço do ativo. Mostra qual teria sido o retorno médio anual se o crescimento tivesse ocorrido de forma constante. Ignora dividendos.

Volatilidade Anualizada: mede a oscilação anualizada dos retornos diários do ativo. Quanto maior, mais instável foi o preço no período.

Volatilidade Negativa Anualizada: mede a oscilação anualizada dos retornos negativos. É uma medida de risco focada apenas nos movimentos ruins.

Drawdown Máximo: maior queda percentual do ativo a partir de um topo anterior dentro do período analisado. Ajuda a entender o tamanho do pior tombo que o investidor teria enfrentado.

Liquidez Média Diária: média do volume financeiro diário negociado no período. Ajuda a avaliar se o ativo tem negociação suficiente para entradas e saídas sem grande impacto.

Dividendos Acumulados por Ação: soma dos dividendos, juros sobre capital próprio e proventos em dinheiro por ação no período analisado, conforme disponíveis na fonte de dados.

Dividend Yield Histórico Aproximado: dividendos acumulados no período divididos pelo preço inicial do período. É uma aproximação da renda recebida em relação ao preço de entrada.

Retorno Acumulado com Dividendos Simples: retorno do ativo considerando preço final mais dividendos recebidos, sem reinvestimento dos dividendos.

CAGR com Dividendos Simples: retorno anual composto considerando preço final mais dividendos acumulados, sem reinvestimento.

SELIC Anualizada: taxa livre de risco anualizada no mesmo período analisado. Serve como comparação mínima de retorno para avaliar se o risco do ativo foi recompensado.

Sharpe Preço: mede o retorno excedente do preço em relação à Selic por unidade de volatilidade. Valores maiores indicam melhor relação entre retorno excedente e risco total.

Sortino Preço: parecido com o Sharpe, mas usa apenas a volatilidade negativa. Penaliza mais os movimentos ruins e ignora parte da volatilidade positiva.

Calmar Preço: mede o CAGR do preço dividido pelo drawdown máximo. Mostra quanto retorno anual o ativo entregou em relação à maior queda sofrida no período.

Retorno/Volatilidade Preço: mede o CAGR do preço dividido pela volatilidade anualizada. É uma medida simples de retorno por unidade de oscilação, sem descontar a Selic.

Melhor Dia: maior retorno diário do ativo dentro do período analisado.

Pior Dia: pior retorno diário do ativo dentro do período analisado.

% Dias Positivos: percentual de dias em que o ativo fechou com retorno positivo.

'''