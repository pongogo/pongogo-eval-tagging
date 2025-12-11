-- Pongogo Eval Tagging Database Schema
-- Aligned with Epic #234: Eval Methodology Reconception
--
-- This schema captures:
-- 1. Conversation boundaries (Epic #234 Gap #1)
-- 2. Iteration indicators (Epic #234 Phase 2)
-- 3. Outcome quality (Epic #234 Gap #2)
-- 4. Anti-pattern detection (Epic #234 Future Direction)

-- ============================================================
-- CORE TABLES
-- ============================================================

-- Events table: Core routing events imported from production
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    
    -- Source linkage
    source_event_id INTEGER NOT NULL,          -- Links to routing_events.id in production DB
    source_db_path TEXT,                        -- Path to source DB for traceability
    
    -- Event data (copied from routing_events)
    user_message TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    db_session_id TEXT,                         -- Original session_id from routing_events
    routed_instructions TEXT,                   -- JSON array of instruction names
    instruction_count INTEGER,
    
    -- Agent response (when available - Epic #234 Future Direction)
    agent_response TEXT,                        -- Full agent response (for outcome/anti-pattern tagging)
    agent_response_source TEXT,                 -- Where response came from: 'logs', 'manual', 'replay'
    
    -- Metadata
    imported_at TEXT DEFAULT (datetime('now')),
    import_batch TEXT,                          -- Batch identifier for bulk imports
    
    UNIQUE(source_event_id, source_db_path)
);

-- Tags table: Human/LLM annotations per Epic #234 requirements
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    
    -- ============================================================
    -- CONVERSATION BOUNDARIES (Epic #234 Gap #1)
    -- ============================================================
    is_new_request BOOLEAN,                     -- START of new task/conversation?
    session_id TEXT,                            -- Tagging session (may differ from db_session_id)
    request_sequence INTEGER,                   -- Position within session (1, 2, 3...)
    
    -- ============================================================
    -- ITERATION INDICATORS (Epic #234 Phase 2)
    -- ============================================================
    is_followup BOOLEAN,                        -- User checking previous work? ("did you...?")
    is_correction BOOLEAN,                      -- User correcting agent? ("no, I meant...")
    iteration_type TEXT CHECK(iteration_type IN (
        'none',           -- First attempt
        'clarification',  -- User provides more info
        'correction',     -- Agent was wrong
        'retry',          -- "try again", "let me rephrase"
        'refinement'      -- "actually, make it X instead"
    )),
    
    -- ============================================================
    -- REQUEST CLASSIFICATION
    -- ============================================================
    request_type TEXT CHECK(request_type IN (
        'procedural',     -- Multi-step process
        'query',          -- Information request
        'action',         -- Single discrete action
        'meta',           -- About the system
        'unclear'         -- Ambiguous
    )),
    
    -- ============================================================
    -- OUTCOME QUALITY (Epic #234 Gap #2)
    -- ============================================================
    expected_outcome TEXT,                      -- What should happen if routing succeeds?
    expected_first_pass_success BOOLEAN,        -- Should agent succeed first try?
    outcome_observed TEXT CHECK(outcome_observed IN (
        'success',        -- Agent succeeded
        'partial',        -- Partially successful
        'failure',        -- Agent failed
        'unknown',        -- Can't determine
        'not_observable'  -- No agent_response data
    )),
    outcome_notes TEXT,                         -- Details about outcome
    
    -- ============================================================
    -- ANTI-PATTERN DETECTION (Epic #234 Future Direction)
    -- ============================================================
    anti_pattern_detected BOOLEAN,
    anti_pattern_type TEXT,                     -- e.g., 'time_estimate_in_output', 'skipped_checklist'
    preventive_instruction TEXT,                -- Which instruction should have prevented this?
    preventive_instruction_was_routed BOOLEAN,  -- Was it actually routed?
    
    -- ============================================================
    -- CONTEXT COMPLETENESS (Epic #234 Goal #3)
    -- ============================================================
    context_sufficient BOOLEAN,                 -- Everything needed on first request?
    missing_context TEXT,                       -- What was missing?
    
    -- ============================================================
    -- METADATA
    -- ============================================================
    confidence TEXT CHECK(confidence IN ('high', 'medium', 'low')),
    notes TEXT,
    requires_agent_response BOOLEAN,            -- Does this event need agent_response for complete tagging?
    
    -- Tagging provenance
    tagger_id TEXT NOT NULL,                    -- Who/what tagged this: 'human:max', 'llm:codex', 'llm:claude'
    tagged_at TEXT DEFAULT (datetime('now')),
    tag_version INTEGER DEFAULT 1,              -- For tracking re-tags
    
    UNIQUE(event_id, tagger_id, tag_version)
);

-- ============================================================
-- VIEWS FOR ANALYSIS
-- ============================================================

-- View: Full event with tags
CREATE VIEW IF NOT EXISTS events_with_tags AS
SELECT 
    e.*,
    t.is_new_request,
    t.session_id AS tag_session_id,
    t.request_sequence,
    t.is_followup,
    t.is_correction,
    t.iteration_type,
    t.request_type,
    t.expected_outcome,
    t.outcome_observed,
    t.anti_pattern_detected,
    t.anti_pattern_type,
    t.confidence,
    t.tagger_id
FROM events e
LEFT JOIN tags t ON e.id = t.event_id;

-- View: Session statistics (for Epic #234 metrics)
CREATE VIEW IF NOT EXISTS session_stats AS
SELECT 
    t.session_id,
    COUNT(*) as event_count,
    SUM(CASE WHEN t.is_followup THEN 1 ELSE 0 END) as followup_count,
    SUM(CASE WHEN t.is_correction THEN 1 ELSE 0 END) as correction_count,
    MAX(t.request_sequence) as max_sequence,
    -- Iteration rate = (total - new requests) / new requests
    CAST(COUNT(*) - SUM(CASE WHEN t.is_new_request THEN 1 ELSE 0 END) AS FLOAT) / 
        NULLIF(SUM(CASE WHEN t.is_new_request THEN 1 ELSE 0 END), 0) as iteration_rate
FROM tags t
GROUP BY t.session_id;

-- View: Anti-pattern analysis
CREATE VIEW IF NOT EXISTS anti_pattern_analysis AS
SELECT 
    t.anti_pattern_type,
    t.preventive_instruction,
    COUNT(*) as occurrence_count,
    SUM(CASE WHEN t.preventive_instruction_was_routed THEN 1 ELSE 0 END) as routed_count,
    SUM(CASE WHEN NOT t.preventive_instruction_was_routed THEN 1 ELSE 0 END) as not_routed_count,
    -- If routed but anti-pattern occurred = instruction quality issue
    -- If not routed = routing failure
    ROUND(100.0 * SUM(CASE WHEN t.preventive_instruction_was_routed THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_instruction_quality_issue
FROM tags t
WHERE t.anti_pattern_detected = 1
GROUP BY t.anti_pattern_type, t.preventive_instruction;

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_events_source ON events(source_event_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_db_session ON events(db_session_id);

CREATE INDEX IF NOT EXISTS idx_tags_event ON tags(event_id);
CREATE INDEX IF NOT EXISTS idx_tags_session ON tags(session_id);
CREATE INDEX IF NOT EXISTS idx_tags_tagger ON tags(tagger_id);
CREATE INDEX IF NOT EXISTS idx_tags_iteration ON tags(is_followup, is_correction);
CREATE INDEX IF NOT EXISTS idx_tags_anti_pattern ON tags(anti_pattern_detected, anti_pattern_type);
