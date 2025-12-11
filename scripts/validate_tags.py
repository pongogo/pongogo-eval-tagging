#!/usr/bin/env python3
"""
Validate tagged events against schema.

Usage:
    python validate_tags.py PATH_TO_JSONL

Examples:
    python validate_tags.py ../data/tagged_events.jsonl
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict


REQUIRED_FIELDS = [
    'is_new_request',
    'is_followup', 
    'is_correction',
    'request_type',
    'expected_outcome',
    'session_id',
    'request_sequence'
]

VALID_REQUEST_TYPES = ['procedural', 'query', 'action', 'meta', 'unclear']
VALID_CONFIDENCE = ['high', 'medium', 'low']


def validate_tags(input_path: str) -> dict:
    """Validate tagged events file.
    
    Args:
        input_path: Path to tagged_events.jsonl
        
    Returns:
        Dict with validation results
    """
    results = {
        'total': 0,
        'valid': 0,
        'errors': [],
        'warnings': [],
        'sessions': defaultdict(list)  # session_id -> [(seq, event_id)]
    }
    
    seen_event_ids = set()
    
    with open(input_path) as f:
        for line_num, line in enumerate(f, 1):
            results['total'] += 1
            
            # Parse JSON
            try:
                event = json.loads(line)
            except json.JSONDecodeError as e:
                results['errors'].append(f"Line {line_num}: Invalid JSON - {e}")
                continue
            
            # Check required top-level fields
            if 'event_id' not in event:
                results['errors'].append(f"Line {line_num}: Missing 'event_id'")
                continue
            
            event_id = event['event_id']
            
            # Check for duplicates
            if event_id in seen_event_ids:
                results['errors'].append(f"Line {line_num}: Duplicate event_id '{event_id}'")
            seen_event_ids.add(event_id)
            
            if 'tags' not in event:
                results['errors'].append(f"Line {line_num} ({event_id}): Missing 'tags'")
                continue
            
            tags = event['tags']
            line_valid = True
            
            # Check required tag fields
            for field in REQUIRED_FIELDS:
                if field not in tags:
                    results['errors'].append(
                        f"Line {line_num} ({event_id}): Missing required field '{field}'"
                    )
                    line_valid = False
            
            if not line_valid:
                continue
            
            # Validate field types and values
            for bool_field in ['is_new_request', 'is_followup', 'is_correction']:
                if not isinstance(tags[bool_field], bool):
                    results['errors'].append(
                        f"Line {line_num} ({event_id}): '{bool_field}' must be boolean, got {type(tags[bool_field]).__name__}"
                    )
                    line_valid = False
            
            if tags['request_type'] not in VALID_REQUEST_TYPES:
                results['errors'].append(
                    f"Line {line_num} ({event_id}): Invalid request_type '{tags['request_type']}'. "
                    f"Must be one of: {VALID_REQUEST_TYPES}"
                )
                line_valid = False
            
            if not isinstance(tags['request_sequence'], int) or tags['request_sequence'] < 1:
                results['errors'].append(
                    f"Line {line_num} ({event_id}): request_sequence must be positive integer"
                )
                line_valid = False
            
            # Validate session_id format
            if not tags['session_id'].startswith('session_'):
                results['warnings'].append(
                    f"Line {line_num} ({event_id}): session_id '{tags['session_id']}' "
                    "doesn't follow 'session_NNN' format"
                )
            
            # Validate optional confidence field
            if 'confidence' in tags and tags['confidence'] not in VALID_CONFIDENCE:
                results['warnings'].append(
                    f"Line {line_num} ({event_id}): Invalid confidence '{tags['confidence']}'. "
                    f"Should be one of: {VALID_CONFIDENCE}"
                )
            
            # Track session sequences for ordering validation
            results['sessions'][tags['session_id']].append(
                (tags['request_sequence'], event_id)
            )
            
            if line_valid:
                results['valid'] += 1
    
    # Validate session sequences are monotonic
    for session_id, events in results['sessions'].items():
        sorted_events = sorted(events, key=lambda x: x[0])
        prev_seq = 0
        for seq, event_id in sorted_events:
            if seq != prev_seq + 1:
                results['warnings'].append(
                    f"Session '{session_id}': Non-sequential request_sequence. "
                    f"Expected {prev_seq + 1}, got {seq} for {event_id}"
                )
            prev_seq = seq
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Validate tagged events')
    parser.add_argument('input', help='Path to tagged_events.jsonl')
    
    args = parser.parse_args()
    
    if not Path(args.input).exists():
        print(f"Error: File not found: {args.input}")
        sys.exit(1)
    
    results = validate_tags(args.input)
    
    print(f"\nValidation Results for {args.input}")
    print("=" * 50)
    print(f"Total events: {results['total']}")
    print(f"Valid events: {results['valid']}")
    print(f"Sessions found: {len(results['sessions'])}")
    
    if results['errors']:
        print(f"\n❌ ERRORS ({len(results['errors'])}):\n")
        for error in results['errors'][:20]:
            print(f"  {error}")
        if len(results['errors']) > 20:
            print(f"  ... and {len(results['errors']) - 20} more errors")
    
    if results['warnings']:
        print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):\n")
        for warning in results['warnings'][:10]:
            print(f"  {warning}")
        if len(results['warnings']) > 10:
            print(f"  ... and {len(results['warnings']) - 10} more warnings")
    
    if not results['errors'] and not results['warnings']:
        print("\n✅ All validations passed!")
        sys.exit(0)
    elif results['errors']:
        print("\n❌ Validation failed with errors")
        sys.exit(1)
    else:
        print("\n⚠️  Validation passed with warnings")
        sys.exit(0)


if __name__ == '__main__':
    main()
