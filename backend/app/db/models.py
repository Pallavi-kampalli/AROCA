"""
All SQLAlchemy ORM models for TraceIQ.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    String, Text, Boolean, Float, Integer, DateTime, ForeignKey,
    Enum as SAEnum, JSON, UniqueConstraint, Index, BigInteger
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from app.db.session import Base
import enum


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid.uuid4())


# ─── Enums ────────────────────────────────────────────────────────────────────

class IncidentStatus(str, enum.Enum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    INVESTIGATING = "INVESTIGATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


class Severity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AnalysisStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# ─── User & Auth ──────────────────────────────────────────────────────────────

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user_roles: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="role")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    user_roles: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="user")
    incidents_reported: Mapped[List["Incident"]] = relationship("Incident", foreign_keys="Incident.reporter_id", back_populates="reporter")
    incidents_assigned: Mapped[List["Incident"]] = relationship("Incident", foreign_keys="Incident.assignee_id", back_populates="assignee")
    comments: Mapped[List["IncidentComment"]] = relationship("IncidentComment", back_populates="author")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")

    @property
    def roles(self):
        return [ur.role for ur in self.user_roles]


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped["User"] = relationship("User", back_populates="user_roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")


# ─── Infrastructure ──────────────────────────────────────────────────────────

class Service(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_team: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    incidents: Mapped[List["Incident"]] = relationship("Incident", back_populates="service")


class Environment(Base):
    __tablename__ = "environments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    incidents: Mapped[List["Incident"]] = relationship("Incident", back_populates="environment")


# ─── Incidents ────────────────────────────────────────────────────────────────

class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(SAEnum(Severity), nullable=False)
    response_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(SAEnum(Severity), nullable=False, default=Severity.MEDIUM)
    status: Mapped[str] = mapped_column(SAEnum(IncidentStatus), nullable=False, default=IncidentStatus.NEW)
    category: Mapped[Optional[str]] = mapped_column(String(200))
    affected_component: Mapped[Optional[str]] = mapped_column(String(200))
    business_impact: Mapped[Optional[str]] = mapped_column(Text)
    environment_name: Mapped[Optional[str]] = mapped_column(String(100))
    reporter_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    assignee_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    service_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("services.id", ondelete="SET NULL"))
    environment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("environments.id", ondelete="SET NULL"))
    sla_policy_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sla_policies.id", ondelete="SET NULL"))
    sla_breach: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    reporter: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reporter_id], back_populates="incidents_reported")
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assignee_id], back_populates="incidents_assigned")
    service: Mapped[Optional["Service"]] = relationship("Service", back_populates="incidents")
    environment: Mapped[Optional["Environment"]] = relationship("Environment", back_populates="incidents")
    comments: Mapped[List["IncidentComment"]] = relationship("IncidentComment", back_populates="incident", cascade="all, delete-orphan")
    events: Mapped[List["IncidentEvent"]] = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan")
    artifacts: Mapped[List["UploadedArtifact"]] = relationship("UploadedArtifact", back_populates="incident", cascade="all, delete-orphan")
    log_ingestion_jobs: Mapped[List["LogIngestionJob"]] = relationship("LogIngestionJob", back_populates="incident", cascade="all, delete-orphan")
    rca_runs: Mapped[List["RCAAnalysisRun"]] = relationship("RCAAnalysisRun", back_populates="incident", cascade="all, delete-orphan")
    related_from: Mapped[List["IncidentRelationship"]] = relationship("IncidentRelationship", foreign_keys="IncidentRelationship.source_id", back_populates="source")
    related_to: Mapped[List["IncidentRelationship"]] = relationship("IncidentRelationship", foreign_keys="IncidentRelationship.target_id", back_populates="target")
    copilot_messages: Mapped[List["CopilotMessage"]] = relationship("CopilotMessage", back_populates="incident", cascade="all, delete-orphan")


class IncidentComment(Base):
    __tablename__ = "incident_comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    incident: Mapped["Incident"] = relationship("Incident", back_populates="comments")
    author: Mapped[Optional["User"]] = relationship("User", back_populates="comments")


class IncidentEvent(Base):
    __tablename__ = "incident_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    incident: Mapped["Incident"] = relationship("Incident", back_populates="events")


class IncidentRelationship(Base):
    __tablename__ = "incident_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(50), default="related")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped["Incident"] = relationship("Incident", foreign_keys=[source_id], back_populates="related_from")
    target: Mapped["Incident"] = relationship("Incident", foreign_keys=[target_id], back_populates="related_to")


# ─── Log Ingestion ────────────────────────────────────────────────────────────

class UploadedArtifact(Base):
    __tablename__ = "uploaded_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploader_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    incident: Mapped["Incident"] = relationship("Incident", back_populates="artifacts")
    ingestion_jobs: Mapped[List["LogIngestionJob"]] = relationship("LogIngestionJob", back_populates="artifact")


class LogIngestionJob(Base):
    __tablename__ = "log_ingestion_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_id: Mapped[str] = mapped_column(String(36), ForeignKey("uploaded_artifacts.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    total_lines: Mapped[int] = mapped_column(Integer, default=0)
    parsed_events: Mapped[int] = mapped_column(Integer, default=0)
    failed_lines: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    incident: Mapped["Incident"] = relationship("Incident", back_populates="log_ingestion_jobs")
    artifact: Mapped["UploadedArtifact"] = relationship("UploadedArtifact", back_populates="ingestion_jobs")
    log_events: Mapped[List["LogEvent"]] = relationship("LogEvent", back_populates="ingestion_job", cascade="all, delete-orphan")


class LogEvent(Base):
    __tablename__ = "log_events"
    __table_args__ = (
        Index("idx_log_events_incident_ts", "ingestion_job_id", "timestamp"),
        Index("idx_log_events_level", "level"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    ingestion_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("log_ingestion_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[Optional[int]] = mapped_column(Integer)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    level: Mapped[str] = mapped_column(SAEnum(LogLevel), default=LogLevel.UNKNOWN)
    source: Mapped[Optional[str]] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_line: Mapped[Optional[str]] = mapped_column(Text)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    service_name: Mapped[Optional[str]] = mapped_column(String(200))
    extra_fields: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_anomalous: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_score: Mapped[Optional[float]] = mapped_column(Float)
    ingestion_job: Mapped["LogIngestionJob"] = relationship("LogIngestionJob", back_populates="log_events")


class ErrorSignature(Base):
    __tablename__ = "error_signatures"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    signature_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    associated_incident_ids: Mapped[Optional[list]] = mapped_column(JSONB, default=list)


# ─── ML Models ────────────────────────────────────────────────────────────────

class MLModel(Base):
    __tablename__ = "ml_models"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    training_samples: Mapped[int] = mapped_column(Integer, default=0)
    features_used: Mapped[Optional[list]] = mapped_column(JSONB)
    hyperparameters: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    training_runs: Mapped[List["MLTrainingRun"]] = relationship("MLTrainingRun", back_populates="model")
    inference_results: Mapped[List["MLInferenceResult"]] = relationship("MLInferenceResult", back_populates="model")


class MLTrainingRun(Base):
    __tablename__ = "ml_training_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    samples_used: Mapped[int] = mapped_column(Integer, default=0)
    features_count: Mapped[int] = mapped_column(Integer, default=0)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    model: Mapped["MLModel"] = relationship("MLModel", back_populates="training_runs")


class MLInferenceResult(Base):
    __tablename__ = "ml_inference_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False)
    incident_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="SET NULL"), index=True)
    ingestion_job_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("log_ingestion_jobs.id", ondelete="SET NULL"))
    anomaly_score: Mapped[Optional[float]] = mapped_column(Float)
    is_anomalous: Mapped[bool] = mapped_column(Boolean, default=False)
    features_used: Mapped[Optional[dict]] = mapped_column(JSONB)
    contributing_features: Mapped[Optional[list]] = mapped_column(JSONB)
    data_sufficient: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    model: Mapped["MLModel"] = relationship("MLModel", back_populates="inference_results")


# ─── RCA ─────────────────────────────────────────────────────────────────────

class RCAAnalysisRun(Base):
    __tablename__ = "rca_analysis_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(SAEnum(AnalysisStatus), default=AnalysisStatus.PENDING)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(100))
    llm_model: Mapped[Optional[str]] = mapped_column(String(200))
    ml_inference_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("ml_inference_results.id", ondelete="SET NULL"))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    triggered_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    incident: Mapped["Incident"] = relationship("Incident", back_populates="rca_runs")
    candidate_causes: Mapped[List["RCACandidateCause"]] = relationship("RCACandidateCause", back_populates="analysis_run", cascade="all, delete-orphan")
    remediation_proposals: Mapped[List["RemediationAction"]] = relationship("RemediationAction", back_populates="analysis_run")


class RCACandidateCause(Base):
    __tablename__ = "rca_candidate_causes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    analysis_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("rca_analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_label: Mapped[str] = mapped_column(String(50), default="UNCERTAIN")
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    supporting_evidence: Mapped[Optional[list]] = mapped_column(JSONB)
    contradicting_evidence: Mapped[Optional[list]] = mapped_column(JSONB)
    missing_evidence: Mapped[Optional[list]] = mapped_column(JSONB)
    affected_components: Mapped[Optional[list]] = mapped_column(JSONB)
    relevant_timestamps: Mapped[Optional[list]] = mapped_column(JSONB)
    human_validated: Mapped[Optional[bool]] = mapped_column(Boolean)
    human_label: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    analysis_run: Mapped["RCAAnalysisRun"] = relationship("RCAAnalysisRun", back_populates="candidate_causes")
    evidence_links: Mapped[List["RCAEvidenceLink"]] = relationship("RCAEvidenceLink", back_populates="cause", cascade="all, delete-orphan")


class RCAEvidenceLink(Base):
    __tablename__ = "rca_evidence_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    cause_id: Mapped[str] = mapped_column(String(36), ForeignKey("rca_candidate_causes.id", ondelete="CASCADE"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50))
    reference_id: Mapped[Optional[str]] = mapped_column(String(36))
    reference_table: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    cause: Mapped["RCACandidateCause"] = relationship("RCACandidateCause", back_populates="evidence_links")


# ─── Remediation ─────────────────────────────────────────────────────────────

class RemediationAction(Base):
    __tablename__ = "remediation_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    analysis_run_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rca_analysis_runs.id", ondelete="SET NULL"))
    cause_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("rca_candidate_causes.id", ondelete="SET NULL"))
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    action_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    parameters: Mapped[Optional[dict]] = mapped_column(JSONB)
    risk_level: Mapped[str] = mapped_column(SAEnum(RiskLevel), default=RiskLevel.MEDIUM)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text)
    rollback_procedure: Mapped[Optional[str]] = mapped_column(Text)
    proposed_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    analysis_run: Mapped[Optional["RCAAnalysisRun"]] = relationship("RCAAnalysisRun", back_populates="remediation_proposals")
    approval_requests: Mapped[List["ApprovalRequest"]] = relationship("ApprovalRequest", back_populates="action")
    executions: Mapped[List["RemediationExecution"]] = relationship("RemediationExecution", back_populates="action")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    action_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_actions.id", ondelete="CASCADE"), nullable=False)
    requested_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reviewed_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    action: Mapped["RemediationAction"] = relationship("RemediationAction", back_populates="approval_requests")


class RemediationExecution(Base):
    __tablename__ = "remediation_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    action_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_actions.id", ondelete="CASCADE"), nullable=False)
    approval_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("approval_requests.id", ondelete="SET NULL"))
    executed_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(SAEnum(ExecutionStatus), default=ExecutionStatus.PENDING)
    output: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verification: Mapped[Optional["VerificationResult"]] = relationship("VerificationResult", back_populates="execution", uselist=False)
    action: Mapped["RemediationAction"] = relationship("RemediationAction", back_populates="executions")


class VerificationResult(Base):
    __tablename__ = "verification_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    execution_id: Mapped[str] = mapped_column(String(36), ForeignKey("remediation_executions.id", ondelete="CASCADE"), unique=True, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    verification_method: Mapped[str] = mapped_column(String(100))
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    verified_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    execution: Mapped["RemediationExecution"] = relationship("RemediationExecution", back_populates="verification")


# ─── Knowledge Base ────────────────────────────────────────────────────────────

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_incident_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="SET NULL"))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    tags: Mapped[Optional[list]] = mapped_column(JSONB)
    created_by_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    chunks: Mapped[List["KnowledgeChunk"]] = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(384))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    document: Mapped["KnowledgeDocument"] = relationship("KnowledgeDocument", back_populates="chunks")


class HistoricalIncidentLink(Base):
    __tablename__ = "historical_incident_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    analysis_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("rca_analysis_runs.id", ondelete="CASCADE"), nullable=False)
    similar_incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float)
    resolution_applicable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ─── AI Copilot ──────────────────────────────────────────────────────────────

class CopilotMessage(Base):
    __tablename__ = "copilot_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    evidence_references: Mapped[Optional[list]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    incident: Mapped["Incident"] = relationship("Incident", back_populates="copilot_messages")


# ─── LLM Usage ───────────────────────────────────────────────────────────────

class LLMUsageRecord(Base):
    __tablename__ = "llm_usage_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    operation: Mapped[str] = mapped_column(String(100))
    incident_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("incidents.id", ondelete="SET NULL"))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ─── Audit ────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
