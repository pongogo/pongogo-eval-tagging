#!/usr/bin/env python3
"""
Add tags to events in the eval database.

Usage:
    # Interactive mode (for humans)
    python add_tags.py --db PATH --interactive
    
    # Batch mode (for LLM output)
    python add_tags.py --db PATH --input tags.jsonl --tagger "llm:codex"

Examples:
    # Import tags from Codex tagging session
    python add_tags.py \
        --db data/eval_tags.db \
        --input tagged_by_codex.jsonl \
        --tagger "llm:codex"
"""

import argparse
import sqlite3
import json
from pathlib import Path
from datetime import datetime


def add_tags_from_jsonl(
    db_path: Path,
    input_path: Path,
    tagger_id: str
) -> dict:
    """Import tags from JSONL file.
    
    Args:
        db_path: Path to eval_tags database
        input_path: Path to JSONL file with tags
        tagger_id: Identifier for who/what tagged (e.g., 'llm:codex')
        
    Returns:
        Dict with import statistics
    """
    stats = {
        'total': 0,
        'imported': 0,
        'errors': []
    }
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
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
            
            # Find event in database
            # event_id format: evt_NNNNNN -> source_event_id = NNNNNN
            try:
                source_id = int(event_id.replace('evt_', ''))
            except ValueError:
                stats['errors'].append(f"Line {line_num}: Invalid event_id format: {event_id}")
                continue
            
            cursor.execute(
                "SELECT id FROM events WHERE source_event_id = ?",
                (source_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                stats['errors'].append(f"Line {line_num}: Event not found: {event_id}")
                continue
            
            db_event_id = result[0]
            
            # Get next tag version for this event+tagger
            cursor.execute(
                "SELECT COALESCE(MAX(tag_version), 0) + 1 FROM tags WHERE event_id = ? AND tagger_id = ?",
                (db_event_id, tagger_id)
            )
            next_version = cursor.fetchone()[0]
            
            try:
                cursor.execute("""
                    INSERT INTO tags (
                        event_id,
                        is_new_request,
                        session_id,
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
                        confidence,
                        notes,
                        requires_agent_response,
                        tagger_id,
                        tag_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    db_event_id,
                    tags.get('is_new_request'),
                    tags.get('session_id'),
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
    parser = argparse.ArgumentParser(description='Add tags to eval database')
    parser.add_argument('--db', type=Path, required=True, help='Eval database path')
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
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):\n")
        for error in stats['errors'][:10]:
            print(f"  - {error}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")


if __name__ == '__main__':
    main()
