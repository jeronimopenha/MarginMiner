from src.data.benchmarks import ibov_history, ifix_history

if __name__ == "__main__":
    ibov = ibov_history()
    ifix = ifix_history()

    print("IBOV")
    print(ibov.head())
    print(ibov.tail())
    print(ibov.shape)

    print()

    print("IFIX")
    print(ifix.head())
    print(ifix.tail())
    print(ifix.shape)
