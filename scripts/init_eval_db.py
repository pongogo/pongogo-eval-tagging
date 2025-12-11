#!/usr/bin/env python3
"""
Initialize the eval tagging database.

Usage:
    python init_eval_db.py [--db PATH]

Examples:
    python init_eval_db.py
    python init_eval_db.py --db data/eval_tags.db
"""

import argparse
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / 'data' / 'eval_tags.db'
SCHEMA_PATH = Path(__file__).parent.parent / 'schema' / 'eval_db_schema.sql'


def init_database(db_path: Path) -> None:
    """Initialize the eval database with schema."""
    
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read schema
    schema_sql = SCHEMA_PATH.read_text()
    
    # Create database and apply schema
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.commit()
    
    # Verify tables created
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Database initialized: {db_path}")
    print(f"Tables created: {', '.join(tables)}")
    
    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Initialize eval tagging database')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB_PATH,
                        help=f'Database path (default: {DEFAULT_DB_PATH})')
    
    args = parser.parse_args()
    init_database(args.db)


if __name__ == '__main__':
    main()
