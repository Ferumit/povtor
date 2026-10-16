"""Точка входа: python main.py [--db ПУТЬ] [--demo]."""
import argparse
from datetime import date
from pathlib import Path

from povtor.db import Storage
from povtor.demo import fill_demo
from povtor.gui import run

DATA = Path(__file__).resolve().parent / "data"


def main():
    parser = argparse.ArgumentParser(description="Повтор — тренажёр карточек с интервальными повторениями")
    parser.add_argument("--db", type=Path, default=DATA / "povtor.sqlite3", help="путь к файлу базы")
    parser.add_argument("--demo", action="store_true",
                        help="открыть демонстрационную базу data/demo.sqlite3 с готовыми колодами")
    args = parser.parse_args()

    path = DATA / "demo.sqlite3" if args.demo else args.db
    is_new = not path.exists()
    storage = Storage(path)
    if args.demo and is_new:
        fill_demo(storage, date.today())
    run(storage)


if __name__ == "__main__":
    main()
