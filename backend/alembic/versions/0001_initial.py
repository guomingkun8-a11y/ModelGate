"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False, server_default="openai_compatible"),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rpm_limit", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("models", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "model_routes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("model", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("strategy", sa.String(32), nullable=False, server_default="priority_weighted"),
        sa.Column("provider_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "virtual_keys",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("key_hash", sa.String(256), nullable=False, unique=True),
        sa.Column("prefix", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("rpm_limit", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "gateway_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("key_id", sa.String(64), nullable=True),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(128), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("is_stream", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_gateway_requests_created_at", "gateway_requests", ["created_at"])
    op.create_index("ix_gateway_requests_model", "gateway_requests", ["model"])

    op.create_table(
        "upstream_attempts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("provider_id", sa.String(64), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["gateway_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_upstream_attempts_request_id", "upstream_attempts", ["request_id"])


def downgrade() -> None:
    op.drop_table("upstream_attempts")
    op.drop_table("gateway_requests")
    op.drop_table("virtual_keys")
    op.drop_table("model_routes")
    op.drop_table("providers")
