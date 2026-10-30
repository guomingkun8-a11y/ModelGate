"""Allow each account to manage its own upstreams and model routes."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_user_owned_upstreams"
down_revision = "0002_accounts_and_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("owner_id", sa.String(64), nullable=True))
    op.create_index("ix_providers_owner_id", "providers", ["owner_id"])
    op.create_foreign_key(
        "fk_providers_owner_id_users", "providers", "users", ["owner_id"], ["id"],
        ondelete="CASCADE",
    )

    op.add_column("model_routes", sa.Column("owner_id", sa.String(64), nullable=True))
    op.create_index("ix_model_routes_owner_id", "model_routes", ["owner_id"])
    op.create_foreign_key(
        "fk_model_routes_owner_id_users", "model_routes", "users", ["owner_id"], ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("model_routes_model_key", "model_routes", type_="unique")
    op.create_unique_constraint(
        "uq_model_routes_owner_model", "model_routes", ["owner_id", "model"],
    )
    op.create_index(
        "uq_model_routes_global_model", "model_routes", ["model"], unique=True,
        postgresql_where=sa.text("owner_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_model_routes_global_model", table_name="model_routes")
    op.drop_constraint("uq_model_routes_owner_model", "model_routes", type_="unique")
    op.create_unique_constraint("model_routes_model_key", "model_routes", ["model"])
    op.drop_constraint("fk_model_routes_owner_id_users", "model_routes", type_="foreignkey")
    op.drop_index("ix_model_routes_owner_id", table_name="model_routes")
    op.drop_column("model_routes", "owner_id")

    op.drop_constraint("fk_providers_owner_id_users", "providers", type_="foreignkey")
    op.drop_index("ix_providers_owner_id", table_name="providers")
    op.drop_column("providers", "owner_id")
