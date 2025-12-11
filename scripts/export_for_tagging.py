#!/usr/bin/env python3
"""
Export events from evaluation_results.db to JSONL for LLM tagging.

Usage:
    python export_for_tagging.py --db PATH --output PATH [--untagged-only] [--limit N]

Examples:
    # Export all events for tagging
    python export_for_tagging.py \
        --db ~/.observability_db/observability_db-learning/evaluation_results.db \
        --output data/events_for_codex.jsonl

    # Export only events without collaboration tags
    python export_for_tagging.py \
        --db ~/.observability_db/observability_db-learning/evaluation_results.db \
        --output data/untagged_events.jsonl \
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
    """Export events from evaluation_dataset to JSONL for tagging.
    
    Args:
        db_path: Path to evaluation_results.db
        output_path: Output JSONL path
        untagged_only: If True, only export events without collaboration_tags
        limit: Maximum number to export
        
    Returns:
        Number of events exported
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if collaboration_tags table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collaboration_tags'")
    has_collab_tags = cursor.fetchone() is not None
    
    if untagged_only and has_collab_tags:
        query = """
            SELECT e.*
            FROM evaluation_dataset e
            LEFT JOIN collaboration_tags c ON e.event_id = c.event_id
            WHERE c.id IS NULL
            ORDER BY e.timestamp
        """
    else:
        query = "SELECT * FROM evaluation_dataset ORDER BY timestamp"
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    count = 0
    with open(output_path, 'w') as f:
        for row in rows:
            # Parse actual_routing JSON to get instruction names
            actual_routing = []
            try:
                routing_data = json.loads(row['actual_routing'] or '[]')
                if isinstance(routing_data, list):
                    for item in routing_data:
                        if isinstance(item, dict) and 'file' in item:
                            actual_routing.append(item['file'])
                        elif isinstance(item, str):
                            actual_routing.append(item)
            except json.JSONDecodeError:
                pass
            
            event = {
                'event_id': row['event_id'],
                'user_message': row['user_message'],
                'timestamp': row['timestamp'],
                'session_id': row['session_id'],
                'task_phase': row['task_phase'],
                'work_context': row['work_context'],
                'routed_instructions': actual_routing,
                'ground_truth_label': row['ground_truth_label'],
                'evidence_type': row['evidence_type']
            }
            f.write(json.dumps(event) + '\n')
            count += 1
    
    conn.close()
    return count


def main():
    parser = argparse.ArgumentParser(description='Export events for LLM tagging')
    parser.add_argument('--db', type=Path, required=True, help='Path to evaluation_results.db')
    parser.add_argument('--output', type=Path, required=True, help='Output JSONL path')
    parser.add_argument('--untagged-only', action='store_true',
                        help='Only export events without collaboration tags')
    parser.add_argument('--limit', type=int, help='Maximum events to export')
    
    args = parser.parse_args()
    
    if not args.db.exists():
        print(f"Error: Database not found: {args.db}")
        return 1
    
    count = export_events(args.db, args.output, args.untagged_only, args.limit)
    print(f"Exported {count} events to {args.output}")


if __name__ == '__main__':
    main()
