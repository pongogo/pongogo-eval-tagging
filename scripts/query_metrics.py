#!/usr/bin/env python3
"""
Query Epic #234 collaboration efficiency metrics from evaluation_results.db.

Usage:
    python query_metrics.py --db PATH [--metric NAME]

Examples:
    # Show all metrics
    python query_metrics.py --db ~/.observability_db/observability_db-learning/evaluation_results.db

    # Show specific metric
    python query_metrics.py --db PATH --metric iteration_rate
    python query_metrics.py --db PATH --metric anti_patterns
    python query_metrics.py --db PATH --metric request_types
"""

import argparse
import sqlite3
from pathlib import Path


def print_table(rows: list, headers: list):
    """Print rows as formatted table."""
    if not rows:
        print("  (no data)")
        return
    
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val) if val is not None else 'NULL'))
    
    # Print header
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(f"  {header_line}")
    print(f"  {'-' * len(header_line)}")
    
    # Print rows
    for row in rows:
        row_line = " | ".join(
            str(val if val is not None else 'NULL').ljust(widths[i]) 
            for i, val in enumerate(row)
        )
        print(f"  {row_line}")


def query_metrics(db_path: Path, metric: str = None):
    """Query and display collaboration efficiency metrics."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if collaboration_tags exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collaboration_tags'")
    if not cursor.fetchone():
        print("Error: collaboration_tags table not found.")
        print("Run: python scripts/apply_schema.py --db PATH")
        return
    
    # Overall stats
    if metric is None or metric == 'summary':
        print("\n=== SUMMARY ===")
        cursor.execute("SELECT COUNT(*) FROM evaluation_dataset")
        total_events = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT event_id) FROM collaboration_tags")
        tagged_events = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT tagger_id) FROM collaboration_tags")
        tagger_count = cursor.fetchone()[0]
        
        print(f"  Total events in evaluation_dataset: {total_events}")
        print(f"  Events with collaboration tags: {tagged_events} ({100*tagged_events/total_events:.1f}%)")
        print(f"  Unique taggers: {tagger_count}")
    
    # Session statistics (iteration rate)
    if metric is None or metric == 'iteration_rate':
        print("\n=== ITERATION RATE BY SESSION ===")
        cursor.execute("""
            SELECT 
                tagged_session_id,
                COUNT(*) as events,
                SUM(CASE WHEN is_followup THEN 1 ELSE 0 END) as followups,
                SUM(CASE WHEN is_correction THEN 1 ELSE 0 END) as corrections,
                ROUND(CAST(COUNT(*) AS FLOAT) / 
                    NULLIF(SUM(CASE WHEN is_new_request THEN 1 ELSE 0 END), 0), 2) as iteration_rate
            FROM collaboration_tags
            GROUP BY tagged_session_id
            ORDER BY iteration_rate DESC
            LIMIT 10
        """)
        print_table(
            cursor.fetchall(),
            ['Session', 'Events', 'Followups', 'Corrections', 'Iter Rate']
        )
    
    # Anti-pattern analysis
    if metric is None or metric == 'anti_patterns':
        print("\n=== ANTI-PATTERN ANALYSIS ===")
        cursor.execute("""
            SELECT 
                anti_pattern_type,
                preventive_instruction,
                COUNT(*) as count,
                SUM(CASE WHEN preventive_instruction_was_routed THEN 1 ELSE 0 END) as routed,
                ROUND(100.0 * SUM(CASE WHEN preventive_instruction_was_routed THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_instr_issue
            FROM collaboration_tags
            WHERE anti_pattern_detected = 1
            GROUP BY anti_pattern_type, preventive_instruction
            ORDER BY count DESC
        """)
        rows = cursor.fetchall()
        if rows:
            print_table(rows, ['Anti-Pattern', 'Preventive Instr', 'Count', 'Routed', '% Instr Issue'])
            print("\n  Legend: pct_instr_issue = cases where instruction was routed but anti-pattern still occurred")
        else:
            print("  (no anti-patterns tagged yet)")
    
    # Request type breakdown
    if metric is None or metric == 'request_types':
        print("\n=== REQUEST TYPE BREAKDOWN ===")
        cursor.execute("""
            SELECT 
                request_type,
                COUNT(*) as count,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM collaboration_tags), 1) as pct,
                AVG(CASE WHEN outcome_observed = 'success' THEN 1.0 ELSE 0.0 END) as success_rate
            FROM collaboration_tags
            GROUP BY request_type
            ORDER BY count DESC
        """)
        print_table(
            cursor.fetchall(),
            ['Request Type', 'Count', '% of Total', 'Success Rate']
        )
    
    # Iteration type breakdown
    if metric is None or metric == 'iteration_types':
        print("\n=== ITERATION TYPE BREAKDOWN ===")
        cursor.execute("""
            SELECT 
                iteration_type,
                COUNT(*) as count,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM collaboration_tags), 1) as pct
            FROM collaboration_tags
            GROUP BY iteration_type
            ORDER BY count DESC
        """)
        print_table(
            cursor.fetchall(),
            ['Iteration Type', 'Count', '% of Total']
        )
    
    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Query collaboration efficiency metrics')
    parser.add_argument('--db', type=Path, required=True, help='Path to evaluation_results.db')
    parser.add_argument('--metric', type=str, choices=[
        'summary', 'iteration_rate', 'anti_patterns', 'request_types', 'iteration_types'
    ], help='Specific metric to query')
    
    args = parser.parse_args()
    
    if not args.db.exists():
        print(f"Error: Database not found: {args.db}")
        return 1
    
    query_metrics(args.db, args.metric)


if __name__ == '__main__':
    main()
