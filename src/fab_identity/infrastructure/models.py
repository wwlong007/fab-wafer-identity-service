from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WaferLayout(Base, TimestampMixin):
    __tablename__ = "wafer_layouts"
    __table_args__ = (
        CheckConstraint("max_x >= min_x", name="ck_layout_x_bounds"),
        CheckConstraint("max_y >= min_y", name="ck_layout_y_bounds"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    min_x: Mapped[int] = mapped_column(Integer, nullable=False)
    max_x: Mapped[int] = mapped_column(Integer, nullable=False)
    min_y: Mapped[int] = mapped_column(Integer, nullable=False)
    max_y: Mapped[int] = mapped_column(Integer, nullable=False)

    dies: Mapped[list[LayoutDie]] = relationship(
        back_populates="layout", cascade="all, delete-orphan", lazy="selectin"
    )
    frames: Mapped[list[CoordinateFrame]] = relationship(back_populates="layout")
    reticle_profiles: Mapped[list[ReticleProfile]] = relationship(back_populates="layout")
    wafers: Mapped[list[Wafer]] = relationship(back_populates="layout")


class LayoutDie(Base):
    __tablename__ = "layout_dies"

    layout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wafer_layouts.id", ondelete="CASCADE"), primary_key=True
    )
    canonical_x: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_y: Mapped[int] = mapped_column(Integer, primary_key=True)

    layout: Mapped[WaferLayout] = relationship(back_populates="dies")


class CoordinateFrame(Base, TimestampMixin):
    __tablename__ = "coordinate_frames"
    __table_args__ = (
        UniqueConstraint("layout_id", "code", name="uq_frame_layout_code"),
        CheckConstraint("rotation_deg IN (0, 90, 180, 270)", name="ck_frame_rotation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wafer_layouts.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_origin_x: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_origin_y: Mapped[int] = mapped_column(Integer, nullable=False)
    rotation_deg: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mirror_x: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parent_frame_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coordinate_frames.id"), nullable=True
    )
    calibration_steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    layout: Mapped[WaferLayout] = relationship(back_populates="frames")
    physical_dies: Mapped[list[PhysicalDie]] = relationship(back_populates="source_frame")
    parent: Mapped["CoordinateFrame | None"] = relationship(
        remote_side="CoordinateFrame.id", back_populates="children"
    )
    children: Mapped[list["CoordinateFrame"]] = relationship(back_populates="parent")


class ReticleProfile(Base, TimestampMixin):
    __tablename__ = "reticle_profiles"
    __table_args__ = (UniqueConstraint("layout_id", "code", name="uq_reticle_layout_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wafer_layouts.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    shot_origin_x: Mapped[int] = mapped_column(Integer, nullable=False)
    shot_origin_y: Mapped[int] = mapped_column(Integer, nullable=False)
    shot_pitch_x: Mapped[int] = mapped_column(Integer, nullable=False)
    shot_pitch_y: Mapped[int] = mapped_column(Integer, nullable=False)

    layout: Mapped[WaferLayout] = relationship(back_populates="reticle_profiles")
    sites: Mapped[list[ReticleSite]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )


class ReticleSite(Base):
    __tablename__ = "reticle_sites"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reticle_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    offset_x: Mapped[int] = mapped_column(Integer, nullable=False)
    offset_y: Mapped[int] = mapped_column(Integer, nullable=False)

    profile: Mapped[ReticleProfile] = relationship(back_populates="sites")


class Wafer(Base, TimestampMixin):
    __tablename__ = "wafers"
    __table_args__ = (UniqueConstraint("lot_code", "wafer_number", name="uq_wafer_lot_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wafer_layouts.id"), nullable=False
    )
    lot_code: Mapped[str] = mapped_column(String(80), nullable=False)
    wafer_number: Mapped[int] = mapped_column(Integer, nullable=False)

    layout: Mapped[WaferLayout] = relationship(back_populates="wafers")
    dies: Mapped[list[PhysicalDie]] = relationship(back_populates="wafer")
    batches: Mapped[list[IngestBatch]] = relationship(back_populates="wafer")


class PhysicalDie(Base, TimestampMixin):
    __tablename__ = "physical_dies"
    __table_args__ = (
        UniqueConstraint(
            "wafer_id", "source_frame_id", "source_x", "source_y", name="uq_die_source_address"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wafer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False
    )
    source_frame_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coordinate_frames.id"), nullable=False
    )
    source_x: Mapped[int] = mapped_column(Integer, nullable=False)
    source_y: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_x: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_y: Mapped[int] = mapped_column(Integer, nullable=False)
    source_catalog_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    wafer: Mapped[Wafer] = relationship(back_populates="dies")
    source_frame: Mapped[CoordinateFrame] = relationship(back_populates="physical_dies")
    observations: Mapped[list[Observation]] = relationship(back_populates="physical_die")


class IngestBatch(Base, TimestampMixin):
    __tablename__ = "ingest_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wafer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False
    )
    frame_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coordinate_frames.id"), nullable=False
    )
    reticle_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reticle_profiles.id"), nullable=True
    )
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    catalog_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    wafer: Mapped[Wafer] = relationship(back_populates="batches")
    observations: Mapped[list[Observation]] = relationship(back_populates="batch")


class Observation(Base, TimestampMixin):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("batch_id", "record_key", name="uq_observation_batch_record"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingest_batches.id", ondelete="CASCADE"), nullable=False
    )
    physical_die_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("physical_dies.id", ondelete="CASCADE"), nullable=False
    )
    record_key: Mapped[str] = mapped_column(String(120), nullable=False)
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    result: Mapped[str] = mapped_column(String(80), nullable=False)
    source_address: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    batch: Mapped[IngestBatch] = relationship(back_populates="observations")
    physical_die: Mapped[PhysicalDie] = relationship(back_populates="observations")

