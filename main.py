import pandas as pd

from src.portfolio.engine import calculate_portfolio


transactions = pd.DataFrame(
    [
        {
            "id": "1",
            "date": "2026-01-02",
            "created_at": "2026-01-02 10:00",
            "type": "compra",
            "ticker": "TEST3",
            "quantity": 100,
            "unit_price": 10.00,
            "costs": 0.0,
        }
    ]
)

income_events = pd.DataFrame(
    [
        {
            "id": "p1",
            "position_date": "2026-01-02",
            "payment_date": "2026-01-04",
            "ticker": "TEST3",
            "net_amount": 50.00,
        }
    ]
)

prices = pd.DataFrame(
    [
        {
            "date": "2026-01-02",
            "close": 10.00,
        },
        {
            "date": "2026-01-03",
            "close": 9.50,
        },
        {
            "date": "2026-01-04",
            "close": 9.50,
        },
    ]
)


def test_history_loader(ticker):
    return prices


result = calculate_portfolio(
    transactions=transactions,
    income_events=income_events,
    history_loader=test_history_loader,
    final_date="2026-01-04",
)

print(result.history)
print()
print(result.positions)
print()
print(result.ledger)