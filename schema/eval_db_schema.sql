-- Pongogo Collaboration Efficiency Schema Extension
-- Epic #234: Eval Methodology Reconception
--
-- PURPOSE: EXTEND the existing evaluation_dataset schema (docs/observability/evaluation_schema.sql)
--          with collaboration efficiency fields for Phase 2 metrics.
--
-- USAGE: Apply this schema to the existing evaluation_results.db database.
--        The collaboration_tags table links to evaluation_dataset.event_id.
--
-- EXISTING SCHEMA PROVIDES:
--   - evaluation_dataset: event_id, user_message, actual_routing, expected_routing, ground_truth_label
--   - tfidf_results, sentence_transformers_results: benchmark metrics
--   - benchmark_runs, comparison_analysis: aggregate analysis
--
-- THIS EXTENSION ADDS:
--   - collaboration_tags: Epic #234 conversation boundaries, iteration indicators, outcomes
--   - Views for collaboration efficiency metrics (iteration rate, first-pass success, etc.)

-- ============================================================================
-- COLLABORATION TAGS TABLE (Epic #234 Extension)
-- ============================================================================

CREATE TABLE IF NOT EXISTS collaboration_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Link to existing evaluation_dataset
    event_id TEXT NOT NULL,                     -- Links to evaluation_dataset.event_id
    
    -- ============================================================================
    -- CONVERSATION BOUNDARIES (Epic #234 Gap #1)
    -- ============================================================================
    is_new_request BOOLEAN,                     -- START of new task/conversation?
    tagged_session_id TEXT,                     -- Tagger-assigned session (may differ from DB session_id)
    request_sequence INTEGER,                   -- Position within session (1, 2, 3...)
    
    -- ============================================================================
    -- ITERATION INDICATORS (Epic #234 Phase 2)
    -- ============================================================================
    is_followup BOOLEAN,                        -- User checking previous work? ("did you...?")
    is_correction BOOLEAN,                      -- User correcting agent? ("no, I meant...")
    iteration_type TEXT CHECK(iteration_type IN (
        'none',           -- First attempt
        'clarification',  -- User provides more info
        'correction',     -- Agent was wrong
        'retry',          -- "try again", "let me rephrase"
        'refinement'      -- "actually, make it X instead"
    )),
    
    -- ============================================================================
    -- REQUEST CLASSIFICATION
    -- ============================================================================
    request_type TEXT CHECK(request_type IN (
        'procedural',     -- Multi-step process (issue closure, epic creation)
        'query',          -- Information request (what is X?)
        'action',         -- Single discrete action (commit, run tests)
        'meta',           -- About the system (how does Pongogo work?)
        'unclear'         -- Ambiguous intent
    )),
    
    -- ============================================================================
    -- OUTCOME QUALITY (Epic #234 Gap #2)
    -- ============================================================================
    expected_outcome TEXT,                      -- What SHOULD happen if routing succeeds?
    expected_first_pass_success BOOLEAN,        -- Should agent succeed first try with good routing?
    outcome_observed TEXT CHECK(outcome_observed IN (
        'success',        -- Agent succeeded
        'partial',        -- Partially successful
        'failure',        -- Agent failed
        'unknown',        -- Can't determine
        'not_observable'  -- No agent_response data available
    )),
    outcome_notes TEXT,                         -- Details about the outcome
    
    -- ============================================================================
    -- ANTI-PATTERN DETECTION (Epic #234 Future Direction)
    -- ============================================================================
    anti_pattern_detected BOOLEAN,
    anti_pattern_type TEXT,                     -- e.g., 'time_estimate_in_output', 'skipped_checklist', 'memory_over_routing'
    preventive_instruction TEXT,                -- Which instruction SHOULD have prevented this?
    preventive_instruction_was_routed BOOLEAN,  -- Was the preventive instruction actually routed?
    -- INTERPRETATION:
    --   routed=TRUE + anti_pattern=TRUE → Instruction quality issue (agent ignored guidance)
    --   routed=FALSE + anti_pattern=TRUE → Routing failure (should have been surfaced)
    
    -- ============================================================================
    -- CONTEXT COMPLETENESS (Epic #234 Goal #3)
    -- ============================================================================
    context_sufficient BOOLEAN,                 -- Was everything needed available on first request?
    missing_context TEXT,                       -- What was missing that caused iteration?
    
    -- ============================================================================
    -- AGENT RESPONSE (For Outcome/Anti-Pattern Analysis)
    -- ============================================================================
    agent_response TEXT,                        -- Full agent response (when available)
    agent_response_source TEXT,                 -- Where response came from: 'logs', 'manual', 'replay'
    
    -- ============================================================================
    -- TAGGING METADATA
    -- ============================================================================
    confidence TEXT CHECK(confidence IN ('high', 'medium', 'low')),
    notes TEXT,
    requires_agent_response BOOLEAN,            -- Does this event need agent_response for complete tagging?
    
    -- Tagging provenance
    tagger_id TEXT NOT NULL,                    -- Who/what tagged: 'human:max', 'llm:codex', 'llm:claude'
    tagged_at TEXT DEFAULT (datetime('now')),
    tag_version INTEGER DEFAULT 1,              -- For tracking re-tags
    
    -- Constraints
    UNIQUE(event_id, tagger_id, tag_version),
    FOREIGN KEY (event_id) REFERENCES evaluation_dataset(event_id)
);

-- ============================================================================
-- VIEWS FOR COLLABORATION EFFICIENCY METRICS
-- ============================================================================

-- View: Events with collaboration tags (joins existing eval data with new tags)
CREATE VIEW IF NOT EXISTS v_eval_with_collaboration AS
SELECT 
    e.*,
    c.is_new_request,
    c.tagged_session_id,
    c.request_sequence,
    c.is_followup,
    c.is_correction,
    c.iteration_type,
    c.request_type,
    c.expected_outcome,
    c.expected_first_pass_success,
    c.outcome_observed,
    c.anti_pattern_detected,
    c.anti_pattern_type,
    c.preventive_instruction,
    c.preventive_instruction_was_routed,
    c.confidence AS tag_confidence,
    c.tagger_id
FROM evaluation_dataset e
LEFT JOIN collaboration_tags c ON e.event_id = c.event_id;

-- View: Session statistics (Epic #234 Phase 2 core metric)
CREATE VIEW IF NOT EXISTS v_session_stats AS
SELECT 
    c.tagged_session_id AS session_id,
    COUNT(*) AS event_count,
    SUM(CASE WHEN c.is_new_request THEN 1 ELSE 0 END) AS new_request_count,
    SUM(CASE WHEN c.is_followup THEN 1 ELSE 0 END) AS followup_count,
    SUM(CASE WHEN c.is_correction THEN 1 ELSE 0 END) AS correction_count,
    MAX(c.request_sequence) AS max_sequence,
    
    -- ITERATION RATE: (total events - new requests) / new requests
    -- 1.0 = no iterations (perfect), 2.0 = one iteration per request, etc.
    ROUND(
        CAST(COUNT(*) AS FLOAT) / 
        NULLIF(SUM(CASE WHEN c.is_new_request THEN 1 ELSE 0 END), 0),
        2
    ) AS iteration_rate,
    
    -- FIRST-PASS SUCCESS RATE: successes / new requests
    ROUND(
        100.0 * SUM(CASE WHEN c.is_new_request AND c.outcome_observed = 'success' THEN 1 ELSE 0 END) / 
        NULLIF(SUM(CASE WHEN c.is_new_request THEN 1 ELSE 0 END), 0),
        1
    ) AS first_pass_success_pct,
    
    -- CORRECTION RATE: corrections / total events
    ROUND(
        100.0 * SUM(CASE WHEN c.is_correction THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(*), 0),
        1
    ) AS correction_rate_pct
    
FROM collaboration_tags c
GROUP BY c.tagged_session_id;

-- View: Anti-pattern analysis (Epic #234 Future Direction)
CREATE VIEW IF NOT EXISTS v_anti_pattern_analysis AS
SELECT 
    c.anti_pattern_type,
    c.preventive_instruction,
    COUNT(*) AS occurrence_count,
    SUM(CASE WHEN c.preventive_instruction_was_routed THEN 1 ELSE 0 END) AS instruction_routed_count,
    SUM(CASE WHEN c.preventive_instruction_was_routed = 0 THEN 1 ELSE 0 END) AS routing_failure_count,
    
    -- Diagnosis breakdown
    ROUND(100.0 * SUM(CASE WHEN c.preventive_instruction_was_routed THEN 1 ELSE 0 END) / COUNT(*), 1) 
        AS pct_instruction_quality_issue,  -- Routed but anti-pattern occurred
    ROUND(100.0 * SUM(CASE WHEN c.preventive_instruction_was_routed = 0 THEN 1 ELSE 0 END) / COUNT(*), 1) 
        AS pct_routing_failure              -- Not routed, should have been
        
FROM collaboration_tags c
WHERE c.anti_pattern_detected = 1
GROUP BY c.anti_pattern_type, c.preventive_instruction
ORDER BY occurrence_count DESC;

-- View: Iteration type breakdown
CREATE VIEW IF NOT EXISTS v_iteration_breakdown AS
SELECT 
    c.iteration_type,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM collaboration_tags), 1) AS pct_of_total,
    AVG(CASE WHEN e.ground_truth_label = 'FULL_SUCCESS' THEN 1.0 ELSE 0.0 END) AS avg_routing_success
FROM collaboration_tags c
JOIN evaluation_dataset e ON c.event_id = e.event_id
GROUP BY c.iteration_type
ORDER BY count DESC;

-- View: Request type performance
CREATE VIEW IF NOT EXISTS v_request_type_performance AS
SELECT 
    c.request_type,
    COUNT(*) AS event_count,
    AVG(CASE WHEN c.outcome_observed = 'success' THEN 1.0 ELSE 0.0 END) AS success_rate,
    AVG(CASE WHEN c.is_correction THEN 1.0 ELSE 0.0 END) AS correction_rate,
    AVG(e.f1_score) AS avg_routing_f1
FROM collaboration_tags c
JOIN evaluation_dataset e ON c.event_id = e.event_id
GROUP BY c.request_type
ORDER BY event_count DESC;

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_collab_event ON collaboration_tags(event_id);
CREATE INDEX IF NOT EXISTS idx_collab_session ON collaboration_tags(tagged_session_id);
CREATE INDEX IF NOT EXISTS idx_collab_tagger ON collaboration_tags(tagger_id);
CREATE INDEX IF NOT EXISTS idx_collab_iteration ON collaboration_tags(is_followup, is_correction);
CREATE INDEX IF NOT EXISTS idx_collab_anti_pattern ON collaboration_tags(anti_pattern_detected, anti_pattern_type);
CREATE INDEX IF NOT EXISTS idx_collab_outcome ON collaboration_tags(outcome_observed);
CREATE INDEX IF NOT EXISTS idx_collab_request_type ON collaboration_tags(request_type);

-- ============================================================================
-- SCHEMA VERSION
-- ============================================================================

-- Add to existing schema_version table
INSERT OR IGNORE INTO schema_version (version, description) VALUES
    ('2.0.0-epic234', 'Epic #234 collaboration efficiency extension - adds collaboration_tags table');
