from __future__ import annotations

from typing import NamedTuple
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.orm import Session, selectinload

from fab_identity.domain.errors import NotFoundError
from fab_identity.domain.pagination import PageCursor
from fab_identity.infrastructure import models


class IdentityDuplicateRow(NamedTuple):
    canonical_x: int
    canonical_y: int
    physical_die_ids: list[UUID]
    source_frame_ids: list[UUID]
    observation_count: int


def _after_cursor(statement: Select, model, cursor: PageCursor | None) -> Select:
    if cursor is None:
        return statement
    return statement.where(
        or_(
            model.created_at > cursor.created_at,
            and_(model.created_at == cursor.created_at, model.id > cursor.resource_id),
        )
    )


class ReportingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def layouts(self, cursor: PageCursor | None, limit: int) -> list[models.WaferLayout]:
        statement = select(models.WaferLayout).options(selectinload(models.WaferLayout.dies))
        statement = _after_cursor(statement, models.WaferLayout, cursor)
        return list(
            self.session.scalars(
                statement.order_by(models.WaferLayout.created_at, models.WaferLayout.id).limit(
                    limit + 1
                )
            )
        )

    def frames_for_layout(self, layout_id: UUID) -> list[models.CoordinateFrame]:
        return list(
            self.session.scalars(
                select(models.CoordinateFrame)
                .where(models.CoordinateFrame.layout_id == layout_id)
                .order_by(models.CoordinateFrame.code)
            )
        )

    def reticles_for_layout(self, layout_id: UUID) -> list[models.ReticleProfile]:
        return list(
            self.session.scalars(
                select(models.ReticleProfile)
                .where(models.ReticleProfile.layout_id == layout_id)
                .options(selectinload(models.ReticleProfile.sites))
                .order_by(models.ReticleProfile.code)
            )
        )

    def wafers(
        self,
        cursor: PageCursor | None,
        limit: int,
        lot_code: str | None,
        layout_id: UUID | None,
    ) -> list[models.Wafer]:
        statement = select(models.Wafer).options(selectinload(models.Wafer.layout))
        if lot_code is not None:
            statement = statement.where(models.Wafer.lot_code == lot_code)
        if layout_id is not None:
            statement = statement.where(models.Wafer.layout_id == layout_id)
        statement = _after_cursor(statement, models.Wafer, cursor)
        return list(
            self.session.scalars(
                statement.order_by(models.Wafer.created_at, models.Wafer.id).limit(limit + 1)
            )
        )

    def batch(self, batch_id: UUID) -> models.IngestBatch:
        batch = self.session.scalar(
            select(models.IngestBatch)
            .where(models.IngestBatch.id == batch_id)
            .options(
                selectinload(models.IngestBatch.observations).selectinload(
                    models.Observation.physical_die
                )
            )
        )
        if batch is None:
            raise NotFoundError(f"ingest batch {batch_id} was not found")
        return batch

    def batches_for_wafer(
        self,
        wafer_id: UUID,
        cursor: PageCursor | None,
        limit: int,
        source_system: str | None,
        frame_id: UUID | None,
    ) -> list[models.IngestBatch]:
        statement = select(models.IngestBatch).where(models.IngestBatch.wafer_id == wafer_id)
        if source_system is not None:
            statement = statement.where(models.IngestBatch.source_system == source_system)
        if frame_id is not None:
            statement = statement.where(models.IngestBatch.frame_id == frame_id)
        statement = _after_cursor(statement, models.IngestBatch, cursor)
        return list(
            self.session.scalars(
                statement.order_by(models.IngestBatch.created_at, models.IngestBatch.id).limit(
                    limit + 1
                )
            )
        )

    def wafer_counts(self, wafer_id: UUID) -> tuple[int, int, int]:
        die_count = self.session.scalar(
            select(func.count()).select_from(models.PhysicalDie).where(
                models.PhysicalDie.wafer_id == wafer_id
            )
        )
        batch_count = self.session.scalar(
            select(func.count()).select_from(models.IngestBatch).where(
                models.IngestBatch.wafer_id == wafer_id
            )
        )
        observation_count = self.session.scalar(
            select(func.count())
            .select_from(models.Observation)
            .join(models.IngestBatch)
            .where(models.IngestBatch.wafer_id == wafer_id)
        )
        return int(die_count or 0), int(batch_count or 0), int(observation_count or 0)

    def identity_audit(
        self, wafer_id: UUID
    ) -> tuple[int, int, list[IdentityDuplicateRow]]:
        observation_counts = (
            select(
                models.Observation.physical_die_id.label("physical_die_id"),
                func.count(models.Observation.id).label("observation_count"),
            )
            .group_by(models.Observation.physical_die_id)
            .subquery()
        )
        statement = (
            select(
                models.PhysicalDie.canonical_x,
                models.PhysicalDie.canonical_y,
                func.array_agg(
                    aggregate_order_by(models.PhysicalDie.id, models.PhysicalDie.id)
                ).label("physical_die_ids"),
                func.array_agg(
                    aggregate_order_by(
                        models.PhysicalDie.source_frame_id,
                        models.PhysicalDie.source_frame_id,
                    )
                ).label("source_frame_ids"),
                func.coalesce(func.sum(observation_counts.c.observation_count), 0).label(
                    "observation_count"
                ),
            )
            .outerjoin(
                observation_counts,
                observation_counts.c.physical_die_id == models.PhysicalDie.id,
            )
            .where(models.PhysicalDie.wafer_id == wafer_id)
            .group_by(models.PhysicalDie.canonical_x, models.PhysicalDie.canonical_y)
            .order_by(models.PhysicalDie.canonical_y, models.PhysicalDie.canonical_x)
        )
        groups = list(self.session.execute(statement))
        duplicates = [
            IdentityDuplicateRow(
                canonical_x=row.canonical_x,
                canonical_y=row.canonical_y,
                physical_die_ids=list(row.physical_die_ids),
                source_frame_ids=list(row.source_frame_ids),
                observation_count=int(row.observation_count),
            )
            for row in groups
            if len(row.physical_die_ids) > 1
        ]
        return sum(len(row.physical_die_ids) for row in groups), len(groups), duplicates
