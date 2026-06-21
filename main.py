import pandas as pd

from src.data.stocks import daily_stock_history


history = daily_stock_history("BEES3")

history["date"] = pd.to_datetime(
    history["date"]
).dt.normalize()

print(
    history.loc[
        history["date"] == "2024-10-15",
        [
            "date",
            "close",
            "adj_close",
        ],
    ]
)