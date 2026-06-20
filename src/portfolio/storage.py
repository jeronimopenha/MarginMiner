from pathlib import Path
from uuid import uuid4

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PORTFOLIO_DIR = PROJECT_ROOT / "storage" / "portfolio"
TRANSACTIONS_PATH = PORTFOLIO_DIR / "transactions.parquet"

TRANSACTION_COLUMNS = [
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


def empty_transactions() -> pd.DataFrame:
    return pd.DataFrame(columns=TRANSACTION_COLUMNS)


def load_transactions() -> pd.DataFrame:
    if not TRANSACTIONS_PATH.exists():
        return empty_transactions()

    transactions = pd.read_parquet(TRANSACTIONS_PATH)

    transactions["date"] = pd.to_datetime(
        transactions["date"]
    ).dt.normalize()

    return transactions.sort_values(
        ["date", "created_at", "id"]
    ).reset_index(drop=True)


def save_transactions(transactions: pd.DataFrame) -> None:
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)

    transactions = transactions.copy()

    transactions["date"] = pd.to_datetime(
        transactions["date"]
    ).dt.normalize()

    transactions.to_parquet(
        TRANSACTIONS_PATH,
        index=False,
    )


def add_transaction(
        transaction_date,
        transaction_type: str,
        ticker: str,
        quantity: float,
        unit_price: float,
        costs: float = 0.0,
        notes: str = "",
) -> pd.DataFrame:
    transaction_type = transaction_type.strip().lower()
    ticker = ticker.strip().upper().removesuffix(".SA")

    if transaction_type not in {"compra", "venda"}:
        raise ValueError("O tipo precisa ser 'compra' ou 'venda'.")

    if not ticker:
        raise ValueError("Informe o ticker.")

    if quantity <= 0:
        raise ValueError("A quantidade precisa ser positiva.")

    if unit_price <= 0:
        raise ValueError("O preço unitário precisa ser positivo.")

    if costs < 0:
        raise ValueError("Os custos não podem ser negativos.")

    transactions = load_transactions()

    new_transaction = pd.DataFrame(
        [
            {
                "id": uuid4().hex,
                "date": pd.Timestamp(transaction_date).normalize(),
                "type": transaction_type,
                "ticker": ticker,
                "quantity": float(quantity),
                "unit_price": float(unit_price),
                "costs": float(costs),
                "notes": notes.strip(),
                "created_at": pd.Timestamp.now(),
            }
        ]
    )

    if transactions.empty:
        transactions = new_transaction
    else:
        transactions = pd.concat(
            [transactions, new_transaction],
            ignore_index=True,
        )

    save_transactions(transactions)

    return load_transactions()

def delete_transaction(transaction_id: str) -> pd.DataFrame:
    transactions = load_transactions()

    if transaction_id not in transactions["id"].values:
        raise ValueError("Lançamento não encontrado.")

    transactions = transactions[
        transactions["id"] != transaction_id
    ].copy()

    save_transactions(transactions)

    return load_transactions()