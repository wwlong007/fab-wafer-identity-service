"""initial wafer identity schema

Revision ID: 0001
Revises:
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wafer_layouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("min_x", sa.Integer(), nullable=False),
        sa.Column("max_x", sa.Integer(), nullable=False),
        sa.Column("min_y", sa.Integer(), nullable=False),
        sa.Column("max_y", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("max_x >= min_x", name="ck_layout_x_bounds"),
        sa.CheckConstraint("max_y >= min_y", name="ck_layout_y_bounds"),
    )
    op.create_table(
        "layout_dies",
        sa.Column("layout_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wafer_layouts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("canonical_x", sa.Integer(), primary_key=True),
        sa.Column("canonical_y", sa.Integer(), primary_key=True),
    )
    op.create_table(
        "coordinate_frames",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("layout_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wafer_layouts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("raw_origin_x", sa.Integer(), nullable=False),
        sa.Column("raw_origin_y", sa.Integer(), nullable=False),
        sa.Column("rotation_deg", sa.Integer(), nullable=False),
        sa.Column("mirror_x", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("layout_id", "code", name="uq_frame_layout_code"),
        sa.CheckConstraint("rotation_deg IN (0, 90, 180, 270)", name="ck_frame_rotation"),
    )
    op.create_table(
        "reticle_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("layout_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wafer_layouts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("shot_origin_x", sa.Integer(), nullable=False),
        sa.Column("shot_origin_y", sa.Integer(), nullable=False),
        sa.Column("shot_pitch_x", sa.Integer(), nullable=False),
        sa.Column("shot_pitch_y", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("layout_id", "code", name="uq_reticle_layout_code"),
    )
    op.create_table(
        "reticle_sites",
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reticle_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("code", sa.String(80), primary_key=True),
        sa.Column("offset_x", sa.Integer(), nullable=False),
        sa.Column("offset_y", sa.Integer(), nullable=False),
    )
    op.create_table(
        "wafers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("layout_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wafer_layouts.id"), nullable=False),
        sa.Column("lot_code", sa.String(80), nullable=False),
        sa.Column("wafer_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("lot_code", "wafer_number", name="uq_wafer_lot_number"),
    )
    op.create_table(
        "physical_dies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wafer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_frame_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("coordinate_frames.id"), nullable=False),
        sa.Column("source_x", sa.Integer(), nullable=False),
        sa.Column("source_y", sa.Integer(), nullable=False),
        sa.Column("canonical_x", sa.Integer(), nullable=False),
        sa.Column("canonical_y", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("wafer_id", "source_frame_id", "source_x", "source_y", name="uq_die_source_address"),
    )
    op.create_table(
        "ingest_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wafer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("frame_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("coordinate_frames.id"), nullable=False),
        sa.Column("reticle_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reticle_profiles.id"), nullable=True),
        sa.Column("source_system", sa.String(120), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingest_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("physical_die_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("physical_dies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_key", sa.String(120), nullable=False),
        sa.Column("stage", sa.String(80), nullable=False),
        sa.Column("result", sa.String(80), nullable=False),
        sa.Column("source_address", sa.JSON(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("batch_id", "record_key", name="uq_observation_batch_record"),
    )


def downgrade() -> None:
    for table in ["observations", "ingest_batches", "physical_dies", "wafers", "reticle_sites", "reticle_profiles", "coordinate_frames", "layout_dies", "wafer_layouts"]:
        op.drop_table(table)

