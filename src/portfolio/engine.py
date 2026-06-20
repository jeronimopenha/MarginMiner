from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.data.stocks import daily_stock_history
from src.portfolio.income_storage import load_income_events
from src.portfolio.storage import load_transactions


INITIAL_QUOTA_VALUE = 1.0
EPSILON = 1e-9


@dataclass
class PortfolioResult:
    history: pd.DataFrame
    positions: pd.DataFrame
    ledger: pd.DataFrame

    @property
    def latest(self):
        if self.history.empty:
            return None

        return self.history.iloc[-1]


def prepare_history(
    history: pd.DataFrame,
) -> pd.DataFrame:

    history = history[
        ["date", "close"]
    ].copy()

    history["date"] = (
        pd.to_datetime(history["date"])
        .dt.normalize()
    )

    history["close"] = pd.to_numeric(
        history["close"],
        errors="coerce",
    )

    return (
        history
        .dropna(subset=["close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def find_ex_date(
    history: pd.DataFrame,
    position_date,
):
    position_date = pd.Timestamp(
        position_date
    ).normalize()

    later_dates = history[
        history["date"] > position_date
    ]["date"]

    if later_dates.empty:
        return None

    return later_dates.iloc[0]


def calculate_portfolio(
    transactions: pd.DataFrame,
    income_events: pd.DataFrame,
    history_loader=daily_stock_history,
    final_date=None,
) -> PortfolioResult:

    if transactions.empty:
        empty = pd.DataFrame()

        return PortfolioResult(
            history=empty,
            positions=empty,
            ledger=empty,
        )

    transactions = transactions.copy()
    income_events = income_events.copy()

    transactions["date"] = (
        pd.to_datetime(transactions["date"])
        .dt.normalize()
    )

    for column in ["position_date", "payment_date"]:
        if not income_events.empty:
            income_events[column] = (
                pd.to_datetime(income_events[column])
                .dt.normalize()
            )

    final_date = pd.Timestamp(
        final_date or date.today()
    ).normalize()

    tickers = sorted(
        set(transactions["ticker"])
        | set(income_events["ticker"])
    )

    histories = {
        ticker: prepare_history(
            history_loader(ticker)
        )
        for ticker in tickers
    }

    for ticker, history in histories.items():
        if history.empty:
            raise ValueError(
                f"Não existe histórico para {ticker}."
            )

    if not income_events.empty:
        income_events["ex_date"] = income_events.apply(
            lambda event: find_ex_date(
                histories[event["ticker"]],
                event["position_date"],
            ),
            axis=1,
        )

    first_date = transactions["date"].min()

    calendar_dates = set(
        transactions["date"]
    )

    for history in histories.values():
        dates = history[
            history["date"].between(
                first_date,
                final_date,
            )
        ]["date"]

        calendar_dates.update(dates)

    if not income_events.empty:
        calendar_dates.update(
            income_events[
                income_events["payment_date"] <= final_date
            ]["payment_date"]
        )

        calendar_dates.update(
            income_events[
                income_events["ex_date"].notna()
                & (income_events["ex_date"] <= final_date)
            ]["ex_date"]
        )

    calendar_dates = sorted(calendar_dates)

    history_indexes = {
        ticker: history.set_index("date")
        for ticker, history in histories.items()
    }

    positions = {
        ticker: 0.0
        for ticker in tickers
    }

    last_prices = {}

    cash = 0.0
    receivables = 0.0

    quota_count = 0.0
    total_external_money = 0.0

    receivables_by_event = {}

    history_rows = []
    ledger_rows = []

    transactions = transactions.sort_values(
        ["date", "created_at", "id"]
    )

    for current_date in calendar_dates:
        if current_date > final_date:
            break

        # Atualiza os preços de fechamento.
        for ticker, history in history_indexes.items():
            if current_date in history.index:
                last_prices[ticker] = float(
                    history.loc[current_date, "close"]
                )

        # Reconhece o provento como valor a receber na data ex.
        if not income_events.empty:
            entitlement_events = income_events[
                income_events["ex_date"] == current_date
            ]

            for _, event in entitlement_events.iterrows():
                value = float(event["net_amount"])

                receivables += value
                receivables_by_event[event["id"]] = value

                ledger_rows.append(
                    {
                        "date": current_date,
                        "event": "provento a receber",
                        "ticker": event["ticker"],
                        "value": value,
                        "external_flow": 0.0,
                    }
                )

        # Na data do pagamento, transforma o recebível em caixa.
        if not income_events.empty:
            payment_events = income_events[
                income_events["payment_date"]
                == current_date
            ]

            for _, event in payment_events.iterrows():
                value = receivables_by_event.pop(
                    event["id"],
                    0.0,
                )

                receivables -= value
                cash += value

                ledger_rows.append(
                    {
                        "date": current_date,
                        "event": "provento pago",
                        "ticker": event["ticker"],
                        "value": value,
                        "external_flow": 0.0,
                    }
                )

        daily_external_flow = 0.0

        daily_transactions = transactions[
            transactions["date"] == current_date
        ]

        for _, transaction in daily_transactions.iterrows():
            ticker = transaction["ticker"]
            quantity = float(transaction["quantity"])
            unit_price = float(transaction["unit_price"])
            costs = float(transaction["costs"])

            last_prices.setdefault(
                ticker,
                unit_price,
            )

            if transaction["type"] == "venda":
                if quantity > positions[ticker] + EPSILON:
                    raise ValueError(
                        f"Venda de {quantity:g} {ticker} "
                        f"excede a posição de "
                        f"{positions[ticker]:g}."
                    )

                sale_value = (
                    quantity * unit_price
                    - costs
                )

                positions[ticker] -= quantity
                cash += sale_value

                ledger_rows.append(
                    {
                        "date": current_date,
                        "event": "venda",
                        "ticker": ticker,
                        "value": sale_value,
                        "external_flow": 0.0,
                    }
                )

                continue

            purchase_value = (
                quantity * unit_price
                + costs
            )

            internal_cash_used = min(
                cash,
                purchase_value,
            )

            external_flow = (
                purchase_value
                - internal_cash_used
            )

            if external_flow > EPSILON:
                assets_before_flow = sum(
                    positions[position_ticker]
                    * last_prices.get(
                        position_ticker,
                        0.0,
                    )
                    for position_ticker in positions
                )

                equity_before_flow = (
                    assets_before_flow
                    + cash
                    + receivables
                )

                if quota_count > EPSILON:
                    quota_value_before_flow = (
                        equity_before_flow
                        / quota_count
                    )
                else:
                    quota_value_before_flow = (
                        INITIAL_QUOTA_VALUE
                    )

                new_quotas = (
                    external_flow
                    / quota_value_before_flow
                )

                quota_count += new_quotas
                cash += external_flow

                total_external_money += external_flow
                daily_external_flow += external_flow

            cash -= purchase_value
            positions[ticker] += quantity

            if abs(cash) < EPSILON:
                cash = 0.0

            ledger_rows.append(
                {
                    "date": current_date,
                    "event": "compra",
                    "ticker": ticker,
                    "value": purchase_value,
                    "internal_cash_used": (
                        internal_cash_used
                    ),
                    "external_flow": external_flow,
                }
            )

        assets = sum(
            positions[ticker]
            * last_prices.get(ticker, 0.0)
            for ticker in positions
        )

        equity = (
            assets
            + cash
            + receivables
        )

        if quota_count > EPSILON:
            quota_value = (
                equity / quota_count
            )
        else:
            quota_value = INITIAL_QUOTA_VALUE

        history_rows.append(
            {
                "date": current_date,
                "assets": assets,
                "receivables": receivables,
                "cash": cash,
                "equity": equity,
                "quota_count": quota_count,
                "quota_value": quota_value,
                "return": (
                    quota_value
                    / INITIAL_QUOTA_VALUE
                    - 1
                ),
                "external_flow": daily_external_flow,
                "external_money_total": (
                    total_external_money
                ),
            }
        )

    position_rows = []

    for ticker, quantity in positions.items():
        if quantity <= EPSILON:
            continue

        price = last_prices.get(ticker, 0.0)

        position_rows.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "last_price": price,
                "market_value": quantity * price,
            }
        )

    return PortfolioResult(
        history=pd.DataFrame(history_rows),
        positions=pd.DataFrame(position_rows),
        ledger=pd.DataFrame(ledger_rows),
    )


def calculate_saved_portfolio() -> PortfolioResult:
    return calculate_portfolio(
        transactions=load_transactions(),
        income_events=load_income_events(),
    )