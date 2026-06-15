from src.analytics.stock_metrics import stock_metrics_by_period, format_metrics_report
from src.data.selic import selic_periods_row
from src.data.stocks import daily_stock_history

import pandas as pd

if __name__ == "__main__":
    stock_history = daily_stock_history("ITSA4")

    selic = selic_periods_row()

    risk_free_by_period = (
        selic
        .set_index("")
        .loc["SELIC"]
        .to_dict()
    )

    metrics = stock_metrics_by_period(
        stock_history,
        risk_free_by_period=risk_free_by_period,
    )

    report = format_metrics_report(metrics)

    with pd.option_context(
            "display.max_rows", None,
            "display.max_columns", None,
            "display.width", 220,
    ):
        print(report)
