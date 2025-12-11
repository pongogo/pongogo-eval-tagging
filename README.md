# Pongogo Eval Tagging

**Purpose**: Create high-quality eval datasets for Pongogo routing evaluation through LLM-assisted tagging.

**Epic #234 Alignment**: This repo directly addresses the three gaps identified in [Epic #234](https://github.com/pongogo/pongogo/issues/234):
1. **Conversation boundaries** - When does a "request" start/end?
2. **Iteration indicators** - Is this a followup/correction?
3. **Outcome quality** - Did the agent succeed?

---

## Two-Tier Tagging Approach

### Tier 1: Conversation Structure (Tag Now)
**Data available**: User messages from routing_events DB

| Field | Description | Enables Metric |
|-------|-------------|----------------|
| `is_new_request` | Conversation boundary | Conversation length |
| `is_followup` | User checking agent work | Iteration rate |
| `is_correction` | User correcting agent | Correction rate |
| `session_id` | Groups related events | Session analysis |
| `request_sequence` | Position in session | Iteration counting |
| `expected_outcome` | What should happen | First-pass success |

### Tier 2: Outcome & Anti-Pattern (Future Data Needed)
**Data NOT currently captured**: Agent responses

| Field | Description | Why It Matters |
|-------|-------------|----------------|
| `outcome_observed` | Did agent succeed? | Measures real impact |
| `anti_pattern_detected` | Did agent make mistake? | Validates instructions |
| `preventive_instruction_was_routed` | Was right instruction surfaced? | Routing vs instruction quality |

**Note**: Tier 2 fields can be tagged as `"not_observable"` until agent_response capture is implemented.

---

## For LLM Taggers (ChatGPT Codex, Claude, etc.)

**Your Task**: Tag routing events with conversation metadata per Epic #234 requirements.

### Quick Start

1. Read `prompts/tagging_instructions.md` for complete guidelines
2. Review `schema/examples.json` for tagged examples (shows both tiers)
3. Load events from `data/events_to_tag.jsonl`
4. Output to `data/tagged_events.jsonl`

### Key Tagging Fields (Tier 1 - Required)

| Field | Type | Question to Ask |
|-------|------|-----------------|
| `is_new_request` | boolean | Is this the START of a new task? |
| `is_followup` | boolean | Is user asking about previous response? |
| `is_correction` | boolean | Is user correcting agent behavior? |
| `iteration_type` | enum | none/clarification/correction/retry/refinement |
| `request_type` | enum | procedural/query/action/meta/unclear |
| `expected_outcome` | string | What should happen if routing succeeds? |

### Why This Matters

Pongogo's routing evaluation currently measures:
- ✅ Did we route the right instructions? (precision/recall)

But we CAN'T measure (Epic #234 gaps):
- ❌ Did routing reduce back-and-forth? (iterations)
- ❌ Did the agent succeed on first try? (first-pass success)
- ❌ How often does the user need to correct the agent? (correction rate)

**Your tagging enables these measurements.**

---

## Repository Structure

```
pongogo-eval-tagging/
├── README.md                    # This file
├── schema/
│   ├── tagging_schema.json      # JSON Schema (Epic #234 aligned)
│   └── examples.json            # Two-tier tagging examples
├── data/
│   ├── events_to_tag.jsonl      # Input: exported from Pongogo DB
│   └── tagged_events.jsonl      # Output: your tagged events
├── scripts/
│   ├── export_events.py         # Pull events from Pongogo DB
│   ├── import_tagged.py         # Push tagged data back
│   └── validate_tags.py         # Validate before submission
└── prompts/
    └── tagging_instructions.md  # Complete tagging guidelines
```

---

## Data Format

### Input (`events_to_tag.jsonl`)

```json
{"event_id": "evt_000001", "user_message": "close issue #270", "timestamp": "2025-12-10T15:30:00", "routed_instructions": ["issue_closure.instructions"], "session_id": "abc123"}
```

### Output (`tagged_events.jsonl`)

```json
{"event_id": "evt_000001", "tags": {"is_new_request": true, "is_followup": false, "is_correction": false, "iteration_type": "none", "request_type": "procedural", "session_id": "session_001", "request_sequence": 1, "expected_outcome": "issue_closed_with_checklist", "expected_first_pass_success": true, "context_sufficient": true, "confidence": "high", "requires_agent_response": false}}
```

---

## Tagging Guidelines Summary

### Conversation Boundaries (`is_new_request`)
- **TRUE**: New topic, >5 min gap, explicit "new task" language
- **FALSE**: Continues existing conversation, references previous context ("now", "also", "next")

### Iteration Indicators
- `is_followup = true`: "did you...?", "what about...?", checking on work
- `is_correction = true`: "no, I meant...", "that's wrong", explicit correction

### Iteration Types
| Type | Example |
|------|---------|
| `none` | First request in session |
| `clarification` | User provides more info |
| `correction` | Agent was wrong |
| `retry` | "try again", "let me rephrase" |
| `refinement` | "actually, make it X instead" |

### Expected Outcome Format
Be specific, use snake_case:
- ✅ `issue_closed_with_checklist_executed`
- ✅ `file_contents_displayed`
- ❌ `success` (too vague)

---

## Validation

```bash
python scripts/validate_tags.py data/tagged_events.jsonl
```

Checks:
- All required fields present
- Enum values valid
- Session sequences monotonic
- Event IDs unique

---

## For Pongogo Developers

### Export Events

```bash
python scripts/export_events.py \
  --db /path/to/routing_log-production.db \
  --output data/events_to_tag.jsonl \
  --exclude-tainted
```

### Import Tagged Data

```bash
python scripts/import_tagged.py \
  --input data/tagged_events.jsonl \
  --db /path/to/routing_log-production.db \
  --source "codex"  # or "claude", "human"
```

---

## Related Issues

- [Epic #234](https://github.com/pongogo/pongogo/issues/234): Eval Methodology Reconception (parent)
- [Task #236](https://github.com/pongogo/pongogo/issues/236): Phase 2 - Collaboration Efficiency Metrics
- [Task #215](https://github.com/pongogo/pongogo/issues/215): External Evaluation Harness

---

## Future Work: Agent Response Capture

To enable Tier 2 tagging (outcome, anti-pattern), Pongogo needs to capture `agent_response` in the routing_events table. This is tracked as a future enhancement.

Once available, taggers can fully assess:
- Did the agent actually succeed?
- Did the agent exhibit any anti-patterns?
- Was the preventive instruction followed?

This enables the "Outcome-Based Evaluation" direction outlined in Epic #234.
