from pathlib import Path
from uuid import uuid4

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PORTFOLIO_DIR = PROJECT_ROOT / "storage" / "portfolio"
INCOME_PATH = PORTFOLIO_DIR / "income_events.parquet"

INCOME_COLUMNS = [
    "id",
    "position_date",
    "payment_date",
    "ticker",
    "type",
    "quantity",
    "gross_amount",
    "tax_rate",
    "tax_amount",
    "net_amount",
    "notes",
    "created_at",
]


def empty_income_events() -> pd.DataFrame:
    return pd.DataFrame(columns=INCOME_COLUMNS)


def load_income_events() -> pd.DataFrame:
    if not INCOME_PATH.exists():
        return empty_income_events()

    events = pd.read_parquet(INCOME_PATH)

    missing_columns = [
        column
        for column in INCOME_COLUMNS
        if column not in events.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Colunas ausentes no Parquet: {missing_columns}"
        )

    for column in ["position_date", "payment_date"]:
        events[column] = (
            pd.to_datetime(events[column])
            .dt.normalize()
        )

    return events.sort_values(
        ["payment_date", "created_at", "id"]
    ).reset_index(drop=True)


def save_income_events(events: pd.DataFrame) -> None:
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)

    events = events.copy()

    for column in ["position_date", "payment_date"]:
        events[column] = (
            pd.to_datetime(events[column])
            .dt.normalize()
        )

    events = events[INCOME_COLUMNS]

    events.to_parquet(
        INCOME_PATH,
        index=False,
    )


def add_income_event(
    position_date,
    payment_date,
    ticker: str,
    income_type: str,
    quantity: float,
    gross_amount: float,
    tax_rate: float | None = None,
    net_amount: float | None = None,
    notes: str = "",
) -> pd.DataFrame:

    position_date = pd.Timestamp(
        position_date
    ).normalize()

    payment_date = pd.Timestamp(
        payment_date
    ).normalize()

    ticker = ticker.strip().upper().removesuffix(".SA")
    income_type = income_type.strip().lower()

    aliases = {
        "div": "dividendo",
        "dividendos": "dividendo",
        "jscp": "jcp",
        "js cp": "jcp",
    }

    income_type = aliases.get(
        income_type,
        income_type,
    )

    if income_type not in {"dividendo", "jcp"}:
        raise ValueError(
            "O tipo precisa ser 'dividendo' ou 'jcp'."
        )

    if not ticker:
        raise ValueError("Informe o ticker.")

    if quantity <= 0:
        raise ValueError(
            "A quantidade de ações precisa ser positiva."
        )

    if gross_amount <= 0:
        raise ValueError(
            "O valor bruto precisa ser positivo."
        )

    if payment_date < position_date:
        raise ValueError(
            "A data de pagamento não pode ser "
            "anterior à data-com."
        )

    gross_amount = round(
        float(gross_amount),
        2,
    )

    if income_type == "dividendo":
        tax_rate = 0.0
        tax_amount = 0.0
        net_amount = gross_amount

    else:
        if tax_rate is None:
            tax_rate = 0.175

        tax_rate = float(tax_rate)

        if not 0 <= tax_rate <= 1:
            raise ValueError(
                "A alíquota precisa estar entre 0 e 1."
            )

        if net_amount is None:
            tax_amount = round(
                gross_amount * tax_rate,
                2,
            )

            net_amount = round(
                gross_amount - tax_amount,
                2,
            )

        else:
            net_amount = round(
                float(net_amount),
                2,
            )

            if not 0 < net_amount <= gross_amount:
                raise ValueError(
                    "O valor líquido precisa ser positivo "
                    "e não pode superar o valor bruto."
                )

            tax_amount = round(
                gross_amount - net_amount,
                2,
            )

    events = load_income_events()

    new_event = pd.DataFrame(
        [
            {
                "id": uuid4().hex,
                "position_date": position_date,
                "payment_date": payment_date,
                "ticker": ticker,
                "type": income_type,
                "quantity": float(quantity),
                "gross_amount": gross_amount,
                "tax_rate": tax_rate,
                "tax_amount": tax_amount,
                "net_amount": net_amount,
                "notes": notes.strip(),
                "created_at": pd.Timestamp.now(),
            }
        ]
    )

    if events.empty:
        events = new_event
    else:
        events = pd.concat(
            [events, new_event],
            ignore_index=True,
        )

    save_income_events(events)

    return load_income_events()

def delete_income_event(
    event_id: str,
) -> pd.DataFrame:

    events = load_income_events()

    if event_id not in events["id"].values:
        raise ValueError("Provento não encontrado.")

    events = events[
        events["id"] != event_id
    ].copy()

    save_income_events(events)

    return load_income_events()