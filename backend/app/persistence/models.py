"""SQLAlchemy async models for the production gateway.

These tables mirror the entities described in docs/PLAN.md: virtual_api_keys,
providers, model_routes, gateway_requests and upstream_attempts. The demo
store (app.persistence.store) is kept intact for the simulated local mode.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: "usr_" + uuid.uuid4().hex[:16])
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: "ses_" + uuid.uuid4().hex[:16])
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: "prov_" + uuid.uuid4().hex[:8])
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(64), default="openai_compatible")
    base_url: Mapped[str] = mapped_column(String(512))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    weight: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rpm_limit: Mapped[int] = mapped_column(Integer, default=120)
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=8)
    models: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of public-to-upstream model mappings
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    attempts: Mapped[list["UpstreamAttempt"]] = relationship(back_populates="provider")


class ModelRoute(Base):
    __tablename__ = "model_routes"
    __table_args__ = (
        UniqueConstraint("owner_id", "model", name="uq_model_routes_owner_model"),
        Index("uq_model_routes_global_model", "model", unique=True,
              postgresql_where=text("owner_id IS NULL")),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: "route_" + uuid.uuid4().hex[:8])
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    model: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128))
    strategy: Mapped[str] = mapped_column(String(32), default="priority_weighted")
    provider_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of provider ids
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VirtualKey(Base):
    __tablename__ = "virtual_keys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: "key_" + uuid.uuid4().hex[:8])
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    key_hash: Mapped[str] = mapped_column(String(256), unique=True)
    prefix: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="active")
    rpm_limit: Mapped[int] = mapped_column(Integer, default=60)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GatewayRequest(Base):
    __tablename__ = "gateway_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: "req_" + uuid.uuid4().hex[:8])
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="running")
    status_code: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_stream: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    attempts: Mapped[list["UpstreamAttempt"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class UpstreamAttempt(Base):
    __tablename__ = "upstream_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: "att_" + uuid.uuid4().hex[:8])
    request_id: Mapped[str] = mapped_column(ForeignKey("gateway_requests.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("providers.id", ondelete="SET NULL"), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    request: Mapped["GatewayRequest"] = relationship(back_populates="attempts")
    provider: Mapped["Provider"] = relationship(back_populates="attempts")
