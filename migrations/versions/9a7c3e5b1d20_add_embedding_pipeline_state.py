"""add embedding pipeline state

Revision ID: 9a7c3e5b1d20
Revises: e3fe5fcf3e90
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a7c3e5b1d20"
down_revision: str | Sequence[str] | None = "e3fe5fcf3e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE asanclipproducts
        SET tag_status = 'done'
        WHERE tag_status IS NULL
        """
    )
    op.alter_column(
        "asanclipproducts",
        "tag_status",
        server_default=sa.text("'done'"),
    )
    op.add_column("asanclipproducts", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column(
        "asanclipproducts",
        sa.Column(
            "embedding_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.add_column("asanclipproducts", sa.Column("embedding_model", sa.String(128), nullable=True))
    op.add_column(
        "asanclipproducts",
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "asanclipproducts",
        sa.Column("embedding_claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "asanclipproducts",
        sa.Column("embedding_claim_token", sa.String(64), nullable=True),
    )
    op.add_column(
        "asanclipproducts",
        sa.Column(
            "embedding_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column("asanclipproducts", sa.Column("embedding_error", sa.Text(), nullable=True))
    op.add_column("asanclipproducts", sa.Column("ingestion_run_id", sa.String(64), nullable=True))
    op.execute(
        """
        UPDATE asanclipproducts
        SET embedding_status = CASE
            WHEN embedding_vector IS NULL THEN 'pending'
            ELSE 'done'
        END
        """
    )
    op.create_index(
        "ix_asanclipproducts_content_hash",
        "asanclipproducts",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_asanclipproducts_ingestion_run_id",
        "asanclipproducts",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_asanclipproducts_embedding_queue",
        "asanclipproducts",
        ["embedding_status", "embedding_claimed_at"],
        unique=False,
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION invalidate_product_embedding()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.embedding_vector IS NULL THEN
                    NEW.embedding_status := 'pending';
                END IF;
            ELSIF ROW(
                OLD.name,
                OLD.short_description,
                OLD.description,
                OLD.product_type,
                OLD.occasion,
                OLD.platform
            ) IS DISTINCT FROM ROW(
                NEW.name,
                NEW.short_description,
                NEW.description,
                NEW.product_type,
                NEW.occasion,
                NEW.platform
            ) THEN
                NEW.embedding_vector := NULL;
                NEW.content_hash := NULL;
                NEW.embedding_model := NULL;
                NEW.embedding_updated_at := NULL;
                NEW.embedding_claimed_at := NULL;
                NEW.embedding_claim_token := NULL;
                NEW.embedding_attempts := 0;
                NEW.embedding_error := NULL;
                NEW.embedding_status := 'pending';
            END IF;
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_invalidate_product_embedding
        BEFORE INSERT OR UPDATE ON asanclipproducts
        FOR EACH ROW
        EXECUTE FUNCTION invalidate_product_embedding()
        """
    )
    # pgvector's vector HNSW operator class is limited to 2,000 dimensions.
    # halfvec supports 3,072 dimensions and is used by the fallback query.
    op.execute(
        """
        CREATE INDEX ix_asanclipproducts_embedding_hnsw
        ON asanclipproducts
        USING hnsw ((CAST(embedding_vector AS halfvec(3072))) halfvec_cosine_ops)
        WHERE embedding_vector IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_asanclipproducts_embedding_hnsw")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_invalidate_product_embedding ON asanclipproducts"
    )
    op.execute("DROP FUNCTION IF EXISTS invalidate_product_embedding()")
    op.drop_index("ix_asanclipproducts_embedding_queue", table_name="asanclipproducts")
    op.drop_index("ix_asanclipproducts_ingestion_run_id", table_name="asanclipproducts")
    op.drop_index("ix_asanclipproducts_content_hash", table_name="asanclipproducts")
    op.drop_column("asanclipproducts", "ingestion_run_id")
    op.drop_column("asanclipproducts", "embedding_error")
    op.drop_column("asanclipproducts", "embedding_attempts")
    op.drop_column("asanclipproducts", "embedding_claim_token")
    op.drop_column("asanclipproducts", "embedding_claimed_at")
    op.drop_column("asanclipproducts", "embedding_updated_at")
    op.drop_column("asanclipproducts", "embedding_model")
    op.drop_column("asanclipproducts", "embedding_status")
    op.drop_column("asanclipproducts", "content_hash")
    op.alter_column(
        "asanclipproducts",
        "tag_status",
        server_default=sa.text("'done'"),
    )
