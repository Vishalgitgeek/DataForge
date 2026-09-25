from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class DatasetVersionStatus(str, Enum):
    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ColumnType(str, Enum):
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    DATETIME = "DATETIME"
    TEXT = "TEXT"
    UNKNOWN = "UNKNOWN"


class QualityStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class QueryStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AnalysisStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    datasets: Mapped[list["Dataset"]] = relationship(back_populates="owner")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")
    query_history: Mapped[list["QueryHistory"]] = relationship(back_populates="user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_refresh_tokens_user_revoked_expires", "user_id", "revoked_at", "expires_at"),
    )


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="datasets")
    versions: Mapped[list["DatasetVersion"]] = relationship(back_populates="dataset")

    __table_args__ = (
        Index("uq_datasets_active_owner_name", "owner_id", text("lower(name)"), unique=True, postgresql_where="deleted_at IS NULL"),
    )


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DatasetVersionStatus] = mapped_column(SAEnum(DatasetVersionStatus, name="dataset_version_status"), nullable=False)
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    dataset: Mapped[Dataset] = relationship(back_populates="versions")
    files: Mapped[list["DatasetFile"]] = relationship(back_populates="version")
    columns: Mapped[list["DatasetColumn"]] = relationship(back_populates="version")
    profiles: Mapped[list["Profile"]] = relationship(back_populates="version")
    quality_results: Mapped[list["QualityResult"]] = relationship(back_populates="version")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="version")
    processing_jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="version")
    query_history: Mapped[list["QueryHistory"]] = relationship(back_populates="version")

    __table_args__ = (
        Index("uq_dataset_versions_dataset_number", "dataset_id", "version_number", unique=True),
        Index("ix_dataset_versions_dataset_created", "dataset_id", "created_at"),
    )


class DatasetFile(Base):
    __tablename__ = "dataset_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False, unique=True)
    storage_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(32), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    version: Mapped[DatasetVersion] = relationship(back_populates="files")


class DatasetColumn(Base):
    __tablename__ = "dataset_columns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    inferred_type: Mapped[ColumnType] = mapped_column(SAEnum(ColumnType, name="column_type"), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    version: Mapped[DatasetVersion] = relationship(back_populates="columns")
    statistics: Mapped["ColumnStatistics"] = relationship(back_populates="column")

    __table_args__ = (
        Index("uq_dataset_columns_version_ordinal", "version_id", "ordinal", unique=True),
        Index("uq_dataset_columns_version_name", "version_id", "normalized_name", unique=True),
    )


class ColumnStatistics(Base):
    __tablename__ = "column_statistics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    column_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_columns.id"), nullable=False, unique=True)
    null_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    null_fraction: Mapped[float] = mapped_column(Numeric(8, 7), nullable=False)
    unique_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uniqueness_ratio: Mapped[float | None] = mapped_column(Numeric(8, 7), nullable=True)
    sample_values: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    numeric_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    categorical_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    datetime_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    column: Mapped[DatasetColumn] = relationship(back_populates="statistics")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False, unique=True)
    duplicate_row_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    version: Mapped[DatasetVersion] = relationship(back_populates="profiles")


class QualityResult(Base):
    __tablename__ = "quality_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False)
    check_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[QualityStatus] = mapped_column(SAEnum(QualityStatus, name="quality_status"), nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    affected_rows: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    version: Mapped[DatasetVersion] = relationship(back_populates="quality_results")

    __table_args__ = (
        Index("uq_quality_results_version_check_time", "version_id", "check_type", "computed_at", unique=True),
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(SAEnum(AnalysisStatus, name="analysis_status"), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped[DatasetVersion] = relationship(back_populates="analysis_runs")
    result: Mapped["AnalysisResult"] = relationship(back_populates="run")

    __table_args__ = (
        Index("uq_analysis_runs_version_type_fingerprint", "version_id", "analysis_type", "input_fingerprint", unique=True),
    )


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False, unique=True)
    result_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="result")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus, name="job_status"), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    version: Mapped[DatasetVersion] = relationship(back_populates="processing_jobs")

    __table_args__ = (
        Index("uq_processing_jobs_version_type_key", "version_id", "job_type", "idempotency_key", unique=True),
        Index("uq_processing_jobs_active_version_type", "version_id", "job_type", unique=True, postgresql_where=text("status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')")),
        Index("ix_processing_jobs_status_queued", "status", "queued_at"),
    )


class QueryHistory(Base):
    __tablename__ = "query_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized_query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[QueryStatus] = mapped_column(SAEnum(QueryStatus, name="query_status"), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="query_history")
    version: Mapped[DatasetVersion] = relationship(back_populates="query_history")

    __table_args__ = (
        Index("ix_query_history_user_created", "user_id", "created_at"),
        Index("ix_query_history_version_created", "version_id", "created_at"),
    )
