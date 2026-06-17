import pandas as pd


def _is_missing(value) -> bool:
    return value is None or pd.isna(value)


def _pct(value: float) -> str:
    return f"{value:.2%}"


def _pp(value: float) -> str:
    return f"{value * 100:.2f} p.p."


def _get_period_value(period_values: pd.Series, row_name: str):
    if row_name not in period_values.index:
        return None

    value = period_values.loc[row_name]

    if _is_missing(value):
        return None

    return value


def _compare_to_selic(
    value: float,
    selic: float | None,
    metric_label: str,
    strong_threshold: float = 0.03,
    weak_threshold: float = 0.00,
) -> str:
    if selic is None:
        return f"{metric_label}: sem Selic disponível para comparação."

    diff = value - selic

    if diff >= strong_threshold:
        return (
            f"Bom: {metric_label} ficou {_pp(diff)} acima da Selic. "
            f"Houve prêmio relevante pelo risco."
        )

    if diff >= weak_threshold:
        return (
            f"Levemente positivo: {metric_label} ficou {_pp(diff)} acima da Selic. "
            f"Bateu a renda fixa, mas com pouca folga."
        )

    if diff >= -strong_threshold:
        return (
            f"Neutro/fraco: {metric_label} ficou {_pp(abs(diff))} abaixo da Selic. "
            f"O retorno não compensou claramente o risco."
        )

    return (
        f"Ruim: {metric_label} ficou {_pp(abs(diff))} abaixo da Selic. "
        f"Neste período, a renda fixa teria sido superior."
    )


def _analyze_volatility(value: float, label: str) -> str:
    if value < 0.15:
        return f"Baixa: {label} de {_pct(value)} indica oscilação relativamente controlada."

    if value < 0.30:
        return f"Moderada: {label} de {_pct(value)} é normal para ações brasileiras."

    if value < 0.45:
        return f"Alta: {label} de {_pct(value)} indica ativo bem oscilante."

    return f"Muito alta: {label} de {_pct(value)} indica instabilidade elevada e maior risco emocional."


def _analyze_drawdown(value: float, label: str) -> str:
    if value >= -0.15:
        return f"Controlado: {label} de {_pct(value)} sugere queda máxima relativamente pequena."

    if value >= -0.30:
        return f"Moderado: {label} de {_pct(value)} exige tolerância a quedas relevantes."

    if value >= -0.50:
        return f"Alto: {label} de {_pct(value)} mostra que o ativo já sofreu queda forte no período."

    return f"Muito alto: {label} de {_pct(value)} indica tombo severo. Exige muita convicção na tese."


def _analyze_liquidity(value: float) -> str:
    if value < 5_000_000:
        return (
            f"Baixa: liquidez média diária de R$ {value:,.0f}. "
            f"Pode haver dificuldade para entrar/sair sem impacto."
        ).replace(",", ".")

    if value < 20_000_000:
        return (
            f"Média: liquidez diária de R$ {value:,.0f}. "
            f"Aceitável para posições pequenas, mas merece atenção."
        ).replace(",", ".")

    if value < 100_000_000:
        return (
            f"Boa: liquidez diária de R$ {value:,.0f}. "
            f"Tende a ser suficiente para investidor pessoa física."
        ).replace(",", ".")

    return (
        f"Excelente: liquidez diária de R$ {value:,.0f}. "
        f"Ativo muito negociado."
    ).replace(",", ".")


def _analyze_sharpe_like(value: float, label: str) -> str:
    if value < 0:
        return f"Ruim: {label} negativo indica retorno abaixo da Selic para o risco assumido."

    if value < 0.50:
        return f"Fraco: {label} de {value:.2f} mostra pouco prêmio por unidade de risco."

    if value < 1.00:
        return f"Razoável: {label} de {value:.2f} indica relação retorno/risco positiva, mas não excepcional."

    if value < 1.50:
        return f"Bom: {label} de {value:.2f} indica boa compensação pelo risco."

    return f"Excelente: {label} de {value:.2f} indica retorno excedente muito forte para o risco."


def _analyze_calmar(value: float, label: str) -> str:
    if value < 0:
        return f"Ruim: {label} negativo indica retorno anual negativo ou insuficiente frente ao drawdown."

    if value < 0.30:
        return f"Fraco: {label} de {value:.2f} mostra pouco retorno para o tamanho da maior queda."

    if value < 0.70:
        return f"Moderado: {label} de {value:.2f} é aceitável, mas o drawdown pesa."

    if value < 1.00:
        return f"Bom: {label} de {value:.2f} indica retorno razoável frente ao pior tombo."

    return f"Muito bom: {label} de {value:.2f} indica bom retorno anual frente ao drawdown máximo."


