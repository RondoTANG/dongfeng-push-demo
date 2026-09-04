from __future__ import annotations


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS collection_runs (
        run_id TEXT PRIMARY KEY,
        idempotency_key TEXT UNIQUE,
        trigger_type TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'quick',
        status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        config_versions_json TEXT NOT NULL DEFAULT '{}',
        query_coverage_json TEXT NOT NULL DEFAULT '{}',
        provider_summary_json TEXT NOT NULL DEFAULT '{}',
        step_summary_json TEXT NOT NULL DEFAULT '{}',
        error_message TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS query_jobs (
        query_job_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        query_id TEXT NOT NULL,
        query_text TEXT NOT NULL,
        query_group TEXT NOT NULL,
        status TEXT NOT NULL,
        retry_count INTEGER NOT NULL DEFAULT 0,
        provider_id TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        result_count INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        FOREIGN KEY (run_id) REFERENCES collection_runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_provider_results (
        raw_result_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        provider_id TEXT NOT NULL,
        query_id TEXT NOT NULL,
        request_started_at TEXT,
        response_received_at TEXT,
        request_status TEXT NOT NULL,
        provider_request_id TEXT,
        raw_payload_json TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES collection_runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_items (
        source_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        raw_result_id TEXT,
        retrieved_by TEXT NOT NULL,
        query_ids_json TEXT NOT NULL DEFAULT '[]',
        source_status TEXT NOT NULL,
        source_platform TEXT NOT NULL,
        source_site_name TEXT,
        source_account TEXT,
        original_url TEXT NOT NULL,
        canonical_url TEXT NOT NULL,
        domain TEXT,
        title TEXT NOT NULL,
        snippet TEXT,
        published_at TEXT,
        published_time_confidence TEXT NOT NULL DEFAULT 'unknown',
        fetched_at TEXT NOT NULL,
        first_seen_at TEXT NOT NULL,
        provider_authority_level TEXT,
        duplicate_of_source_id TEXT,
        event_id TEXT,
        FOREIGN KEY (run_id) REFERENCES collection_runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_discoveries (
        discovery_id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        raw_result_id TEXT,
        query_job_id TEXT NOT NULL,
        provider_id TEXT NOT NULL,
        query_id TEXT NOT NULL,
        query_text TEXT NOT NULL,
        provider_rank INTEGER,
        provider_title TEXT,
        provider_snippet TEXT,
        retrieved_at TEXT NOT NULL,
        UNIQUE (source_id, provider_id, query_id),
        FOREIGN KEY (source_id) REFERENCES source_items(source_id),
        FOREIGN KEY (run_id) REFERENCES collection_runs(run_id),
        FOREIGN KEY (query_job_id) REFERENCES query_jobs(query_job_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invalid_logs (
        invalid_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        source_id_or_raw_result_id TEXT NOT NULL,
        invalid_rule_id TEXT NOT NULL,
        invalid_reason TEXT NOT NULL,
        discarded_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES collection_runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        event_title TEXT NOT NULL,
        primary_entity_id_or_name TEXT,
        event_action TEXT,
        event_date TEXT,
        source_count INTEGER NOT NULL DEFAULT 0,
        independent_source_count INTEGER NOT NULL DEFAULT 0,
        source_platforms_json TEXT NOT NULL DEFAULT '[]',
        brand_relations_json TEXT NOT NULL DEFAULT '[]',
        entity_mentions_json TEXT NOT NULL DEFAULT '[]',
        entity_uncertainties_json TEXT NOT NULL DEFAULT '[]',
        risk_tags_json TEXT NOT NULL DEFAULT '[]',
        missing_evidence_json TEXT NOT NULL DEFAULT '[]',
        hotspot_judgement_available INTEGER NOT NULL DEFAULT 0,
        hotspot_status TEXT NOT NULL DEFAULT 'unknown',
        hotspot_unavailable_reason_json TEXT NOT NULL DEFAULT '[]',
        event_status TEXT NOT NULL DEFAULT 'pending_review',
        decision_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES collection_runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_evidence (
        evidence_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        source_id TEXT,
        evidence_type TEXT NOT NULL,
        evidence_text TEXT NOT NULL,
        evidence_url TEXT,
        provided_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(event_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS codex_work_items (
        work_item_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        work_type TEXT NOT NULL,
        status TEXT NOT NULL,
        input_json TEXT NOT NULL DEFAULT '{}',
        output_json TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        locked_by TEXT,
        locked_at TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        error_message TEXT,
        FOREIGN KEY (event_id) REFERENCES events(event_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_requests (
        evidence_request_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        status TEXT NOT NULL,
        question TEXT NOT NULL,
        unresolved_items_json TEXT NOT NULL DEFAULT '[]',
        search_queries_json TEXT NOT NULL DEFAULT '[]',
        selected_methods_json TEXT NOT NULL DEFAULT '[]',
        lookback_hours INTEGER NOT NULL DEFAULT 72,
        estimated_calls_json TEXT NOT NULL DEFAULT '{}',
        confirmed_by TEXT,
        confirmed_at TEXT,
        result_summary TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        error_message TEXT,
        FOREIGN KEY (event_id) REFERENCES events(event_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_jobs (
        evidence_job_id TEXT PRIMARY KEY,
        evidence_request_id TEXT NOT NULL,
        provider_id TEXT NOT NULL,
        query_text TEXT,
        status TEXT NOT NULL,
        result_count INTEGER NOT NULL DEFAULT 0,
        result_json TEXT,
        started_at TEXT,
        finished_at TEXT,
        error_message TEXT,
        FOREIGN KEY (evidence_request_id) REFERENCES evidence_requests(evidence_request_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_reviews (
        candidate_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        event_status TEXT NOT NULL,
        evidence_summary TEXT,
        risk_summary TEXT,
        recommended_action TEXT,
        review_result TEXT NOT NULL,
        reviewer TEXT NOT NULL,
        review_note TEXT,
        reviewed_at TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(event_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS task_drafts (
        task_draft_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        draft_purpose TEXT NOT NULL DEFAULT 'original_growth',
        target_source_id TEXT NOT NULL DEFAULT '',
        target_submission_id TEXT NOT NULL DEFAULT '',
        trigger_evaluation_id TEXT,
        target_url TEXT,
        target_content_title TEXT,
        task_type TEXT NOT NULL,
        task_title TEXT NOT NULL,
        task_brief TEXT NOT NULL,
        recommended_platforms_json TEXT NOT NULL DEFAULT '[]',
        target_member_tags_json TEXT NOT NULL DEFAULT '[]',
        engagement_actions_json TEXT NOT NULL DEFAULT '[]',
        response_deadline TEXT,
        evidence_source_ids_json TEXT NOT NULL DEFAULT '[]',
        prohibited_claims_json TEXT NOT NULL DEFAULT '[]',
        risk_notes_json TEXT NOT NULL DEFAULT '[]',
        task_status TEXT NOT NULL DEFAULT 'draft_pending_review',
        reviewer TEXT,
        review_note TEXT,
        reviewed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (event_id, draft_purpose, target_source_id, target_submission_id),
        FOREIGN KEY (event_id) REFERENCES events(event_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS original_publications (
        publication_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        original_draft_id TEXT NOT NULL,
        platform TEXT NOT NULL,
        content_url TEXT NOT NULL UNIQUE,
        content_title TEXT,
        platform_content_id TEXT,
        published_at TEXT NOT NULL,
        submitted_by TEXT NOT NULL,
        submitted_at TEXT NOT NULL,
        tracking_status TEXT NOT NULL DEFAULT 'tracking',
        latest_evaluation_id TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(event_id),
        FOREIGN KEY (original_draft_id) REFERENCES task_drafts(task_draft_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS publication_metric_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        publication_id TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        data_source TEXT NOT NULL,
        metrics_json TEXT NOT NULL DEFAULT '{}',
        unavailable_reason TEXT,
        note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (publication_id) REFERENCES original_publications(publication_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS publication_evaluations (
        evaluation_id TEXT PRIMARY KEY,
        publication_id TEXT NOT NULL,
        baseline_snapshot_id TEXT,
        latest_snapshot_id TEXT,
        delta_metrics_json TEXT NOT NULL DEFAULT '{}',
        growth_status TEXT NOT NULL,
        decision TEXT NOT NULL,
        decision_reason TEXT NOT NULL,
        evaluated_by TEXT NOT NULL,
        evaluated_at TEXT NOT NULL,
        created_draft_id TEXT,
        FOREIGN KEY (publication_id) REFERENCES original_publications(publication_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        audit_id TEXT PRIMARY KEY,
        actor_type TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        action TEXT NOT NULL,
        object_type TEXT NOT NULL,
        object_id TEXT NOT NULL,
        before_json TEXT,
        after_json TEXT,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_queries_run ON query_jobs(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_sources_run ON source_items(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_sources_event ON source_items(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_discoveries_source ON source_discoveries(source_id, retrieved_at)",
    "CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_work_items_status ON codex_work_items(status)",
    "CREATE INDEX IF NOT EXISTS idx_evidence_requests_event ON evidence_requests(event_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_publications_status ON original_publications(tracking_status)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_publication ON publication_metric_snapshots(publication_id, captured_at)",
    "CREATE INDEX IF NOT EXISTS idx_evaluations_publication ON publication_evaluations(publication_id, evaluated_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_object ON audit_logs(object_type, object_id)",
]


JSON_FIELDS = {
    "config_versions_json",
    "query_coverage_json",
    "provider_summary_json",
    "step_summary_json",
    "query_ids_json",
    "source_platforms_json",
    "brand_relations_json",
    "entity_mentions_json",
    "entity_uncertainties_json",
    "risk_tags_json",
    "missing_evidence_json",
    "hotspot_unavailable_reason_json",
    "input_json",
    "output_json",
    "unresolved_items_json",
    "search_queries_json",
    "selected_methods_json",
    "estimated_calls_json",
    "result_json",
    "recommended_platforms_json",
    "target_member_tags_json",
    "engagement_actions_json",
    "evidence_source_ids_json",
    "prohibited_claims_json",
    "risk_notes_json",
    "metrics_json",
    "delta_metrics_json",
    "before_json",
    "after_json",
}
