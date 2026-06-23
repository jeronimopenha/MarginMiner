from pathlib import Path
from uuid import uuid4

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PORTFOLIO_DIR = PROJECT_ROOT / "storage" / "portfolio"
ACTIONS_PATH = PORTFOLIO_DIR / "corporate_actions.parquet"

ACTION_COLUMNS = [
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


def empty_corporate_actions() -> pd.DataFrame:
    return pd.DataFrame(columns=ACTION_COLUMNS)


def load_corporate_actions() -> pd.DataFrame:
    if not ACTIONS_PATH.exists():
        return empty_corporate_actions()

    actions = pd.read_parquet(ACTIONS_PATH)

    for column in ["ex_date", "credit_date"]:
        actions[column] = (
            pd.to_datetime(actions[column])
            .dt.normalize()
        )

    return actions[
        ACTION_COLUMNS
    ].sort_values(
        ["ex_date", "created_at", "id"]
    ).reset_index(drop=True)


def save_corporate_actions(
        actions: pd.DataFrame,
) -> None:
    PORTFOLIO_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    actions = actions.copy()

    for column in ["ex_date", "credit_date"]:
        actions[column] = (
            pd.to_datetime(actions[column])
            .dt.normalize()
        )

    actions[ACTION_COLUMNS].to_parquet(
        ACTIONS_PATH,
        index=False,
    )


def add_corporate_action(
        ex_date,
        credit_date,
        action_type: str,
        source_ticker: str,
        target_ticker: str | None,
        factor: float,
        cash_amount: float = 0.0,
        notes: str = "",
) -> pd.DataFrame:
    action_type = action_type.strip().lower()

    aliases = {
        "bonificacao": "bonificação",
        "desdobramento": "desdobramento",
        "grupamento": "grupamento",
        "mudanca": "mudança de ticker",
        "conversao": "conversão",
        "incorporacao": "conversão",
    }

    action_type = aliases.get(
        action_type,
        action_type,
    )

    valid_types = {
        "bonificação",
        "desdobramento",
        "grupamento",
        "mudança de ticker",
        "conversão",
    }

    if action_type not in valid_types:
        raise ValueError(
            "Tipo de evento corporativo inválido."
        )

    ex_date = pd.Timestamp(ex_date).normalize()
    credit_date = pd.Timestamp(
        credit_date
    ).normalize()

    if credit_date < ex_date:
        raise ValueError(
            "O crédito não pode ser anterior à data ex."
        )

    source_ticker = (
        source_ticker
        .strip()
        .upper()
        .removesuffix(".SA")
    )

    if not source_ticker:
        raise ValueError(
            "Informe o ativo de origem."
        )

    if target_ticker:
        target_ticker = (
            target_ticker
            .strip()
            .upper()
            .removesuffix(".SA")
        )
    else:
        target_ticker = source_ticker

    factor = float(factor)
    cash_amount = round(float(cash_amount), 2)

    if factor <= 0:
        raise ValueError(
            "O fator precisa ser positivo."
        )

    if cash_amount < 0:
        raise ValueError(
            "O valor residual não pode ser negativo."
        )

    if action_type in {
        "mudança de ticker",
        "conversão",
    }:
        if target_ticker == source_ticker:
            raise ValueError(
                "Informe um ativo de destino diferente."
            )

    actions = load_corporate_actions()

    new_action = pd.DataFrame(
        [
            {
                "id": uuid4().hex,
                "ex_date": ex_date,
                "credit_date": credit_date,
                "action_type": action_type,
                "source_ticker": source_ticker,
                "target_ticker": target_ticker,
                "factor": factor,
                "cash_amount": cash_amount,
                "notes": notes.strip(),
                "created_at": pd.Timestamp.now(),
            }
        ]
    )

    if actions.empty:
        actions = new_action
    else:
        actions = pd.concat(
            [actions, new_action],
            ignore_index=True,
        )

    save_corporate_actions(actions)

    return load_corporate_actions()


def delete_corporate_action(
        action_id: str,
) -> pd.DataFrame:
    actions = load_corporate_actions()

    if action_id not in actions["id"].values:
        raise ValueError(
            "Evento corporativo não encontrado."
        )

    actions = actions[
        actions["id"] != action_id
        ].copy()

    save_corporate_actions(actions)

    return load_corporate_actions()
