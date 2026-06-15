import sys
from src.data.selic import selic_periods_row

if __name__ == "__main__":
    df = selic_periods_row()

    print(df)
    # df = daily_selic_10y()

    # print(df.head())
    # print(df.tail())
    # print(f"Linhas: {len(df)}")
