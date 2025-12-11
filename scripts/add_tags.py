#!/usr/bin/env python3
"""
Add collaboration tags to events in evaluation_results.db.

Usage:
    python add_tags.py --db PATH --input tags.jsonl --tagger "llm:codex"

Examples:
    # Import tags from Codex tagging session
    python add_tags.py \
        --db ~/.observability_db/observability_db-learning/evaluation_results.db \
        --input tagged_by_codex.jsonl \
        --tagger "llm:codex"
"""

import argparse
import sqlite3
import json
from pathlib import Path


def add_tags_from_jsonl(
    db_path: Path,
    input_path: Path,
    tagger_id: str
) -> dict:
    """Import collaboration tags from JSONL file.
    
    Args:
        db_path: Path to evaluation_results.db
        input_path: Path to JSONL file with tags
        tagger_id: Identifier for who/what tagged (e.g., 'llm:codex')
        
    Returns:
        Dict with import statistics
    """
    stats = {
        'total': 0,
        'imported': 0,
        'event_not_found': 0,
        'errors': []
    }
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verify collaboration_tags table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collaboration_tags'")
    if not cursor.fetchone():
        stats['errors'].append(
            "collaboration_tags table not found. Run: python scripts/apply_schema.py --db PATH"
        )
        conn.close()
        return stats
    
    with open(input_path) as f:
        for line_num, line in enumerate(f, 1):
            stats['total'] += 1
            
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                stats['errors'].append(f"Line {line_num}: JSON parse error - {e}")
                continue
            
            event_id = data.get('event_id', '')
            tags = data.get('tags', {})
            
            # Verify event exists in evaluation_dataset
            cursor.execute(
                "SELECT event_id FROM evaluation_dataset WHERE event_id = ?",
                (event_id,)
            )
            if not cursor.fetchone():
                stats['event_not_found'] += 1
                continue
            
            # Get next tag version for this event+tagger
            cursor.execute(
                "SELECT COALESCE(MAX(tag_version), 0) + 1 FROM collaboration_tags WHERE event_id = ? AND tagger_id = ?",
                (event_id, tagger_id)
            )
            next_version = cursor.fetchone()[0]
            
            try:
                cursor.execute("""
                    INSERT INTO collaboration_tags (
                        event_id,
                        is_new_request,
                        tagged_session_id,
                        request_sequence,
                        is_followup,
                        is_correction,
                        iteration_type,
                        request_type,
                        expected_outcome,
                        expected_first_pass_success,
                        outcome_observed,
                        outcome_notes,
                        anti_pattern_detected,
                        anti_pattern_type,
                        preventive_instruction,
                        preventive_instruction_was_routed,
                        context_sufficient,
                        missing_context,
                        agent_response,
                        agent_response_source,
                        confidence,
                        notes,
                        requires_agent_response,
                        tagger_id,
                        tag_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    tags.get('is_new_request'),
                    tags.get('session_id'),  # Maps to tagged_session_id
                    tags.get('request_sequence'),
                    tags.get('is_followup'),
                    tags.get('is_correction'),
                    tags.get('iteration_type'),
                    tags.get('request_type'),
                    tags.get('expected_outcome'),
                    tags.get('expected_first_pass_success'),
                    tags.get('outcome_observed'),
                    tags.get('outcome_notes'),
                    tags.get('anti_pattern_detected'),
                    tags.get('anti_pattern_type'),
                    tags.get('preventive_instruction'),
                    tags.get('preventive_instruction_was_routed'),
                    tags.get('context_sufficient'),
                    tags.get('missing_context'),
                    tags.get('agent_response'),
                    tags.get('agent_response_source'),
                    tags.get('confidence'),
                    tags.get('notes'),
                    tags.get('requires_agent_response'),
                    tagger_id,
                    next_version
                ))
                stats['imported'] += 1
                
            except Exception as e:
                stats['errors'].append(f"Line {line_num}: Insert error - {e}")
    
    conn.commit()
    conn.close()
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Add collaboration tags to eval database')
    parser.add_argument('--db', type=Path, required=True, help='Path to evaluation_results.db')
    parser.add_argument('--input', type=Path, required=True, help='JSONL file with tags')
    parser.add_argument('--tagger', type=str, required=True,
                        help='Tagger identifier (e.g., "llm:codex", "human:max")')
    
    args = parser.parse_args()
    
    if not args.db.exists():
        print(f"Error: Database not found: {args.db}")
        return 1
    
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return 1
    
    stats = add_tags_from_jsonl(args.db, args.input, args.tagger)
    
    print(f"\nTag Import Statistics:")
    print(f"  Total lines: {stats['total']}")
    print(f"  Imported: {stats['imported']}")
    print(f"  Event not found: {stats['event_not_found']}")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):\n")
        for error in stats['errors'][:10]:
            print(f"  - {error}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")


if __name__ == '__main__':
    main()
