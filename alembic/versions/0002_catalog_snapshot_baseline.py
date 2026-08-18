"""add the public catalog snapshot provenance fields

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ingest_batches",
        sa.Column("catalog_snapshot", sa.JSON(), nullable=True),
    )
    op.add_column(
        "physical_dies",
        sa.Column("source_catalog_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("physical_dies", "source_catalog_snapshot")
    op.drop_column("ingest_batches", "catalog_snapshot")
