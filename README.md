# Pongogo Eval Tagging

**Purpose**: Create high-quality eval datasets for Pongogo routing evaluation through LLM-assisted tagging.

## For LLM Taggers (ChatGPT Codex, Claude, etc.)

**Your Task**: Tag routing events with conversation boundaries, iteration indicators, and outcome expectations.

### Quick Start

1. Read `prompts/tagging_instructions.md` for complete tagging guidelines
2. Review `schema/examples.json` for tagged examples (few-shot learning)
3. Load events from `data/events_to_tag.jsonl`
4. Output tagged events to `data/tagged_events.jsonl`

### What You're Tagging

Each event in `data/events_to_tag.jsonl` is a user message that was routed to Pongogo knowledge instructions. You're adding metadata about:

| Field | Type | Description |
|-------|------|-------------|
| `is_new_request` | boolean | Is this the START of a new task/conversation? |
| `is_followup` | boolean | Is this asking about a previous response? ("did you do X?") |
| `is_correction` | boolean | Is the user correcting agent behavior? ("no, I meant...") |
| `request_type` | enum | `procedural` (do steps), `query` (answer question), `action` (single action) |
| `expected_outcome` | string | What should happen if routing succeeds? |

### Why This Matters

Pongogo's routing evaluation currently measures:
- ✅ Did we route the right instructions? (precision/recall)

But we CAN'T measure:
- ❌ Did routing reduce back-and-forth? (iterations)
- ❌ Did the agent succeed on first try? (first-pass success)
- ❌ How often does the user need to correct the agent? (correction rate)

Your tagging enables these measurements.

---

## Repository Structure

```
pongogo-eval-tagging/
├── README.md                    # This file
├── schema/
│   ├── tagging_schema.json      # JSON Schema for validation
│   └── examples.json            # Tagged examples for learning
├── data/
│   ├── events_to_tag.jsonl      # Input: events to tag
│   └── tagged_events.jsonl      # Output: your tagged events
├── scripts/
│   ├── export_events.py         # Pull events from Pongogo DB
│   └── import_tagged.py         # Push tagged data back
└── prompts/
    └── tagging_instructions.md  # Complete tagging guidelines
```

---

## Context: What is Pongogo?

Pongogo is a knowledge routing system that surfaces relevant instructions to AI agents based on user requests.

**Example**:
- User says: "close issue #270"
- Pongogo routes: `issue_closure.instructions.md` (relevance: 464)
- Agent receives: Step-by-step issue closure checklist

**The Goal**: Measure whether good routing leads to better collaboration (fewer iterations, higher first-pass success).

---

## Data Format

### Input (`events_to_tag.jsonl`)

```json
{"event_id": "evt_001", "user_message": "close issue #270", "timestamp": "2025-12-10T15:30:00", "routed_instructions": ["issue_closure.instructions"]}
{"event_id": "evt_002", "user_message": "did you add the work log entry?", "timestamp": "2025-12-10T15:32:00", "routed_instructions": ["work_logging.instructions"]}
```

### Output (`tagged_events.jsonl`)

```json
{"event_id": "evt_001", "tags": {"is_new_request": true, "is_followup": false, "is_correction": false, "request_type": "procedural", "expected_outcome": "issue_closed_with_checklist", "session_id": "session_001", "request_sequence": 1}}
{"event_id": "evt_002", "tags": {"is_new_request": false, "is_followup": true, "is_correction": false, "request_type": "query", "expected_outcome": "confirmation_of_work_log", "session_id": "session_001", "request_sequence": 2}}
```

---

## Validation

Run validation before submitting:

```bash
python scripts/validate_tags.py data/tagged_events.jsonl
```

This checks:
- All required fields present
- Enum values valid
- Session IDs consistent
- Request sequences monotonic within sessions

---

## For Pongogo Developers

### Export Events

```bash
# From pongogo repo root
python pongogo-eval-tagging/scripts/export_events.py \
  --db .observability_db/observability_db-production/routing_log-production.db \
  --output pongogo-eval-tagging/data/events_to_tag.jsonl \
  --exclude-tainted  # Skip events with exclude_reason != NULL
```

### Import Tagged Data

```bash
python pongogo-eval-tagging/scripts/import_tagged.py \
  --input pongogo-eval-tagging/data/tagged_events.jsonl \
  --db .observability_db/observability_db-production/routing_log-production.db
```

---

## Related Issues

- [Epic #234](https://github.com/pongogo/pongogo/issues/234): Eval Methodology Reconception
- [Task #236](https://github.com/pongogo/pongogo/issues/236): Phase 2 - Collaboration Efficiency Metrics
- [Task #215](https://github.com/pongogo/pongogo/issues/215): External Evaluation Harness
