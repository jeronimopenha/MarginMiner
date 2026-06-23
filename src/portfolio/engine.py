from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import pandas as pd


INITIAL_QUOTA_VALUE = 1.0
EPSILON = 1e-9


@dataclass(frozen=True)
class PortfolioResult:
    history: pd.DataFrame
    positions: pd.DataFrame
    ledger: pd.DataFrame

    @property
    def latest(self) -> pd.Series | None:
        if self.history.empty:
            return None
        return self.history.iloc[-1]


def _empty_result() -> PortfolioResult:
    return PortfolioResult(
        history=pd.DataFrame(),
        positions=pd.DataFrame(),
        ledger=pd.DataFrame(),
    )


def _normalize_ticker(value) -> str:
    return str(value).strip().upper().removesuffix(".SA")


def _prepare_history(history: pd.DataFrame, ticker: str) -> pd.DataFrame:
    required = {"date", "close"}
    missing = required.difference(history.columns)

    if missing:
        raise ValueError(f"Histórico de {ticker} sem colunas: {sorted(missing)}")

    result = history[["date", "close"]].copy()
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    result["close"] = pd.to_numeric(result["close"], errors="coerce")

    return (
        result.dropna(subset=["close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def _prepare_transactions(transactions: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "id",
        "date",
        "type",
        "ticker",
        "quantity",
        "unit_price",
        "costs",
        "notes",
        "created_at",
    ]

    if transactions is None or transactions.empty:
        return pd.DataFrame(columns=columns)

    result = transactions.copy()

    for column in columns:
        if column not in result.columns:
            result[column] = None

    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    result["type"] = result["type"].astype(str).str.strip().str.lower()
    result["ticker"] = result["ticker"].map(_normalize_ticker)

    for column in ["quantity", "unit_price", "costs"]:
        result[column] = pd.to_numeric(result[column], errors="raise")

    if (~result["type"].isin(["compra", "venda"])).any():
        raise ValueError("Existem lançamentos com tipo inválido.")

    if (result["quantity"] <= 0).any():
        raise ValueError("Existem lançamentos com quantidade não positiva.")

    if (result["unit_price"] <= 0).any():
        raise ValueError("Existem lançamentos com preço não positivo.")

    if (result["costs"] < 0).any():
        raise ValueError("Existem lançamentos com custos negativos.")

    return result[columns].sort_values(
        ["date", "created_at", "id"]
    ).reset_index(drop=True)


def _prepare_income_events(income_events: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "id",
        "position_date",
        "payment_date",
        "ticker",
        "quantity",
        "net_amount",
        "notes",
        "created_at",
    ]

    if income_events is None or income_events.empty:
        return pd.DataFrame(columns=columns)

    result = income_events.copy()

    for column in columns:
        if column not in result.columns:
            result[column] = None

    result["position_date"] = pd.to_datetime(
        result["position_date"]
    ).dt.normalize()
    result["payment_date"] = pd.to_datetime(
        result["payment_date"]
    ).dt.normalize()
    result["ticker"] = result["ticker"].map(_normalize_ticker)
    result["quantity"] = pd.to_numeric(result["quantity"], errors="coerce")
    result["net_amount"] = pd.to_numeric(result["net_amount"], errors="raise")

    if (result["net_amount"] <= 0).any():
        raise ValueError("Existem proventos com valor líquido não positivo.")

    if (result["payment_date"] < result["position_date"]).any():
        raise ValueError("Existe provento com pagamento anterior à posição.")

    return result[columns].sort_values(
        ["position_date", "payment_date", "created_at", "id"]
    ).reset_index(drop=True)


def _prepare_corporate_actions(
    corporate_actions: pd.DataFrame | None,
) -> pd.DataFrame:
    columns = [
        "id",
        "ex_date",
        "credit_date",
        "action_type",
        "source_ticker",
        "target_ticker",
        "factor",
        "cash_amount",
        "notes",
        "created_at",
    ]

    if corporate_actions is None or corporate_actions.empty:
        return pd.DataFrame(columns=columns)

    result = corporate_actions.copy()

    for column in columns:
        if column not in result.columns:
            result[column] = None

    result["ex_date"] = pd.to_datetime(result["ex_date"]).dt.normalize()
    result["credit_date"] = pd.to_datetime(result["credit_date"]).dt.normalize()

    result["action_type"] = (
        result["action_type"]
        .astype(str)
        .str.strip()
        .str.lower()
        .replace(
            {
                "bonificacao": "bonificação",
                "desdobramento": "desdobramento",
                "grupamento": "grupamento",
                "mudanca": "mudança de ticker",
                "mudanca de ticker": "mudança de ticker",
                "conversao": "conversão",
            }
        )
    )

    valid_types = {
        "bonificação",
        "desdobramento",
        "grupamento",
        "mudança de ticker",
        "conversão",
    }

    if (~result["action_type"].isin(valid_types)).any():
        raise ValueError("Existem eventos corporativos com tipo inválido.")

    result["source_ticker"] = result["source_ticker"].map(_normalize_ticker)

    result["target_ticker"] = result["target_ticker"].fillna(
        result["source_ticker"]
    )
    result["target_ticker"] = result["target_ticker"].map(_normalize_ticker)

    result["factor"] = pd.to_numeric(result["factor"], errors="raise")
    result["cash_amount"] = (
        pd.to_numeric(result["cash_amount"], errors="coerce")
        .fillna(0.0)
    )

    if (result["factor"] <= 0).any():
        raise ValueError("Existem eventos corporativos com fator não positivo.")

    if (result["cash_amount"] < 0).any():
        raise ValueError("Existem eventos corporativos com dinheiro negativo.")

    if (result["credit_date"] < result["ex_date"]).any():
        raise ValueError("Existe evento corporativo com crédito anterior à data ex.")

    return result[columns].sort_values(
        ["ex_date", "credit_date", "created_at", "id"]
    ).reset_index(drop=True)


def _first_market_date_on_or_after(
    history: pd.DataFrame,
    target_date: pd.Timestamp,
) -> pd.Timestamp:
    dates = history.loc[history["date"] >= target_date, "date"]

    if dates.empty:
        return target_date

    return dates.iloc[0]


def _adjust_histories_for_corporate_actions(
    histories: dict[str, pd.DataFrame],
    corporate_actions: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    adjusted = {
        ticker: history.copy()
        for ticker, history in histories.items()
    }

    if corporate_actions.empty:
        return adjusted

    same_ticker_actions = corporate_actions[
        corporate_actions["source_ticker"]
        == corporate_actions["target_ticker"]
    ]

    for _, action in same_ticker_actions.iterrows():
        ticker = action["source_ticker"]

        if ticker not in adjusted:
            continue

        factor = float(action["factor"])
        ex_date = action["ex_date"]

        before_event = adjusted[ticker]["date"] < ex_date
        adjusted[ticker].loc[before_event, "close"] *= factor

    return adjusted


def calculate_portfolio(
    transactions: pd.DataFrame,
    income_events: pd.DataFrame | None = None,
    corporate_actions: pd.DataFrame | None = None,
    history_loader: Callable[[str], pd.DataFrame] | None = None,
    final_date: date | pd.Timestamp | None = None,
) -> PortfolioResult:
    transactions = _prepare_transactions(transactions)
    income_events = _prepare_income_events(income_events)
    corporate_actions = _prepare_corporate_actions(corporate_actions)

    if transactions.empty:
        return _empty_result()

    if history_loader is None:
        raise ValueError("Informe uma função history_loader.")

    tickers = set(transactions["ticker"].unique())

    if not income_events.empty:
        tickers.update(income_events["ticker"].unique())

    if not corporate_actions.empty:
        tickers.update(corporate_actions["source_ticker"].unique())
        tickers.update(corporate_actions["target_ticker"].unique())

    tickers = sorted(tickers)

    histories = {
        ticker: _prepare_history(history_loader(ticker), ticker)
        for ticker in tickers
    }

    empty_tickers = [
        ticker
        for ticker, history in histories.items()
        if history.empty
    ]

    if empty_tickers:
        raise ValueError(f"Sem histórico para: {', '.join(empty_tickers)}")

    histories = _adjust_histories_for_corporate_actions(
        histories,
        corporate_actions,
    )

    first_date = transactions["date"].min()
    end = pd.Timestamp(final_date or date.today()).normalize()

    if end < first_date:
        raise ValueError("A data final é anterior ao primeiro lançamento.")

    income_events = income_events.copy()

    if not income_events.empty:
        ex_dates = []

        for _, income in income_events.iterrows():
            ticker = income["ticker"]
            position_date = income["position_date"]
            ex_date = _first_market_date_on_or_after(
                histories[ticker],
                position_date,
            )
            ex_dates.append(ex_date)

        income_events["ex_date"] = ex_dates
    else:
        income_events["ex_date"] = pd.Series(dtype="datetime64[ns]")

    calendar_dates = set(transactions["date"])

    for history in histories.values():
        calendar_dates.update(
            history.loc[
                history["date"].between(first_date, end),
                "date",
            ]
        )

    if not income_events.empty:
        calendar_dates.update(income_events["ex_date"])
        calendar_dates.update(income_events["payment_date"])

    if not corporate_actions.empty:
        calendar_dates.update(corporate_actions["ex_date"])
        calendar_dates.update(corporate_actions["credit_date"])

    all_dates = sorted(
        current_date
        for current_date in calendar_dates
        if first_date <= current_date <= end
    )

    positions = {ticker: 0.0 for ticker in tickers}
    last_prices: dict[str, float] = {}

    cash = 0.0
    receivables = 0.0
    quota_count = 0.0

    external_money_total = 0.0
    income_received_total = 0.0

    history_rows: list[dict] = []
    ledger_rows: list[dict] = []

    histories_by_date = {
        ticker: history.set_index("date")
        for ticker, history in histories.items()
    }

    for current_date in all_dates:
        for ticker, history in histories_by_date.items():
            if current_date not in history.index:
                continue

            market_row = history.loc[current_date]

            if isinstance(market_row, pd.DataFrame):
                market_row = market_row.iloc[-1]

            last_prices[ticker] = float(market_row["close"])

        daily_external_flow = 0.0
        daily_income_received = 0.0

        day_corporate_actions = corporate_actions[
            corporate_actions["credit_date"] == current_date
        ]

        for _, action in day_corporate_actions.iterrows():
            action_type = action["action_type"]
            source_ticker = action["source_ticker"]
            target_ticker = action["target_ticker"]
            factor = float(action["factor"])
            cash_amount = float(action["cash_amount"])

            source_quantity = positions.get(source_ticker, 0.0)

            if source_quantity <= EPSILON:
                continue

            if action_type in {
                "bonificação",
                "desdobramento",
                "grupamento",
            }:
                new_quantity = source_quantity * factor
                quantity_delta = new_quantity - source_quantity

                positions[source_ticker] = new_quantity
                cash += cash_amount

                ledger_rows.append(
                    {
                        "date": current_date,
                        "event": action_type,
                        "ticker": source_ticker,
                        "gross_value": cash_amount,
                        "internal_cash_used": 0.0,
                        "external_flow": 0.0,
                        "cash_after": cash,
                        "quantity_delta": quantity_delta,
                        "corporate_action_id": action["id"],
                    }
                )

            elif action_type in {"mudança de ticker", "conversão"}:
                new_quantity = source_quantity * factor

                positions[source_ticker] = 0.0
                positions[target_ticker] = (
                    positions.get(target_ticker, 0.0)
                    + new_quantity
                )
                cash += cash_amount

                ledger_rows.append(
                    {
                        "date": current_date,
                        "event": action_type,
                        "ticker": f"{source_ticker}->{target_ticker}",
                        "gross_value": cash_amount,
                        "internal_cash_used": 0.0,
                        "external_flow": 0.0,
                        "cash_after": cash,
                        "quantity_delta": new_quantity,
                        "corporate_action_id": action["id"],
                    }
                )

        day_income_rights = income_events[
            income_events["ex_date"] == current_date
        ]

        for _, income in day_income_rights.iterrows():
            amount = float(income["net_amount"])
            receivables += amount

            ledger_rows.append(
                {
                    "date": current_date,
                    "event": "provento a receber",
                    "ticker": income["ticker"],
                    "gross_value": amount,
                    "internal_cash_used": 0.0,
                    "external_flow": 0.0,
                    "cash_after": cash,
                    "receivables_after": receivables,
                    "income_event_id": income["id"],
                }
            )

        day_income_payments = income_events[
            income_events["payment_date"] == current_date
        ]

        for _, income in day_income_payments.iterrows():
            amount = float(income["net_amount"])

            receivables -= amount

            if abs(receivables) < EPSILON:
                receivables = 0.0

            cash += amount
            daily_income_received += amount
            income_received_total += amount

            ledger_rows.append(
                {
                    "date": current_date,
                    "event": "provento pago",
                    "ticker": income["ticker"],
                    "gross_value": amount,
                    "internal_cash_used": 0.0,
                    "external_flow": 0.0,
                    "cash_after": cash,
                    "receivables_after": receivables,
                    "income_event_id": income["id"],
                }
            )

        day_transactions = transactions[
            transactions["date"] == current_date
        ]

        for _, transaction in day_transactions.iterrows():
            ticker = transaction["ticker"]
            transaction_type = transaction["type"]
            quantity = float(transaction["quantity"])
            unit_price = float(transaction["unit_price"])
            costs = float(transaction["costs"])

            last_prices.setdefault(ticker, unit_price)

            if transaction_type == "venda":
                if quantity > positions[ticker] + EPSILON:
                    raise ValueError(
                        f"Venda de {quantity:g} {ticker} em "
                        f"{current_date.date()} excede a posição de "
                        f"{positions[ticker]:g}."
                    )

                proceeds = quantity * unit_price - costs

                if proceeds < -EPSILON:
                    raise ValueError("Custos da venda excedem o valor vendido.")

                positions[ticker] -= quantity
                cash += proceeds

                ledger_rows.append(
                    {
                        "date": current_date,
                        "event": "venda",
                        "ticker": ticker,
                        "gross_value": proceeds,
                        "internal_cash_used": 0.0,
                        "external_flow": 0.0,
                        "cash_after": cash,
                        "transaction_id": transaction["id"],
                    }
                )

                continue

            purchase_total = quantity * unit_price + costs
            internal_cash_used = min(cash, purchase_total)
            external_flow = purchase_total - internal_cash_used

            if external_flow > EPSILON:
                marked_assets_before_flow = sum(
                    position * last_prices.get(position_ticker, 0.0)
                    for position_ticker, position in positions.items()
                )
                equity_before_flow = (
                    marked_assets_before_flow
                    + receivables
                    + cash
                )

                quota_value_before_flow = (
                    equity_before_flow / quota_count
                    if quota_count > EPSILON
                    else INITIAL_QUOTA_VALUE
                )

                quota_count += external_flow / quota_value_before_flow
                external_money_total += external_flow
                daily_external_flow += external_flow
                cash += external_flow

            cash -= purchase_total

            if abs(cash) < EPSILON:
                cash = 0.0

            positions[ticker] += quantity

            ledger_rows.append(
                {
                    "date": current_date,
                    "event": "compra",
                    "ticker": ticker,
                    "gross_value": purchase_total,
                    "internal_cash_used": internal_cash_used,
                    "external_flow": external_flow,
                    "cash_after": cash,
                    "transaction_id": transaction["id"],
                }
            )

        marked_assets = sum(
            position * last_prices.get(ticker, 0.0)
            for ticker, position in positions.items()
        )

        equity = marked_assets + receivables + cash

        quota_value = (
            equity / quota_count
            if quota_count > EPSILON
            else INITIAL_QUOTA_VALUE
        )

        history_rows.append(
            {
                "date": current_date,
                "assets": marked_assets,
                "receivables": receivables,
                "cash": cash,
                "equity": equity,
                "quota_count": quota_count,
                "quota_value": quota_value,
                "return": quota_value / INITIAL_QUOTA_VALUE - 1.0,
                "external_flow": daily_external_flow,
                "external_money_total": external_money_total,
                "new_money_total": external_money_total,
                "income_received": daily_income_received,
                "income_received_total": income_received_total,
            }
        )

    position_rows = []

    for ticker, quantity in positions.items():
        if quantity <= EPSILON:
            continue

        price = last_prices.get(ticker)

        position_rows.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "last_price": price,
                "market_value": (
                    quantity * price
                    if price is not None
                    else None
                ),
            }
        )

    return PortfolioResult(
        history=pd.DataFrame(history_rows),
        positions=pd.DataFrame(position_rows),
        ledger=pd.DataFrame(ledger_rows),
    )