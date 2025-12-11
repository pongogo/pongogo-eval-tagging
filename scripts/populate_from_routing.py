#!/usr/bin/env python3
"""
Populate eval database from production routing_events database.

Usage:
    python populate_from_routing.py --source PATH --target PATH [--exclude-tainted] [--batch NAME]

Examples:
    # Import all clean events
    python populate_from_routing.py \
        --source /path/to/routing_log-production.db \
        --target data/eval_tags.db \
        --exclude-tainted \
        --batch "initial_import_2025-12"

    # Import specific ID range
    python populate_from_routing.py \
        --source /path/to/routing_log-production.db \
        --target data/eval_tags.db \
        --min-id 100 --max-id 500
"""

import argparse
import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime


def extract_instructions(formatted_context: str) -> list:
    """Extract instruction names from formatted_context text."""
    if not formatted_context:
        return []
    # Pattern: ### N. instruction_name.instructions (category: X, relevance: N)
    pattern = r'### \d+\. (\w+\.instructions)'
    return re.findall(pattern, formatted_context)


def populate_events(
    source_db: Path,
    target_db: Path,
    exclude_tainted: bool = True,
    min_id: int = None,
    max_id: int = None,
    batch_name: str = None
) -> dict:
    """Populate eval database from routing_events.
    
    Args:
        source_db: Path to routing_log database
        target_db: Path to eval_tags database
        exclude_tainted: Skip events with exclude_reason set
        min_id: Minimum event ID to import
        max_id: Maximum event ID to import
        batch_name: Batch identifier for this import
        
    Returns:
        Dict with import statistics
    """
    stats = {
        'source_count': 0,
        'imported': 0,
        'skipped_existing': 0,
        'errors': []
    }
    
    if batch_name is None:
        batch_name = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Connect to source
    source_conn = sqlite3.connect(source_db)
    source_conn.row_factory = sqlite3.Row
    source_cursor = source_conn.cursor()
    
    # Build query
    conditions = []
    params = []
    
    if exclude_tainted:
        conditions.append("exclude_reason IS NULL")
    
    if min_id is not None:
        conditions.append("id >= ?")
        params.append(min_id)
    
    if max_id is not None:
        conditions.append("id <= ?")
        params.append(max_id)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    source_cursor.execute(f"""
        SELECT 
            id,
            message_clean,
            message_excerpt,
            timestamp,
            session_id,
            formatted_context,
            instruction_count
        FROM routing_events
        WHERE {where_clause}
        ORDER BY id
    """, params)
    
    source_rows = source_cursor.fetchall()
    stats['source_count'] = len(source_rows)
    
    # Connect to target
    target_conn = sqlite3.connect(target_db)
    target_cursor = target_conn.cursor()
    
    for row in source_rows:
        msg = row['message_clean'] or row['message_excerpt'] or ''
        instructions = extract_instructions(row['formatted_context'])
        
        try:
            target_cursor.execute("""
                INSERT INTO events (
                    source_event_id,
                    source_db_path,
                    user_message,
                    timestamp,
                    db_session_id,
                    routed_instructions,
                    instruction_count,
                    import_batch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['id'],
                str(source_db),
                msg,
                row['timestamp'],
                row['session_id'],
                json.dumps(instructions),
                row['instruction_count'],
                batch_name
            ))
            stats['imported'] += 1
            
        except sqlite3.IntegrityError:
            # Already exists
            stats['skipped_existing'] += 1
        except Exception as e:
            stats['errors'].append(f"Event {row['id']}: {e}")
    
    target_conn.commit()
    source_conn.close()
    target_conn.close()
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Populate eval DB from routing_events')
    parser.add_argument('--source', type=Path, required=True,
                        help='Source routing_log database path')
    parser.add_argument('--target', type=Path, required=True,
                        help='Target eval_tags database path')
    parser.add_argument('--exclude-tainted', action='store_true',
                        help='Exclude events with exclude_reason set')
    parser.add_argument('--min-id', type=int, help='Minimum event ID')
    parser.add_argument('--max-id', type=int, help='Maximum event ID')
    parser.add_argument('--batch', type=str, help='Batch name for this import')
    
    args = parser.parse_args()
    
    if not args.source.exists():
        print(f"Error: Source database not found: {args.source}")
        return 1
    
    if not args.target.exists():
        print(f"Error: Target database not found: {args.target}")
        print(f"Run: python scripts/init_eval_db.py --db {args.target}")
        return 1
    
    stats = populate_events(
        source_db=args.source,
        target_db=args.target,
        exclude_tainted=args.exclude_tainted,
        min_id=args.min_id,
        max_id=args.max_id,
        batch_name=args.batch
    )
    
    print(f"\nImport Statistics:")
    print(f"  Source events: {stats['source_count']}")
    print(f"  Imported: {stats['imported']}")
    print(f"  Skipped (existing): {stats['skipped_existing']}")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):\n")
        for error in stats['errors'][:10]:
            print(f"  - {error}")


if __name__ == '__main__':
    main()
