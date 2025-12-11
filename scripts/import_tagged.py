#!/usr/bin/env python3
"""
Import tagged events back into Pongogo database.

Usage:
    python import_tagged.py --input PATH --db PATH [--dry-run]

Examples:
    # Preview import
    python import_tagged.py \
        --input ../data/tagged_events.jsonl \
        --db ../../.observability_db/observability_db-production/routing_log-production.db \
        --dry-run

    # Actual import
    python import_tagged.py \
        --input ../data/tagged_events.jsonl \
        --db ../../.observability_db/observability_db-production/routing_log-production.db
"""

import argparse
import json
import sqlite3
from pathlib import Path


def ensure_tag_columns(conn: sqlite3.Connection) -> None:
    """Ensure tag columns exist in routing_events table."""
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(routing_events)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # Tag columns to add
    tag_columns = [
        ("tag_is_new_request", "INTEGER"),  # 0/1 for boolean
        ("tag_is_followup", "INTEGER"),
        ("tag_is_correction", "INTEGER"),
        ("tag_request_type", "TEXT"),
        ("tag_expected_outcome", "TEXT"),
        ("tag_session_id", "TEXT"),
        ("tag_request_sequence", "INTEGER"),
        ("tag_confidence", "TEXT"),
        ("tag_notes", "TEXT"),
        ("tag_source", "TEXT"),  # Which LLM tagged this
        ("tag_timestamp", "TEXT")  # When it was tagged
    ]
    
    for col_name, col_type in tag_columns:
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE routing_events ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
    
    conn.commit()


def import_tags(
    input_path: str,
    db_path: str,
    dry_run: bool = False,
    source: str = "unknown"
) -> dict:
    """Import tagged events into database.
    
    Args:
        input_path: Path to tagged_events.jsonl
        db_path: Path to routing_log database
        dry_run: If True, validate but don't write
        source: Tag source identifier (e.g., "codex", "claude")
        
    Returns:
        Dict with import statistics
    """
    from datetime import datetime
    
    stats = {
        'total': 0,
        'matched': 0,
        'not_found': 0,
        'errors': []
    }
    
    # Load tagged events
    tagged_events = []
    with open(input_path) as f:
        for line_num, line in enumerate(f, 1):
            try:
                tagged_events.append(json.loads(line))
            except json.JSONDecodeError as e:
                stats['errors'].append(f"Line {line_num}: JSON parse error - {e}")
    
    stats['total'] = len(tagged_events)
    
    if dry_run:
        print(f"DRY RUN: Would import {stats['total']} tagged events")
        # Validate format
        for event in tagged_events:
            if 'event_id' not in event:
                stats['errors'].append(f"Missing event_id in {event}")
            if 'tags' not in event:
                stats['errors'].append(f"Missing tags in {event}")
        return stats
    
    conn = sqlite3.connect(db_path)
    ensure_tag_columns(conn)
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    for event in tagged_events:
        event_id = event.get('event_id', '')
        tags = event.get('tags', {})
        
        # Extract numeric ID from evt_NNNNNN format
        try:
            db_id = int(event_id.replace('evt_', ''))
        except ValueError:
            stats['errors'].append(f"Invalid event_id format: {event_id}")
            continue
        
        # Check event exists
        cursor.execute("SELECT id FROM routing_events WHERE id = ?", (db_id,))
        if not cursor.fetchone():
            stats['not_found'] += 1
            continue
        
        # Update with tags
        cursor.execute("""
            UPDATE routing_events SET
                tag_is_new_request = ?,
                tag_is_followup = ?,
                tag_is_correction = ?,
                tag_request_type = ?,
                tag_expected_outcome = ?,
                tag_session_id = ?,
                tag_request_sequence = ?,
                tag_confidence = ?,
                tag_notes = ?,
                tag_source = ?,
                tag_timestamp = ?
            WHERE id = ?
        """, (
            1 if tags.get('is_new_request') else 0,
            1 if tags.get('is_followup') else 0,
            1 if tags.get('is_correction') else 0,
            tags.get('request_type'),
            tags.get('expected_outcome'),
            tags.get('session_id'),
            tags.get('request_sequence'),
            tags.get('confidence'),
            tags.get('notes'),
            source,
            timestamp,
            db_id
        ))
        
        stats['matched'] += 1
    
    conn.commit()
    conn.close()
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Import tagged events into database')
    parser.add_argument('--input', required=True, help='Path to tagged_events.jsonl')
    parser.add_argument('--db', required=True, help='Path to routing_log database')
    parser.add_argument('--dry-run', action='store_true', help='Validate without importing')
    parser.add_argument('--source', default='unknown', help='Tag source identifier')
    
    args = parser.parse_args()
    
    stats = import_tags(
        input_path=args.input,
        db_path=args.db,
        dry_run=args.dry_run,
        source=args.source
    )
    
    print(f"\nImport Statistics:")
    print(f"  Total events: {stats['total']}")
    print(f"  Matched: {stats['matched']}")
    print(f"  Not found: {stats['not_found']}")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):\n")
        for error in stats['errors'][:10]:  # Show first 10
            print(f"  - {error}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")


if __name__ == '__main__':
    main()
