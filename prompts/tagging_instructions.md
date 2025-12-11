# Pongogo Eval Tagging Instructions

**For**: LLM Taggers (ChatGPT Codex, Claude, etc.)
**Task**: Tag routing events with conversation metadata
**Output**: JSONL file with tagged events

---

## Your Mission

You're helping evaluate Pongogo, a knowledge routing system for AI agents. Each event in your input is a user message that was routed to relevant instructions.

**Your job**: Add metadata about conversation structure and expected outcomes.

---

## Input Format

You'll receive a JSONL file (`data/events_to_tag.jsonl`) where each line is:

```json
{"event_id": "evt_123", "user_message": "close issue #270", "timestamp": "2025-12-10T15:30:00", "routed_instructions": ["issue_closure.instructions"]}
```

---

## Output Format

Produce a JSONL file (`data/tagged_events.jsonl`) where each line is:

```json
{"event_id": "evt_123", "tags": {"is_new_request": true, "is_followup": false, "is_correction": false, "request_type": "procedural", "expected_outcome": "issue_closed", "session_id": "session_001", "request_sequence": 1, "confidence": "high"}}
```

---

## Tagging Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_new_request` | boolean | Is this the START of a new task? |
| `is_followup` | boolean | Is user asking about previous response? |
| `is_correction` | boolean | Is user correcting agent behavior? |
| `request_type` | enum | Type of request (see below) |
| `expected_outcome` | string | What should happen if successful? |
| `session_id` | string | Groups related events (format: `session_NNN`) |
| `request_sequence` | integer | Position within session (1, 2, 3...) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `confidence` | enum | Your confidence: `high`, `medium`, `low` |
| `notes` | string | Explanation for edge cases |

---

## Request Types

| Type | Description | Examples |
|------|-------------|----------|
| `procedural` | Multi-step process | "close issue #270", "create a new Epic" |
| `query` | Information request | "what's the routing version?", "explain this code" |
| `action` | Single discrete action | "commit these changes", "run tests" |
| `meta` | About the system itself | "how does pongogo work?", "what can you do?" |
| `unclear` | Ambiguous intent | "can you help?", "this" |

---

## Decision Rules

### is_new_request = true when:
- User starts a completely new topic
- Significant time gap from previous message (>5 minutes)
- User explicitly says "new task", "let's work on X"
- No reference to previous context

### is_new_request = false when:
- User continues existing conversation
- References previous context ("now", "also", "next")
- Short time gap (<2 minutes typically)

### is_followup = true when:
- User asks about previous response: "did you...?", "what about...?"
- Checking on work: "is that done?", "did it work?"
- Seeking confirmation: "so you're saying...?"

### is_correction = true when:
- User explicitly corrects: "no, I meant...", "that's wrong"
- Negative feedback: "not like that", "try again"
- Clarification after misunderstanding: "I said X not Y"

---

## Session Grouping

Group events into sessions based on:

1. **Topic coherence** - Same general task/goal
2. **Time proximity** - Events close in time (within ~10 minutes)
3. **Explicit boundaries** - User starting fresh topic

**Rules**:
- New session = new `session_id` (increment: `session_001`, `session_002`, ...)
- `request_sequence` resets to 1 for each new session
- Sequences must be monotonically increasing within session

---

## Expected Outcome Guidelines

Be specific but concise. Use snake_case.

**Good examples**:
- `issue_closed_with_checklist_executed`
- `file_contents_displayed`
- `commit_created_with_message`
- `routing_version_reported`

**Bad examples**:
- `success` (too vague)
- `the agent should close the issue` (too verbose)
- `Done` (not descriptive)

---

## Edge Cases

### Mixed signals
If a message has multiple characteristics, prioritize:
1. `is_correction` (strongest signal of failure)
2. `is_followup` (iteration indicator)
3. `is_new_request` (conversation boundary)

### Insufficient context
- Use `confidence: "low"` when context is missing
- Add `notes` explaining uncertainty
- Still make a best-effort tag

### Ambiguous timestamps
- If timestamps are missing or unclear, rely on message content
- Sequential event_ids suggest temporal order

---

## Validation Checklist

Before submitting, verify:

- [ ] Every input event has a corresponding output tag
- [ ] All required fields present in every output
- [ ] `request_type` uses only allowed enum values
- [ ] `session_id` format is `session_NNN`
- [ ] `request_sequence` starts at 1 and increments within session
- [ ] No duplicate `event_id` values
- [ ] Low-confidence tags have explanatory `notes`

---

## Example Workflow

```python
import json

# Load input
with open('data/events_to_tag.jsonl') as f:
    events = [json.loads(line) for line in f]

# Tag each event
tagged = []
current_session = 1
sequence = 1

for event in events:
    # Analyze message
    msg = event['user_message'].lower()
    
    # Determine if new request (simplified example)
    is_new = not any(word in msg for word in ['now', 'also', 'did you', 'what about'])
    
    if is_new:
        current_session += 1
        sequence = 1
    
    tagged.append({
        'event_id': event['event_id'],
        'tags': {
            'is_new_request': is_new,
            'is_followup': 'did you' in msg or 'what about' in msg,
            'is_correction': 'no,' in msg or "that's wrong" in msg,
            'request_type': 'procedural',  # Determine properly
            'expected_outcome': 'task_completed',  # Be specific
            'session_id': f'session_{current_session:03d}',
            'request_sequence': sequence,
            'confidence': 'high'
        }
    })
    sequence += 1

# Write output
with open('data/tagged_events.jsonl', 'w') as f:
    for item in tagged:
        f.write(json.dumps(item) + '\n')
```

---

## Questions?

If you encounter scenarios not covered here:
1. Make a best-effort tag with `confidence: "low"`
2. Add detailed `notes` explaining the edge case
3. These edge cases help improve the schema