def _analyze_return_volatility(value: float, label: str) -> str:
    if value < 0:
        return f"Ruim: {label} negativo indica retorno anual negativo ou muito fraco."

    if value < 0.30:
        return f"Fraco: {label} de {value:.2f} mostra baixo retorno para a volatilidade assumida."

    if value < 0.70:
        return f"Moderado: {label} de {value:.2f} mostra relação retorno/oscilação aceitável."

    if value < 1.00:
        return f"Bom: {label} de {value:.2f} indica bom retorno para a volatilidade."

    return f"Muito bom: {label} de {value:.2f} indica retorno forte para a volatilidade."


def _analyze_positive_days(value: float, label: str) -> str:
    if value < 0.45:
        return f"Atenção: {label} de {_pct(value)} mostra predominância de dias negativos."

    if value <= 0.55:
        return f"Normal: {label} de {_pct(value)} é comum em ações; poucos ativos sobem na maioria ampla dos dias."

    return f"Boa consistência: {label} de {_pct(value)} mostra frequência positiva acima do normal."


def _analyze_best_worst_day(value: float, label: str) -> str:
    abs_value = abs(value)

    if abs_value < 0.03:
        return f"Controlado: {label} de {_pct(value)} mostra baixa variação extrema diária."

    if abs_value < 0.07:
        return f"Moderado: {label} de {_pct(value)} mostra variação diária relevante, mas comum em ações."

    return f"Alto: {label} de {_pct(value)} mostra evento diário extremo. Indica risco de oscilação forte."


def _analyze_dividend_yield(value: float, history_years: float | None) -> str:
    if history_years is None or history_years <= 0:
        return f"Dividend yield acumulado de {_pct(value)}. Sem anos suficientes para anualizar."

    annualized_yield = (1 + value) ** (1 / history_years) - 1

    if annualized_yield < 0.03:
        return (
            f"Baixo: DY histórico aproximado de {_pct(value)} no período "
            f"equivale a cerca de {_pct(annualized_yield)} ao ano."
        )

    if annualized_yield < 0.07:
        return (
            f"Moderado: DY histórico aproximado de {_pct(value)} no período "
            f"equivale a cerca de {_pct(annualized_yield)} ao ano."
        )

    if annualized_yield < 0.12:
        return (
            f"Alto: DY histórico aproximado de {_pct(value)} no período "
            f"equivale a cerca de {_pct(annualized_yield)} ao ano."
        )

    return (
        f"Muito alto: DY histórico aproximado de {_pct(value)} no período "
        f"equivale a cerca de {_pct(annualized_yield)} ao ano. "
        f"Verificar se há eventos não recorrentes."
    )


