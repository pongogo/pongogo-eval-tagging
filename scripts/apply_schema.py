#!/usr/bin/env python3
"""
Apply Epic #234 collaboration_tags schema extension to existing evaluation_results.db.

Usage:
    python apply_schema.py --db PATH

Examples:
    python apply_schema.py --db ~/.observability_db/observability_db-learning/evaluation_results.db
"""

import argparse
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / 'schema' / 'eval_db_schema.sql'


def apply_schema(db_path: Path) -> dict:
    """Apply Epic #234 schema extension to existing evaluation database.
    
    Args:
        db_path: Path to evaluation_results.db
        
    Returns:
        Dict with application results
    """
    results = {
        'tables_before': [],
        'tables_after': [],
        'views_created': [],
        'indexes_created': [],
        'errors': []
    }
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    results['tables_before'] = [row[0] for row in cursor.fetchall()]
    
    # Verify evaluation_dataset exists
    if 'evaluation_dataset' not in results['tables_before']:
        results['errors'].append(
            "evaluation_dataset table not found. This schema extends the existing eval schema. "
            "See docs/observability/evaluation_schema.sql"
        )
        conn.close()
        return results
    
    # Read and apply schema
    schema_sql = SCHEMA_PATH.read_text()
    
    try:
        conn.executescript(schema_sql)
        conn.commit()
    except Exception as e:
        results['errors'].append(f"Schema application failed: {e}")
        conn.close()
        return results
    
    # Check results
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    results['tables_after'] = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
    results['views_created'] = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_collab%'")
    results['indexes_created'] = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return results


def main():
    parser = argparse.ArgumentParser(description='Apply Epic #234 schema extension')
    parser.add_argument('--db', type=Path, required=True,
                        help='Path to evaluation_results.db')
    
    args = parser.parse_args()
    
    if not args.db.exists():
        print(f"Error: Database not found: {args.db}")
        return 1
    
    results = apply_schema(args.db)
    
    if results['errors']:
        print("ERRORS:")
        for error in results['errors']:
            print(f"  - {error}")
        return 1
    
    new_tables = set(results['tables_after']) - set(results['tables_before'])
    
    print(f"Schema applied successfully to: {args.db}")
    print(f"  New tables: {', '.join(new_tables) if new_tables else '(none, already existed)'}") 
    print(f"  Views: {', '.join(results['views_created'])}")
    print(f"  Indexes: {', '.join(results['indexes_created'])}")


if __name__ == '__main__':
    main()
