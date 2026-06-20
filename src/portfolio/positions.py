import pandas as pd


POSITION_COLUMNS = [
    "ticker",
    "quantity",
]


def calculate_positions(
    transactions: pd.DataFrame,
    until_date=None,
) -> pd.DataFrame:

    if transactions.empty:
        return pd.DataFrame(columns=POSITION_COLUMNS)

    transactions = transactions.copy()

    transactions["date"] = pd.to_datetime(
        transactions["date"]
    ).dt.normalize()

    if until_date is not None:
        until_date = pd.Timestamp(until_date).normalize()

        transactions = transactions[
            transactions["date"] <= until_date
        ]

    transactions = transactions.sort_values(
        ["date", "created_at", "id"]
    )

    positions: dict[str, float] = {}

    for _, transaction in transactions.iterrows():
        ticker = transaction["ticker"]
        transaction_type = transaction["type"]
        quantity = float(transaction["quantity"])

        current_quantity = positions.get(ticker, 0.0)

        if transaction_type == "compra":
            positions[ticker] = current_quantity + quantity

        elif transaction_type == "venda":
            if quantity > current_quantity:
                raise ValueError(
                    f"Venda de {quantity:g} ações de {ticker} "
                    f"excede a posição de {current_quantity:g}."
                )

            positions[ticker] = current_quantity - quantity

        else:
            raise ValueError(
                f"Tipo de lançamento inválido: {transaction_type}"
            )

    rows = [
        {
            "ticker": ticker,
            "quantity": quantity,
        }
        for ticker, quantity in positions.items()
        if quantity > 0
    ]

    return pd.DataFrame(
        rows,
        columns=POSITION_COLUMNS,
    ).sort_values("ticker").reset_index(drop=True)