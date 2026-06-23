from src.portfolio.corporate_actions_storage import (
    add_corporate_action,
)


actions = add_corporate_action(
    ex_date="2025-09-02",
    credit_date="2025-09-04",
    action_type="bonificação",
    source_ticker="BEES3",
    target_ticker="BEES3",
    factor=1.10,
    notes="Uma nova ação para cada dez ações",
)

print(actions)