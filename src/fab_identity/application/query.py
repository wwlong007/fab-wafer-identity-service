from sqlalchemy.orm import Session

from fab_identity.api import schemas
from fab_identity.domain.coordinates import Bounds, Point, chain_transform
from fab_identity.domain.errors import ValidationError
from fab_identity.repositories.catalog import CatalogRepository
from fab_identity.repositories.dies import DieRepository


class QueryService:
    def __init__(self, session: Session) -> None:
        self.catalog = CatalogRepository(session)
        self.dies = DieRepository(session)

    def die(self, wafer_id, x: int, y: int) -> schemas.DieView:
        self.catalog.wafer(wafer_id)
        die = self.dies.by_canonical(wafer_id, Point(x, y))
        return schemas.DieView(
            id=die.id,
            wafer_id=die.wafer_id,
            canonical_x=die.canonical_x,
            canonical_y=die.canonical_y,
            observations=[
                schemas.ObservationView(
                    id=item.id,
                    batch_id=item.batch_id,
                    record_key=item.record_key,
                    stage=item.stage,
                    result=item.result,
                    measured_at=item.measured_at,
                    source_address=item.source_address,
                    attributes=item.attributes,
                )
                for item in sorted(die.observations, key=lambda row: (row.measured_at, row.id))
            ],
        )

    def export(self, wafer_id, frame_id) -> schemas.ExportView:
        wafer = self.catalog.wafer(wafer_id)
        frame = self.catalog.frame(frame_id)
        if frame.layout_id != wafer.layout_id:
            raise ValidationError("coordinate frame does not belong to wafer layout")
        geometry = Bounds(
            wafer.layout.min_x,
            wafer.layout.max_x,
            wafer.layout.min_y,
            wafer.layout.max_y,
        )
        frames = []
        current = frame
        seen = set()
        while current is not None:
            if current.id in seen:
                raise ValidationError("coordinate frame parent cycle")
            seen.add(current.id)
            frames.append(current)
            current = self.catalog.frame(current.parent_frame_id) if current.parent_frame_id else None
        transform = chain_transform(geometry, list(reversed(frames)))
        dies = self.dies.for_wafer(wafer.id)
        if dies:
            observed = Bounds.enclosing(
                [Point(die.canonical_x, die.canonical_y) for die in dies]
            )
        else:
            observed = Bounds(
                wafer.layout.min_x,
                wafer.layout.max_x,
                wafer.layout.min_y,
                wafer.layout.max_y,
            )
        records = []
        for die in dies:
            canonical = Point(die.canonical_x, die.canonical_y)
            raw = transform.apply(canonical)
            records.append(
                schemas.ExportRecord(
                    physical_die_id=die.id,
                    canonical_x=canonical.x,
                    canonical_y=canonical.y,
                    raw_x=raw.x,
                    raw_y=raw.y,
                )
            )
        return schemas.ExportView(wafer_id=wafer.id, frame_id=frame.id, records=records)

