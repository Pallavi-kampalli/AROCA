"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # roles
    op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    # user_roles
    op.create_table(
        "user_roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "role_id"),
    )

    # services
    op.create_table(
        "services",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("owner_team", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # environments
    op.create_table(
        "environments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # sla_policies
    op.create_table(
        "sla_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("response_time_minutes", sa.Integer, nullable=False),
        sa.Column("resolution_time_minutes", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # incidents
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("category", sa.String(200)),
        sa.Column("affected_component", sa.String(200)),
        sa.Column("business_impact", sa.Text),
        sa.Column("environment_name", sa.String(100)),
        sa.Column("reporter_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("assignee_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("service_id", sa.String(36), sa.ForeignKey("services.id", ondelete="SET NULL")),
        sa.Column("environment_id", sa.String(36), sa.ForeignKey("environments.id", ondelete="SET NULL")),
        sa.Column("sla_policy_id", sa.String(36), sa.ForeignKey("sla_policies.id", ondelete="SET NULL")),
        sa.Column("sla_breach", sa.Boolean, default=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extra_data", postgresql.JSONB),
    )
    op.create_index("ix_incidents_number", "incidents", ["number"])

    # incident_comments
    op.create_table(
        "incident_comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_internal", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incident_comments_incident_id", "incident_comments", ["incident_id"])

    # incident_events
    op.create_table(
        "incident_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("metadata", postgresql.JSONB),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incident_events_incident_id", "incident_events", ["incident_id"])

    # incident_relationships
    op.create_table(
        "incident_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(50), default="related"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # uploaded_artifacts
    op.create_table(
        "uploaded_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100)),
        sa.Column("file_size_bytes", sa.BigInteger, default=0),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("uploader_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_uploaded_artifacts_incident_id", "uploaded_artifacts", ["incident_id"])

    # log_ingestion_jobs
    op.create_table(
        "log_ingestion_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("uploaded_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("total_lines", sa.Integer, default=0),
        sa.Column("parsed_events", sa.Integer, default=0),
        sa.Column("failed_lines", sa.Integer, default=0),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_log_ingestion_jobs_incident_id", "log_ingestion_jobs", ["incident_id"])

    # log_events
    op.create_table(
        "log_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ingestion_job_id", sa.String(36), sa.ForeignKey("log_ingestion_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer),
        sa.Column("timestamp", sa.DateTime(timezone=True)),
        sa.Column("level", sa.String(20), default="UNKNOWN"),
        sa.Column("source", sa.String(200)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("raw_line", sa.Text),
        sa.Column("correlation_id", sa.String(200)),
        sa.Column("service_name", sa.String(200)),
        sa.Column("extra_fields", postgresql.JSONB),
        sa.Column("is_anomalous", sa.Boolean, default=False),
        sa.Column("anomaly_score", sa.Float),
    )
    op.create_index("ix_log_events_ingestion_job_id", "log_events", ["ingestion_job_id"])
    op.create_index("ix_log_events_timestamp", "log_events", ["timestamp"])
    op.create_index("ix_log_events_level", "log_events", ["level"])

    # error_signatures
    op.create_table(
        "error_signatures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("signature_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("pattern", sa.Text, nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurrence_count", sa.Integer, default=1),
        sa.Column("associated_incident_ids", postgresql.JSONB),
    )
    op.create_index("ix_error_signatures_hash", "error_signatures", ["signature_hash"])

    # ml_models
    op.create_table(
        "ml_models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("model_type", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("artifact_path", sa.String(500)),
        sa.Column("is_active", sa.Boolean, default=False),
        sa.Column("training_samples", sa.Integer, default=0),
        sa.Column("features_used", postgresql.JSONB),
        sa.Column("hyperparameters", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ml_training_runs
    op.create_table(
        "ml_training_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), default="pending"),
        sa.Column("samples_used", sa.Integer, default=0),
        sa.Column("features_count", sa.Integer, default=0),
        sa.Column("metrics", postgresql.JSONB),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ml_inference_results
    op.create_table(
        "ml_inference_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="SET NULL")),
        sa.Column("ingestion_job_id", sa.String(36), sa.ForeignKey("log_ingestion_jobs.id", ondelete="SET NULL")),
        sa.Column("anomaly_score", sa.Float),
        sa.Column("is_anomalous", sa.Boolean, default=False),
        sa.Column("features_used", postgresql.JSONB),
        sa.Column("contributing_features", postgresql.JSONB),
        sa.Column("data_sufficient", sa.Boolean, default=False),
        sa.Column("explanation", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # rca_analysis_runs
    op.create_table(
        "rca_analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), default="PENDING"),
        sa.Column("llm_provider", sa.String(100)),
        sa.Column("llm_model", sa.String(200)),
        sa.Column("ml_inference_id", sa.String(36), sa.ForeignKey("ml_inference_results.id", ondelete="SET NULL")),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("error_message", sa.Text),
        sa.Column("summary", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("triggered_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
    )
    op.create_index("ix_rca_analysis_runs_incident_id", "rca_analysis_runs", ["incident_id"])

    # rca_candidate_causes
    op.create_table(
        "rca_candidate_causes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_run_id", sa.String(36), sa.ForeignKey("rca_analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("confidence_label", sa.String(50), default="UNCERTAIN"),
        sa.Column("confidence_score", sa.Float),
        sa.Column("supporting_evidence", postgresql.JSONB),
        sa.Column("contradicting_evidence", postgresql.JSONB),
        sa.Column("missing_evidence", postgresql.JSONB),
        sa.Column("affected_components", postgresql.JSONB),
        sa.Column("relevant_timestamps", postgresql.JSONB),
        sa.Column("human_validated", sa.Boolean),
        sa.Column("human_label", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # rca_evidence_links
    op.create_table(
        "rca_evidence_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cause_id", sa.String(36), sa.ForeignKey("rca_candidate_causes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_type", sa.String(50)),
        sa.Column("reference_id", sa.String(36)),
        sa.Column("reference_table", sa.String(100)),
        sa.Column("description", sa.Text),
        sa.Column("relevance_score", sa.Float),
    )

    # remediation_actions
    op.create_table(
        "remediation_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_run_id", sa.String(36), sa.ForeignKey("rca_analysis_runs.id", ondelete="SET NULL")),
        sa.Column("cause_id", sa.String(36), sa.ForeignKey("rca_candidate_causes.id", ondelete="SET NULL")),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("parameters", postgresql.JSONB),
        sa.Column("risk_level", sa.String(50), default="MEDIUM"),
        sa.Column("requires_approval", sa.Boolean, default=True),
        sa.Column("expected_outcome", sa.Text),
        sa.Column("rollback_procedure", sa.Text),
        sa.Column("proposed_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_remediation_actions_incident_id", "remediation_actions", ["incident_id"])

    # approval_requests
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action_id", sa.String(36), sa.ForeignKey("remediation_actions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewed_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(50), default="PENDING"),
        sa.Column("reason", sa.Text),
        sa.Column("review_notes", sa.Text),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )

    # remediation_executions
    op.create_table(
        "remediation_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action_id", sa.String(36), sa.ForeignKey("remediation_actions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approval_id", sa.String(36), sa.ForeignKey("approval_requests.id", ondelete="SET NULL")),
        sa.Column("executed_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(50), default="PENDING"),
        sa.Column("output", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # verification_results
    op.create_table(
        "verification_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_id", sa.String(36), sa.ForeignKey("remediation_executions.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("is_resolved", sa.Boolean, nullable=False),
        sa.Column("verification_method", sa.String(100)),
        sa.Column("evidence", sa.Text),
        sa.Column("verified_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # knowledge_documents
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source_incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="SET NULL")),
        sa.Column("is_verified", sa.Boolean, default=False),
        sa.Column("verified_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("tags", postgresql.JSONB),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # knowledge_chunks
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text),  # stored as text, cast later when pgvector available
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # historical_incident_links
    op.create_table(
        "historical_incident_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_run_id", sa.String(36), sa.ForeignKey("rca_analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("similar_incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("similarity_score", sa.Float),
        sa.Column("resolution_applicable", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # copilot_messages
    op.create_table(
        "copilot_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("evidence_references", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_copilot_messages_incident_id", "copilot_messages", ["incident_id"])

    # llm_usage_records
    op.create_table(
        "llm_usage_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(100)),
        sa.Column("model", sa.String(200)),
        sa.Column("operation", sa.String(100)),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="SET NULL")),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("success", sa.Boolean, default=True),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("details", postgresql.JSONB),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # Insert default roles (system metadata, not operational data)
    op.execute("""
        INSERT INTO roles (id, name, description, created_at) VALUES
        (gen_random_uuid()::text, 'admin', 'Full system administrator', NOW()),
        (gen_random_uuid()::text, 'engineer', 'IT Engineer with full incident access', NOW()),
        (gen_random_uuid()::text, 'l1_support', 'Level 1 Support Engineer', NOW()),
        (gen_random_uuid()::text, 'l2_support', 'Level 2 Support Engineer', NOW()),
        (gen_random_uuid()::text, 'auditor', 'Read-only auditor', NOW())
    """)

    # Insert default SLA policies (system metadata)
    op.execute("""
        INSERT INTO sla_policies (id, name, severity, response_time_minutes, resolution_time_minutes, created_at) VALUES
        (gen_random_uuid()::text, 'Critical SLA', 'CRITICAL', 15, 240, NOW()),
        (gen_random_uuid()::text, 'High SLA', 'HIGH', 30, 480, NOW()),
        (gen_random_uuid()::text, 'Medium SLA', 'MEDIUM', 120, 1440, NOW()),
        (gen_random_uuid()::text, 'Low SLA', 'LOW', 480, 4320, NOW())
    """)


def downgrade() -> None:
    tables = [
        "audit_logs", "llm_usage_records", "copilot_messages",
        "historical_incident_links", "knowledge_chunks", "knowledge_documents",
        "verification_results", "remediation_executions", "approval_requests",
        "remediation_actions", "rca_evidence_links", "rca_candidate_causes",
        "rca_analysis_runs", "ml_inference_results", "ml_training_runs",
        "ml_models", "error_signatures", "log_events", "log_ingestion_jobs",
        "uploaded_artifacts", "incident_relationships", "incident_events",
        "incident_comments", "incidents", "sla_policies", "environments",
        "services", "user_roles", "users", "roles",
    ]
    for t in tables:
        op.drop_table(t)
    op.execute("DROP EXTENSION IF EXISTS vector")
