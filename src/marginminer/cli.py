import argparse
import universe
from cache_io import ensure_dirs

def main():
    import sys

    if len(sys.argv) == 1:
        user_input = input("Digite o comando: ")
        sys.argv.extend(user_input.split())

    parser = argparse.ArgumentParser(prog="marginminer")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("sectors")

    tickers_parser = subparsers.add_parser("tickers")
    tickers_parser.add_argument("filename")

    args = parser.parse_args()

    ensure_dirs()

    if args.command == "sectors":
        files = universe.list_sector_files()
        for f in files:
            print(f)

    elif args.command == "tickers":
        tickers = universe.load_sector_tickers(args.filename)
        for t in tickers:
            print(t)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
