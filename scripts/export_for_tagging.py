#!/usr/bin/env python3
"""
Export events from eval database to JSONL for LLM tagging.

Usage:
    python export_for_tagging.py --db PATH --output PATH [--untagged-only] [--limit N]

Examples:
    # Export all events for tagging
    python export_for_tagging.py \
        --db data/eval_tags.db \
        --output data/events_for_codex.jsonl

    # Export only untagged events
    python export_for_tagging.py \
        --db data/eval_tags.db \
        --output data/events_for_codex.jsonl \
        --untagged-only
"""

import argparse
import sqlite3
import json
from pathlib import Path


def export_events(
    db_path: Path,
    output_path: Path,
    untagged_only: bool = False,
    limit: int = None
) -> int:
    """Export events to JSONL for tagging.
    
    Args:
        db_path: Path to eval_tags database
        output_path: Output JSONL path
        untagged_only: If True, only export events without tags
        limit: Maximum number to export
        
    Returns:
        Number of events exported
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if untagged_only:
        query = """
            SELECT e.*
            FROM events e
            LEFT JOIN tags t ON e.id = t.event_id
            WHERE t.id IS NULL
            ORDER BY e.id
        """
    else:
        query = "SELECT * FROM events ORDER BY id"
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    count = 0
    with open(output_path, 'w') as f:
        for row in rows:
            event = {
                'event_id': f"evt_{row['source_event_id']:06d}",
                'user_message': row['user_message'],
                'timestamp': row['timestamp'],
                'routed_instructions': json.loads(row['routed_instructions'] or '[]'),
                'db_session_id': row['db_session_id']
            }
            f.write(json.dumps(event) + '\n')
            count += 1
    
    conn.close()
    return count


def main():
    parser = argparse.ArgumentParser(description='Export events for LLM tagging')
    parser.add_argument('--db', type=Path, required=True, help='Eval database path')
    parser.add_argument('--output', type=Path, required=True, help='Output JSONL path')
    parser.add_argument('--untagged-only', action='store_true',
                        help='Only export events without tags')
    parser.add_argument('--limit', type=int, help='Maximum events to export')
    
    args = parser.parse_args()
    
    if not args.db.exists():
        print(f"Error: Database not found: {args.db}")
        return 1
    
    count = export_events(args.db, args.output, args.untagged_only, args.limit)
    print(f"Exported {count} events to {args.output}")


if __name__ == '__main__':
    main()
