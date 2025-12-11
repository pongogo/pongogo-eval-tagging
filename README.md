# Pongogo Eval Tagging

**Purpose**: Add collaboration efficiency metadata to Pongogo's existing evaluation dataset through LLM-assisted tagging.

**Architecture**: This repo provides a **schema extension** to the existing `evaluation_results.db` database (see `docs/observability/evaluation_schema.sql` in pongogo repo).

**Epic #234 Alignment**: Addresses the three gaps identified in [Epic #234](https://github.com/pongogo/pongogo/issues/234):
1. **Conversation boundaries** - When does a "request" start/end?
2. **Iteration indicators** - Is this a followup/correction?
3. **Outcome quality** - Did the agent succeed?

---

## Architecture: Schema Extension

This repo **extends** the existing `evaluation_dataset` table, not replaces it.

```
evaluation_results.db (existing)
├── evaluation_dataset          # Core events (event_id, user_message, actual_routing, expected_routing)
├── tfidf_results              # TF-IDF benchmark metrics
├── sentence_transformers_results  # Embedding benchmark metrics
└── collaboration_tags         # NEW: Epic #234 extension (this repo)
    └── FOREIGN KEY → evaluation_dataset.event_id
```

**Why extension?**
- Keeps existing eval queries working
- No data duplication
- Combined analysis via JOINs (e.g., routing accuracy × iteration rate)

---

## Workflow

### 1. Apply Schema Extension

```bash
# Apply collaboration_tags table to existing eval DB
python scripts/apply_schema.py \
  --db ~/.observability_db/observability_db-learning/evaluation_results.db
```

### 2. Export Events for Tagging

```bash
# Export all events (or --untagged-only for incremental)
python scripts/export_for_tagging.py \
  --db ~/.observability_db/observability_db-learning/evaluation_results.db \
  --output data/events_for_codex.jsonl
```

### 3. Tag with LLM (Codex, Claude, etc.)

Give the LLM:
- `data/events_for_codex.jsonl` (input)
- `prompts/tagging_instructions.md` (instructions)
- `schema/examples.json` (few-shot examples)

LLM outputs: `data/tagged_events.jsonl`

### 4. Import Tags

```bash
python scripts/add_tags.py \
  --db ~/.observability_db/observability_db-learning/evaluation_results.db \
  --input data/tagged_events.jsonl \
  --tagger "llm:codex"
```

### 5. Query Metrics

```bash
python scripts/query_metrics.py \
  --db ~/.observability_db/observability_db-learning/evaluation_results.db
```

---

## Two-Tier Tagging Approach

### Tier 1: Conversation Structure (Tag Now)
**Data available**: User messages from evaluation_dataset

| Field | Description | Enables Metric |
|-------|-------------|----------------|
| `is_new_request` | Conversation boundary | Conversation length |
| `is_followup` | User checking agent work | Iteration rate |
| `is_correction` | User correcting agent | Correction rate |
| `tagged_session_id` | Groups related events | Session analysis |
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

**Your Task**: Tag events with conversation metadata per Epic #234 requirements.

### Quick Start

1. Read `prompts/tagging_instructions.md` for complete guidelines
2. Review `schema/examples.json` for tagged examples
3. Load events from the JSONL file you receive
4. Output tagged events as JSONL

### Key Tagging Fields

| Field | Type | Question to Ask |
|-------|------|-----------------|
| `is_new_request` | boolean | Is this the START of a new task? |
| `is_followup` | boolean | Is user asking about previous response? |
| `is_correction` | boolean | Is user correcting agent behavior? |
| `iteration_type` | enum | none/clarification/correction/retry/refinement |
| `request_type` | enum | procedural/query/action/meta/unclear |
| `expected_outcome` | string | What should happen if routing succeeds? |

### Why This Matters

Pongogo currently measures:
- ✅ Did we route the right instructions? (precision/recall/F1)

Your tagging enables measuring:
- ❌ Did routing reduce back-and-forth? (iteration rate)
- ❌ Did the agent succeed on first try? (first-pass success)
- ❌ How often does the user need to correct the agent? (correction rate)

---

## Repository Structure

```
pongogo-eval-tagging/
├── README.md                    # This file
├── schema/
│   ├── eval_db_schema.sql       # SQL schema extension (collaboration_tags table)
│   ├── tagging_schema.json      # JSON Schema for validation
│   └── examples.json            # Tagged examples for few-shot learning
├── data/
│   └── .gitkeep                 # Data files (gitignored)
├── scripts/
│   ├── apply_schema.py          # Apply schema to existing eval DB
│   ├── export_for_tagging.py    # Export events for LLM tagging
│   ├── add_tags.py              # Import LLM-generated tags
│   ├── query_metrics.py         # Query collaboration metrics
│   └── validate_tags.py         # Validate tag format
└── prompts/
    └── tagging_instructions.md  # Complete tagging guidelines
```

---

## Output Format

```json
{"event_id": "evt_000001", "tags": {"is_new_request": true, "is_followup": false, "is_correction": false, "iteration_type": "none", "request_type": "procedural", "session_id": "session_001", "request_sequence": 1, "expected_outcome": "issue_closed_with_checklist", "expected_first_pass_success": true, "context_sufficient": true, "confidence": "high"}}
```

---

## Tagging Guidelines Summary

### Conversation Boundaries (`is_new_request`)
- **TRUE**: New topic, >5 min gap, explicit "new task" language
- **FALSE**: Continues existing conversation ("now", "also", "next")

### Iteration Types
| Type | Example |
|------|---------|
| `none` | First request in session |
| `clarification` | User provides more info |
| `correction` | Agent was wrong ("no, I meant...") |
| `retry` | "try again", "let me rephrase" |
| `refinement` | "actually, make it X instead" |

### Expected Outcome Format
Be specific, use snake_case:
- ✅ `issue_closed_with_checklist_executed`
- ❌ `success` (too vague)

---

## Metrics Enabled

After tagging, `query_metrics.py` shows:

```
=== ITERATION RATE BY SESSION ===
  Session     | Events | Followups | Corrections | Iter Rate
  session_001 | 5      | 2         | 1           | 2.50

=== ANTI-PATTERN ANALYSIS ===
  Anti-Pattern           | Preventive Instr              | Count | Routed | % Instr Issue
  skipped_checklist      | issue_closure.instructions    | 3     | 3      | 100.0
  time_estimate_in_output| time_free_pm.instructions     | 2     | 0      | 0.0
```

**Interpretation**:
- `% Instr Issue = 100%` → Instruction was routed but agent ignored it
- `% Instr Issue = 0%` → Routing failure (instruction should have been surfaced)

---

## Related Issues

- [Epic #234](https://github.com/pongogo/pongogo/issues/234): Eval Methodology Reconception
- [Task #236](https://github.com/pongogo/pongogo/issues/236): Phase 2 - Collaboration Efficiency Metrics
- [Task #215](https://github.com/pongogo/pongogo/issues/215): External Evaluation Harness

---

## Future: Agent Response Capture

To enable Tier 2 tagging (outcome, anti-pattern detection), Pongogo will need to capture `agent_response` data. This enables:
- Did the agent actually succeed?
- Did the agent exhibit anti-patterns?
- Was the preventive instruction followed?

This is the "Outcome-Based Evaluation" direction from Epic #234.
