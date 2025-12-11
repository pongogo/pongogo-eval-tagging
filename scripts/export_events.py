#!/usr/bin/env python3
"""
Export routing events from Pongogo database for tagging.

Usage:
    python export_events.py --db PATH --output PATH [--exclude-tainted] [--limit N]

Examples:
    # Export all clean events
    python export_events.py \
        --db ../../.observability_db/observability_db-production/routing_log-production.db \
        --output ../data/events_to_tag.jsonl \
        --exclude-tainted

    # Export specific range
    python export_events.py \
        --db ../../.observability_db/observability_db-production/routing_log-production.db \
        --output ../data/events_to_tag.jsonl \
        --min-id 100 --max-id 500
"""

import argparse
import json
import sqlite3
from pathlib import Path


def export_events(
    db_path: str,
    output_path: str,
    exclude_tainted: bool = True,
    min_id: int = None,
    max_id: int = None,
    limit: int = None
) -> int:
    """Export routing events to JSONL format for tagging.
    
    Args:
        db_path: Path to routing_log database
        output_path: Path for output JSONL file
        exclude_tainted: If True, skip events with exclude_reason != NULL
        min_id: Minimum event ID to include
        max_id: Maximum event ID to include
        limit: Maximum number of events to export
        
    Returns:
        Number of events exported
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
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
    limit_clause = f" LIMIT {limit}" if limit else ""
    
    query = f"""
        SELECT 
            id,
            user_message,
            timestamp,
            routed_instructions,
            routing_engine_version
        FROM routing_events
        WHERE {where_clause}
        ORDER BY id
        {limit_clause}
    """
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Write to JSONL
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    count = 0
    with open(output_path, 'w') as f:
        for row in rows:
            # Parse routed_instructions if stored as JSON string
            routed = row['routed_instructions']
            if isinstance(routed, str):
                try:
                    routed = json.loads(routed)
                except json.JSONDecodeError:
                    routed = [routed] if routed else []
            
            event = {
                'event_id': f"evt_{row['id']:06d}",
                'user_message': row['user_message'],
                'timestamp': row['timestamp'],
                'routed_instructions': routed if isinstance(routed, list) else []
            }
            
            f.write(json.dumps(event) + '\n')
            count += 1
    
    conn.close()
    return count


def main():
    parser = argparse.ArgumentParser(description='Export routing events for tagging')
    parser.add_argument('--db', required=True, help='Path to routing_log database')
    parser.add_argument('--output', required=True, help='Output JSONL file path')
    parser.add_argument('--exclude-tainted', action='store_true', 
                        help='Exclude events with exclude_reason set')
    parser.add_argument('--min-id', type=int, help='Minimum event ID')
    parser.add_argument('--max-id', type=int, help='Maximum event ID')
    parser.add_argument('--limit', type=int, help='Maximum events to export')
    
    args = parser.parse_args()
    
    count = export_events(
        db_path=args.db,
        output_path=args.output,
        exclude_tainted=args.exclude_tainted,
        min_id=args.min_id,
        max_id=args.max_id,
        limit=args.limit
    )
    
    print(f"Exported {count} events to {args.output}")


if __name__ == '__main__':
    main()
