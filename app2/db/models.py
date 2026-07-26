from app2.db.base import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB


# =====================================================
# Firewall Daily Usage
# =====================================================
class FirewallDailyUsage(Base):
    __tablename__ = "firewall_daily_usage"

    day = Column(Date, primary_key=True, index=True)
    used_units = Column(Integer, default=0, nullable=False)
    daily_limit = Column(Integer, default=1000, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# =====================================================
# Retrieval Logs
# =====================================================
class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Request Identity
    request_id = Column(String(64), nullable=False, unique=True, index=True)
    session_id = Column(String(128), nullable=True, index=True)
    user_id = Column(String(128), nullable=True, index=True)

    # Query
    query_raw = Column(Text, nullable=False)
    query_normalized = Column(Text, nullable=False)
    query_hash = Column(String(64), nullable=False, index=True)
    query_length = Column(Integer, nullable=False, default=0)
    token_count = Column(Integer, nullable=False, default=0)
    char_count = Column(Integer, nullable=False, default=0)
    language = Column(String(16), nullable=True)

    # Firewall
    blocked = Column(Boolean, nullable=False, default=False, index=True)
    block_reason = Column(String(128), nullable=True)
    firewall_allowed = Column(Boolean, nullable=True)
    firewall_reason = Column(String(128), nullable=True)
    firewall_signals = Column(JSONB, nullable=True)
    query_validation_score = Column(Float, nullable=True)

    # Semantic
    semantic_best_field = Column(String(64), nullable=True)
    semantic_best_score = Column(Float, nullable=True)
    semantic = Column(JSONB, nullable=True)

    # Routing & Retrieval
    filters = Column(JSONB, nullable=True)
    mode = Column(String(32), nullable=True, index=True)
    route_reason = Column(String(128), nullable=True)

    retrieval_quality = Column(JSONB, nullable=True)
    retrieval_quality_score = Column(Float, nullable=True, index=True)
    candidate_count = Column(Integer, nullable=True)
    bm25_used = Column(Boolean, nullable=True)
    retry_triggered = Column(Boolean, nullable=True)
    attempt_count = Column(Integer, nullable=True)
    attempt_history = Column(JSONB, nullable=True)
    fallback_used = Column(Boolean, nullable=True)

    # Result
    result_count = Column(Integer, nullable=True)
    top_result_id = Column(BigInteger, nullable=True, index=True)
    top_result_score = Column(Float, nullable=True)
    top_results = Column(JSONB, nullable=True)

    # Latency
    latency_total_ms = Column(Float, nullable=True)
    latency_firewall_ms = Column(Float, nullable=True)
    latency_preprocess_ms = Column(Float, nullable=True)
    latency_metadata_ms = Column(Float, nullable=True)
    latency_semantic_ms = Column(Float, nullable=True)
    latency_embedding_ms = Column(Float, nullable=True)
    latency_candidate_ms = Column(Float, nullable=True)
    latency_retrieval_ms = Column(Float, nullable=True)
    latency_ranking_ms = Column(Float, nullable=True)
    latency_alignment_ms = Column(Float, nullable=True)

    # Cost & Cache
    cost_allowed = Column(Boolean, nullable=True)
    cost_reason = Column(String(128), nullable=True)
    cost_units = Column(Float, nullable=True)
    used_today = Column(Integer, nullable=True)
    daily_limit = Column(Integer, nullable=True)
    estimated_input_tokens = Column(Integer, nullable=True)
    estimated_output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, nullable=False, default=False, index=True)
    cache_layer = Column(String(32), nullable=True)

    # Misc
    extra = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_retrieval_logs_created_mode", "created_at", "mode"),
        Index("ix_retrieval_logs_created_blocked", "created_at", "blocked"),
        Index("ix_retrieval_logs_cache", "cache_hit", "created_at"),
    )


# =====================================================
# Product Captions
# =====================================================
class ProductCaption(Base):
    __tablename__ = "product_captions"

    id = Column(BigInteger, primary_key=True, index=True)
    product_id = Column(BigInteger, nullable=False, index=True)
    caption_text = Column(Text, nullable=False)
    caption_type = Column(String(50), nullable=False, index=True)
    occasion_category = Column(String(100), nullable=True, index=True)
    priority = Column(Integer, default=1)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_pc_product_active", "product_id", "is_active"),
    )


# =====================================================
# Main Product Table (مهم‌ترین مدل)
# =====================================================
class AsanClipProduct(Base):
    __tablename__ = "asanclipproducts"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    short_description = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    rag_text = Column(Text, nullable=True)

    product_type = Column(Text, nullable=True)
    occasion = Column(Text, nullable=True)
    platform = Column(Text, nullable=True)

    embedding_vector = Column(Vector(3072), nullable=True)

    tag_status = Column(Text, default="done")
    url = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
