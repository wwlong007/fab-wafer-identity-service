from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from fab_identity.api import schemas
from fab_identity.domain.pagination import PageCursor, next_cursor
from fab_identity.repositories.catalog import CatalogRepository
from fab_identity.repositories.reporting import ReportingRepository


class ReportingService:
    def __init__(self, session: Session) -> None:
        self.catalog = CatalogRepository(session)
        self.reporting = ReportingRepository(session)

    def layout(self, layout_id: UUID) -> schemas.LayoutDetail:
        layout = self.catalog.layout(layout_id)
        frames = self.reporting.frames_for_layout(layout_id)
        reticles = self.reporting.reticles_for_layout(layout_id)
        return schemas.LayoutDetail(
            id=layout.id,
            code=layout.code,
            min_x=layout.min_x,
            max_x=layout.max_x,
            min_y=layout.min_y,
            max_y=layout.max_y,
            valid_dies=[
                schemas.DieCoordinate(x=die.canonical_x, y=die.canonical_y)
                for die in sorted(layout.dies, key=lambda item: (item.canonical_y, item.canonical_x))
            ],
            frames=[self._frame(frame) for frame in frames],
            reticles=[self._reticle(profile) for profile in reticles],
        )

    def layouts(self, cursor: str | None, limit: int) -> schemas.LayoutPage:
        rows = self.reporting.layouts(PageCursor.decode(cursor), limit)
        return schemas.LayoutPage(
            items=[
                schemas.LayoutView(
                    id=row.id,
                    code=row.code,
                    min_x=row.min_x,
                    max_x=row.max_x,
                    min_y=row.min_y,
                    max_y=row.max_y,
                    valid_die_count=len(row.dies),
                )
                for row in rows[:limit]
            ],
            next_cursor=next_cursor(rows, limit),
        )

    def frame(self, frame_id: UUID) -> schemas.FrameView:
        return self._frame(self.catalog.frame(frame_id))

    def reticle(self, profile_id: UUID) -> schemas.ReticleView:
        return self._reticle(self.catalog.reticle(profile_id))

    def wafer(self, wafer_id: UUID) -> schemas.WaferDetail:
        wafer = self.catalog.wafer(wafer_id)
        die_count, batch_count, observation_count = self.reporting.wafer_counts(wafer_id)
        return schemas.WaferDetail(
            id=wafer.id,
            layout_id=wafer.layout_id,
            layout_code=wafer.layout.code,
            lot_code=wafer.lot_code,
            wafer_number=wafer.wafer_number,
            physical_die_count=die_count,
            ingest_batch_count=batch_count,
            observation_count=observation_count,
            created_at=wafer.created_at,
        )

    def identity_audit(self, wafer_id: UUID) -> schemas.IdentityAuditView:
        self.catalog.wafer(wafer_id)
        die_count, identity_count, duplicates = self.reporting.identity_audit(wafer_id)
        return schemas.IdentityAuditView(
            wafer_id=wafer_id,
            physical_die_count=die_count,
            canonical_identity_count=identity_count,
            duplicate_identity_count=sum(len(group.physical_die_ids) - 1 for group in duplicates),
            affected_observation_count=sum(group.observation_count for group in duplicates),
            duplicate_groups=[
                schemas.IdentityDuplicateGroup(
                    canonical_x=group.canonical_x,
                    canonical_y=group.canonical_y,
                    physical_die_ids=group.physical_die_ids,
                    source_frame_ids=group.source_frame_ids,
                    observation_count=group.observation_count,
                )
                for group in duplicates
            ],
            scanned_at=datetime.now(timezone.utc),
        )

    def wafers(
        self,
        cursor: str | None,
        limit: int,
        lot_code: str | None,
        layout_id: UUID | None,
    ) -> schemas.WaferPage:
        rows = self.reporting.wafers(PageCursor.decode(cursor), limit, lot_code, layout_id)
        return schemas.WaferPage(
            items=[
                schemas.WaferSummary(
                    id=row.id,
                    layout_id=row.layout_id,
                    layout_code=row.layout.code,
                    lot_code=row.lot_code,
                    wafer_number=row.wafer_number,
                    created_at=row.created_at,
                )
                for row in rows[:limit]
            ],
            next_cursor=next_cursor(rows, limit),
        )

    def batch(self, batch_id: UUID) -> schemas.BatchDetail:
        batch = self.reporting.batch(batch_id)
        return schemas.BatchDetail(
            id=batch.id,
            wafer_id=batch.wafer_id,
            frame_id=batch.frame_id,
            reticle_profile_id=batch.reticle_profile_id,
            source_system=batch.source_system,
            record_count=batch.record_count,
            created_at=batch.created_at,
            observations=[
                schemas.BatchObservation(
                    id=item.id,
                    physical_die_id=item.physical_die_id,
                    canonical_x=item.physical_die.canonical_x,
                    canonical_y=item.physical_die.canonical_y,
                    record_key=item.record_key,
                    stage=item.stage,
                    result=item.result,
                    source_address=item.source_address,
                    measured_at=item.measured_at,
                    attributes=item.attributes,
                )
                for item in sorted(batch.observations, key=lambda row: (row.measured_at, row.id))
            ],
        )

    def batches(
        self,
        wafer_id: UUID,
        cursor: str | None,
        limit: int,
        source_system: str | None,
        frame_id: UUID | None,
    ) -> schemas.BatchPage:
        self.catalog.wafer(wafer_id)
        rows = self.reporting.batches_for_wafer(
            wafer_id, PageCursor.decode(cursor), limit, source_system, frame_id
        )
        return schemas.BatchPage(
            items=[
                schemas.BatchSummary(
                    id=row.id,
                    wafer_id=row.wafer_id,
                    frame_id=row.frame_id,
                    reticle_profile_id=row.reticle_profile_id,
                    source_system=row.source_system,
                    record_count=row.record_count,
                    created_at=row.created_at,
                )
                for row in rows[:limit]
            ],
            next_cursor=next_cursor(rows, limit),
        )

    @staticmethod
    def _frame(frame) -> schemas.FrameView:
        return schemas.FrameView(
            id=frame.id,
            layout_id=frame.layout_id,
            code=frame.code,
            raw_origin_x=frame.raw_origin_x,
            raw_origin_y=frame.raw_origin_y,
            rotation_deg=frame.rotation_deg,
            mirror_x=frame.mirror_x,
        )

    @staticmethod
    def _reticle(profile) -> schemas.ReticleView:
        return schemas.ReticleView(
            id=profile.id,
            layout_id=profile.layout_id,
            code=profile.code,
            shot_origin_x=profile.shot_origin_x,
            shot_origin_y=profile.shot_origin_y,
            shot_pitch_x=profile.shot_pitch_x,
            shot_pitch_y=profile.shot_pitch_y,
            sites=[
                schemas.ReticleSiteCreate(
                    code=site.code, offset_x=site.offset_x, offset_y=site.offset_y
                )
                for site in sorted(profile.sites, key=lambda item: item.code)
            ],
        )
