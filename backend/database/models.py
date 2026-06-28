from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, TIMESTAMP, JSON, inspect, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func
import uuid

from config import settings

# ── Engine & Session ──────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# ── Dependency: get DB session ────────────────────────────
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Models ────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), index=True, nullable=True) # UUID from Supabase Auth
    name = Column(String(255), nullable=False)
    business_description = Column(Text, nullable=False)
    status = Column(String(50), default="draft")       # draft, active, paused, archived
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class ICPConfiguration(Base):
    __tablename__ = "icp_configurations"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(PG_UUID(as_uuid=True), nullable=False)
    version = Column(Integer, default=1)
    industry = Column(JSON)
    company_size = Column(JSON)
    revenue_range = Column(JSON)
    geography = Column(JSON)
    employee_count_min = Column(Integer)
    employee_count_max = Column(Integer)
    personas = Column(JSON)
    triggers = Column(JSON)
    qualification_rules = Column(JSON)
    disqualifiers = Column(JSON)
    constraints = Column(JSON)
    confidence_indicator = Column(Float)
    target_market_description = Column(Text)
    product_or_service = Column(Text)
    value_proposition = Column(Text)
    confidence_notes = Column(Text)
    confirmed_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), index=True, nullable=True) # UUID from Supabase Auth
    project_id = Column(PG_UUID(as_uuid=True), nullable=False)
    icp_config_id = Column(PG_UUID(as_uuid=True))
    status = Column(String(50), default="pending")     # pending, running, paused_hitl, completed, failed
    planner_strategy = Column(JSON)
    agent_execution_log = Column(JSON)
    started_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))
    total_cost_estimate = Column(Float, default=0.0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Company(Base):
    __tablename__ = "companies"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_run_id = Column(PG_UUID(as_uuid=True), nullable=False)
    name = Column(String(255))
    domain = Column(String(255))
    website = Column(String(500))
    industry = Column(String(255))
    employee_count = Column(Integer)
    revenue_estimate = Column(String(100))
    headquarters = Column(String(255))
    funding_total = Column(String(100))
    recent_funding = Column(JSON)
    tech_stack = Column(JSON)
    hiring_trends = Column(JSON)
    growth_signals = Column(JSON)
    recent_news = Column(JSON)
    social_presence = Column(JSON)
    confidence_score = Column(Float)
    validation_status = Column(String(50), default="pending")  # pending, validated, rejected, duplicate
    icp_match_score = Column(Float)
    trigger_reason = Column(String(255))
    status = Column(String(50), default="discovered")
    enriched_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(PG_UUID(as_uuid=True), nullable=False)
    full_name = Column(String(255))
    designation = Column(String(255))
    department = Column(String(255))
    email = Column(String(255))
    email_confidence = Column(Float)
    phone = Column(String(100))
    linkedin_url = Column(String(500))
    confidence_score = Column(Float)
    source = Column(String(255))
    is_unavailable_email = Column(Boolean, default=False)
    is_unavailable_phone = Column(Boolean, default=False)
    is_unavailable_linkedin = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class BusinessBrief(Base):
    __tablename__ = "business_briefs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), index=True, nullable=True) # UUID from Supabase Auth
    workflow_run_id = Column(PG_UUID(as_uuid=True), nullable=False)
    company_id = Column(PG_UUID(as_uuid=True), nullable=False)
    company_name = Column(String(255))
    company_domain = Column(String(255))
    company_summary = Column(Text)
    trigger_summary = Column(Text)
    qualification_summary = Column(Text)
    company_insights = Column(JSON)
    decision_makers = Column(JSON)
    next_best_actions = Column(JSON)
    talking_points = Column(JSON)
    risk_factors = Column(JSON)
    priority_score = Column(Float)
    recommended_contact_id = Column(PG_UUID(as_uuid=True))
    recommended_channel = Column(String(100))
    recommended_timing = Column(String(255))
    overall_confidence = Column(Float)
    sources = Column(JSON)
    hitl_status = Column(String(50), default="pending_review")  # pending_review, approved, rejected, pending_research
    version = Column(Integer, default=1)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class HumanFeedback(Base):
    __tablename__ = "human_feedback"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brief_id = Column(PG_UUID(as_uuid=True), nullable=False)
    project_id = Column(PG_UUID(as_uuid=True), nullable=False)
    action = Column(String(100))   # approve, reject, modify, change_personas, update_icp, request_research
    feedback_data = Column(JSON)
    outcome = Column(JSON)
    recorded_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(PG_UUID(as_uuid=True))
    workflow_run_id = Column(PG_UUID(as_uuid=True))
    event_type = Column(String(100))      # agent_success, agent_failure, hitl_triggered, dedup_avoided
    agent_name = Column(String(100))
    capability_used = Column(String(100))
    model_used = Column(String(100))
    duration_ms = Column(Integer)
    tokens_used = Column(Integer)
    cost_estimate = Column(Float)
    event_metadata = Column("metadata", JSON)   # "metadata" is reserved by SQLAlchemy — use alias
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


# ── Create all tables ─────────────────────────────────────
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_icp_context_columns(conn)


async def _ensure_icp_context_columns(conn):
    """Backfill optional ICP context columns for existing databases."""
    existing_columns = await conn.run_sync(
        lambda sync_conn: {
            col["name"]
            for col in inspect(sync_conn).get_columns("icp_configurations")
        }
    )

    missing_columns = {
        "target_market_description": "TEXT",
        "product_or_service": "TEXT",
        "value_proposition": "TEXT",
        "confidence_notes": "TEXT",
    }

    for column_name, column_type in missing_columns.items():
        if column_name in existing_columns:
            continue
        await conn.execute(
            text(
                f"ALTER TABLE icp_configurations "
                f"ADD COLUMN {column_name} {column_type}"
            )
        )
