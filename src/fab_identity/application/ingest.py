from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fab_identity.api import schemas
from fab_identity.domain.coordinates import (
    Bounds,
    FrameDefinition,
    Point,
    flatten_shot_site,
    normalize_observed,
)
from fab_identity.domain.errors import ConflictError, ValidationError
from fab_identity.infrastructure import models
from fab_identity.repositories.catalog import CatalogRepository
from fab_identity.repositories.dies import DieRepository


@dataclass(frozen=True, slots=True)
class PreparedObservation:
    request: schemas.ObservationInput
    raw: Point


class IngestService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog = CatalogRepository(session)
        self.dies = DieRepository(session)

    def ingest(self, wafer_id, request: schemas.BatchIngest) -> schemas.BatchView:
        wafer = self.catalog.wafer(wafer_id)
        frame = self.catalog.frame(request.frame_id)
        if frame.layout_id != wafer.layout_id:
            raise ValidationError("coordinate frame does not belong to wafer layout")

        reticle = None
        if request.reticle_profile_id is not None:
            reticle = self.catalog.reticle(request.reticle_profile_id)
            if reticle.layout_id != wafer.layout_id:
                raise ValidationError("reticle profile does not belong to wafer layout")

        prepared = [self._prepare(item, reticle) for item in request.observations]
        observed = Bounds.enclosing([item.raw for item in prepared])
        frame_definition = FrameDefinition(
            raw_origin=Point(frame.raw_origin_x, frame.raw_origin_y),
            rotation_deg=frame.rotation_deg,
            mirror_x=frame.mirror_x,
        )

        batch = models.IngestBatch(
            wafer_id=wafer.id,
            frame_id=frame.id,
            reticle_profile_id=request.reticle_profile_id,
            source_system=request.source_system,
            record_count=len(prepared),
            # Public baseline stores only provenance identifiers. The task
            # requires the complete immutable effective catalog.
            catalog_snapshot={
                "layout_id": str(wafer.layout_id),
                "frame_id": str(frame.id),
                "reticle_profile_id": (
                    str(request.reticle_profile_id)
                    if request.reticle_profile_id is not None
                    else None
                ),
            },
        )
        self.session.add(batch)
        accepted: list[schemas.AcceptedObservation] = []
        valid_mask = {(die.canonical_x, die.canonical_y) for die in wafer.layout.dies}

        try:
            self.session.flush()
            for item in prepared:
                canonical = normalize_observed(item.raw, frame_definition, observed)
                if (canonical.x, canonical.y) not in valid_mask:
                    raise ValidationError(
                        f"record {item.request.record_key} maps outside the valid die mask"
                    )
                die = self.dies.get_or_create_source(
                    wafer.id, frame.id, item.raw, canonical
                )
                observation = models.Observation(
                    batch_id=batch.id,
                    physical_die_id=die.id,
                    record_key=item.request.record_key,
                    stage=item.request.stage,
                    result=item.request.result,
                    source_address=item.request.address.model_dump(),
                    measured_at=item.request.measured_at,
                    attributes=item.request.attributes,
                )
                self.session.add(observation)
                self.session.flush()
                accepted.append(
                    schemas.AcceptedObservation(
                        observation_id=observation.id,
                        physical_die_id=die.id,
                        record_key=item.request.record_key,
                        canonical_x=canonical.x,
                        canonical_y=canonical.y,
                    )
                )
            self.session.commit()
        except (ValidationError, IntegrityError) as exc:
            self.session.rollback()
            if isinstance(exc, ValidationError):
                raise
            raise ConflictError("batch contains duplicate record or source addresses") from exc

        return schemas.BatchView(batch_id=batch.id, wafer_id=wafer.id, accepted=accepted)

    @staticmethod
    def _prepare(
        item: schemas.ObservationInput, reticle: models.ReticleProfile | None
    ) -> PreparedObservation:
        if isinstance(item.address, schemas.GridAddress):
            return PreparedObservation(item, Point(item.address.x, item.address.y))
        if reticle is None:
            raise ValidationError("shot_site address requires a reticle profile")
        site = next((site for site in reticle.sites if site.code == item.address.site_code), None)
        if site is None:
            raise ValidationError(f"reticle site {item.address.site_code} was not found")
        raw = flatten_shot_site(
            item.address.shot_col,
            item.address.shot_row,
            Point(reticle.shot_origin_x, reticle.shot_origin_y),
            Point(reticle.shot_pitch_x, reticle.shot_pitch_y),
            Point(site.offset_x, site.offset_y),
        )
        return PreparedObservation(item, raw)

