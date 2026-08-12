from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fab_identity.domain.coordinates import Point
from fab_identity.domain.errors import NotFoundError
from fab_identity.infrastructure import models


class DieRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_source(
        self, wafer_id: UUID, frame_id: UUID, source: Point
    ) -> models.PhysicalDie | None:
        return self.session.scalar(
            select(models.PhysicalDie).where(
                models.PhysicalDie.wafer_id == wafer_id,
                models.PhysicalDie.source_frame_id == frame_id,
                models.PhysicalDie.source_x == source.x,
                models.PhysicalDie.source_y == source.y,
            )
        )

    def get_or_create_source(
        self, wafer_id: UUID, frame_id: UUID, source: Point, canonical: Point
    ) -> models.PhysicalDie:
        die = self.find_source(wafer_id, frame_id, source)
        if die is not None:
            return die
        die = models.PhysicalDie(
            wafer_id=wafer_id,
            source_frame_id=frame_id,
            source_x=source.x,
            source_y=source.y,
            canonical_x=canonical.x,
            canonical_y=canonical.y,
        )
        self.session.add(die)
        self.session.flush()
        return die

    def by_canonical(self, wafer_id: UUID, canonical: Point) -> models.PhysicalDie:
        dies = list(
            self.session.scalars(
                select(models.PhysicalDie)
                .where(
                    models.PhysicalDie.wafer_id == wafer_id,
                    models.PhysicalDie.canonical_x == canonical.x,
                    models.PhysicalDie.canonical_y == canonical.y,
                )
                .options(selectinload(models.PhysicalDie.observations))
                .order_by(models.PhysicalDie.created_at, models.PhysicalDie.id)
            )
        )
        if not dies:
            raise NotFoundError(
                f"die ({canonical.x}, {canonical.y}) on wafer {wafer_id} was not found"
            )
        return dies[0]

    def for_wafer(self, wafer_id: UUID) -> list[models.PhysicalDie]:
        return list(
            self.session.scalars(
                select(models.PhysicalDie)
                .where(models.PhysicalDie.wafer_id == wafer_id)
                .order_by(models.PhysicalDie.canonical_y, models.PhysicalDie.canonical_x)
            )
        )

