#!/usr/bin/env python3

import argparse
import os
import sqlite3
import sys


def get_db_path(explicit_path: str | None) -> str:
    if explicit_path:
        return explicit_path
    return os.environ.get('DATABASE_PATH', '/data/udako.db')


def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote TEXT NOT NULL,
            author TEXT,
            category TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )


def parse_quote_line(raw_line: str) -> str | None:
    line = raw_line.strip()
    if not line:
        return None
    if len(line) < 2 or line[0] != '"' or line[-1] != '"':
        raise ValueError(f'Invalid quote line: {raw_line.rstrip()}')
    return line[1:-1].strip()


def load_quotes(path: str) -> list[str]:
    quotes = []
    with open(path, 'r', encoding='utf-8') as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            try:
                quote = parse_quote_line(raw_line)
            except ValueError as exc:
                raise ValueError(f'{path}:{line_number}: {exc}') from exc
            if quote:
                quotes.append(quote)
    return quotes


def main() -> int:
    parser = argparse.ArgumentParser(description='Import quoted lines into the quotes database table.')
    parser.add_argument('quotes_file', help='Text file containing one quote per line in double quotes')
    parser.add_argument('--db', dest='db_path', default=None, help='SQLite database path')
    args = parser.parse_args()

    db_path = get_db_path(args.db_path)
    quotes = load_quotes(args.quotes_file)

    if not quotes:
        print('No quotes found to import.')
        return 0

    db = sqlite3.connect(db_path)
    try:
        ensure_schema(db)
        existing = {row[0] for row in db.execute('SELECT quote FROM quotes')}

        inserted = 0
        for quote in quotes:
            if quote in existing:
                continue
            db.execute('INSERT INTO quotes (quote, is_active) VALUES (?, 1)', (quote,))
            inserted += 1

        db.commit()
    finally:
        db.close()

    print(f'Imported {inserted} quote(s) into {db_path}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())