def analyze_metric_value(
    metric_name: str,
    value,
    period_values: pd.Series,
) -> str:
    """
    Interpreta um valor específico de métrica em um período.

    period_values é a coluna completa daquele período.
    Ex: metrics["5A"]
    """

    if _is_missing(value):
        return "Sem dados suficientes para análise."

    selic = _get_period_value(period_values, "SELIC Anualizada")
    history_years = _get_period_value(period_values, "Anos de Histórico no Período")

    if metric_name == "Histórico Válido":
        return (
            "Período válido para análise."
            if bool(value)
            else "Histórico insuficiente. Ignore os indicadores deste período."
        )

    if metric_name == "Anos de Histórico no Período":
        if value >= 9.8:
            return "Histórico longo. Bom para avaliar ciclos maiores."
        if value >= 4.8:
            return "Histórico intermediário. Útil, mas pode não pegar ciclos completos."
        if value >= 2.8:
            return "Histórico curto/médio. Use com cautela."
        return "Histórico curto. Indicadores podem estar muito influenciados pelo momento recente."

    if metric_name == "Liquidez Média Diária":
        return _analyze_liquidity(float(value))

    if metric_name == "Retorno Acumulado Preço":
        if value > 0:
            return f"Preço subiu {_pct(value)} no período. Lembre que isso ignora dividendos."
        if value < 0:
            return f"Preço caiu {_pct(value)} no período. Verificar retorno total com dividendos."
        return "Preço ficou praticamente estável no período."

    if metric_name == "CAGR Preço":
        return _compare_to_selic(float(value), selic, "CAGR preço")

    if metric_name == "Volatilidade Preço Anualizada":
        return _analyze_volatility(float(value), "volatilidade de preço")

    if metric_name == "Volatilidade Negativa Preço Anualizada":
        return _analyze_volatility(float(value), "volatilidade negativa de preço")

    if metric_name == "Drawdown Máximo Preço":
        return _analyze_drawdown(float(value), "drawdown máximo de preço")

    if metric_name == "Dividendos Acumulados por Ação":
        if value <= 0:
            return "Não há dividendos registrados no período ou a fonte não retornou proventos."
        return f"Foram pagos R$ {value:.2f} por ação no período. Avalie junto com o DY histórico."

    if metric_name == "Dividend Yield Histórico Aproximado":
        return _analyze_dividend_yield(float(value), history_years)

    if metric_name == "Retorno Acumulado com Dividendos Simples":
        if value > 0:
            return f"Retorno simples com dividendos foi positivo: {_pct(value)}."
        if value < 0:
            return f"Mesmo com dividendos, o retorno simples foi negativo: {_pct(value)}."
        return "Retorno simples com dividendos ficou praticamente zerado."

    if metric_name == "CAGR com Dividendos Simples":
        return _compare_to_selic(float(value), selic, "CAGR com dividendos simples")

    if metric_name == "Retorno Total Reinvestido":
        if value > 0:
            return f"Retorno total reinvestido positivo: {_pct(value)}. Melhor métrica que preço isolado."
        if value < 0:
            return f"Retorno total reinvestido negativo: {_pct(value)}. Dividendos não compensaram a queda."
        return "Retorno total reinvestido ficou praticamente zerado."

    if metric_name == "CAGR Total Reinvestido":
        return _compare_to_selic(float(value), selic, "CAGR total reinvestido")

    if metric_name == "Volatilidade Total Anualizada":
        return _analyze_volatility(float(value), "volatilidade total")

    if metric_name == "Volatilidade Negativa Total Anualizada":
        return _analyze_volatility(float(value), "volatilidade negativa total")

    if metric_name == "Drawdown Máximo Total":
        return _analyze_drawdown(float(value), "drawdown máximo total")

    if metric_name == "SELIC Anualizada":
        return f"Taxa livre de risco do período: {_pct(value)} ao ano. Use como base de comparação."

    if metric_name == "Sharpe Preço":
        return _analyze_sharpe_like(float(value), "Sharpe preço")

    if metric_name == "Sortino Preço":
        return _analyze_sharpe_like(float(value), "Sortino preço")

    if metric_name == "Calmar Preço":
        return _analyze_calmar(float(value), "Calmar preço")

    if metric_name == "Retorno/Volatilidade Preço":
        return _analyze_return_volatility(float(value), "retorno/volatilidade preço")

    if metric_name == "Sharpe Total":
        return _analyze_sharpe_like(float(value), "Sharpe total")

    if metric_name == "Sortino Total":
        return _analyze_sharpe_like(float(value), "Sortino total")

    if metric_name == "Calmar Total":
        return _analyze_calmar(float(value), "Calmar total")

    if metric_name == "Retorno/Volatilidade Total":
        return _analyze_return_volatility(float(value), "retorno/volatilidade total")

    if metric_name == "Melhor Dia Preço":
        return _analyze_best_worst_day(float(value), "melhor dia de preço")

    if metric_name == "Pior Dia Preço":
        return _analyze_best_worst_day(float(value), "pior dia de preço")

    if metric_name == "% Dias Positivos Preço":
        return _analyze_positive_days(float(value), "% de dias positivos por preço")

    if metric_name == "Melhor Dia Total":
        return _analyze_best_worst_day(float(value), "melhor dia total")

    if metric_name == "Pior Dia Total":
        return _analyze_best_worst_day(float(value), "pior dia total")

    if metric_name == "% Dias Positivos Total":
        return _analyze_positive_days(float(value), "% de dias positivos total")

    return "Indicador calculado. Interpretação específica ainda não definida."


def build_metric_analysis(metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Gera uma tabela com a análise automática de cada indicador.

    Recebe metrics cru, não formatado.
    """

    analysis = pd.DataFrame(index=metrics.index, columns=metrics.columns)

    for period in metrics.columns:
        period_values = metrics[period]

        for metric_name in metrics.index:
            value = metrics.loc[metric_name, period]

            analysis.loc[metric_name, period] = analyze_metric_value(
                metric_name=metric_name,
                value=value,
                period_values=period_values,
            )

    return analysis


def combine_metrics_and_analysis(
    formatted_metrics: pd.DataFrame,
    analysis: pd.DataFrame,
) -> pd.DataFrame:
    """
    Junta valores formatados e análise em uma única tabela.

    Ex:
        12m Valor | 12m Análise | 3A Valor | 3A Análise ...
    """

    output = pd.DataFrame(index=formatted_metrics.index)

    for period in formatted_metrics.columns:
        output[f"{period} Valor"] = formatted_metrics[period]
        output[f"{period} Análise"] = analysis[period]

    return output