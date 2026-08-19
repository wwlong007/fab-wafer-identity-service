from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DieCoordinate(ApiModel):
    x: int
    y: int


class LayoutCreate(ApiModel):
    code: str = Field(min_length=1, max_length=80)
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    valid_dies: list[DieCoordinate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_geometry(self) -> "LayoutCreate":
        if self.max_x < self.min_x or self.max_y < self.min_y:
            raise ValueError("layout bounds are inverted")
        seen: set[tuple[int, int]] = set()
        for die in self.valid_dies:
            key = (die.x, die.y)
            if key in seen:
                raise ValueError("valid_dies contains a duplicate coordinate")
            if not (self.min_x <= die.x <= self.max_x and self.min_y <= die.y <= self.max_y):
                raise ValueError("valid die is outside layout bounds")
            seen.add(key)
        return self


class LayoutView(ApiModel):
    id: UUID
    code: str
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    valid_die_count: int


class LayoutPage(ApiModel):
    items: list[LayoutView]
    next_cursor: str | None


class TranslateStep(ApiModel):
    op: Literal["translate"] = "translate"
    dx: int
    dy: int


class MirrorXStep(ApiModel):
    op: Literal["mirror_x"] = "mirror_x"


class MirrorYStep(ApiModel):
    op: Literal["mirror_y"] = "mirror_y"


class RotateStep(ApiModel):
    op: Literal["rotate"] = "rotate"
    degrees: Literal[0, 90, 180, 270]


CalibrationStep = Annotated[
    TranslateStep | MirrorXStep | MirrorYStep | RotateStep,
    Field(discriminator="op"),
]


class FrameCreate(ApiModel):
    code: str = Field(min_length=1, max_length=80)
    raw_origin_x: int
    raw_origin_y: int
    rotation_deg: Literal[0, 90, 180, 270]
    mirror_x: bool = False
    parent_frame_id: UUID | None = None
    calibration_steps: list[CalibrationStep] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def reject_ambiguous_legacy_orientation(self) -> "FrameCreate":
        if self.calibration_steps and (self.rotation_deg != 0 or self.mirror_x):
            raise ValueError("legacy orientation and calibration_steps must not conflict")
        return self


class FrameView(FrameCreate):
    id: UUID
    layout_id: UUID


class ReticleSiteCreate(ApiModel):
    code: str = Field(min_length=1, max_length=80)
    offset_x: int
    offset_y: int


class ReticleCreate(ApiModel):
    code: str = Field(min_length=1, max_length=80)
    shot_origin_x: int
    shot_origin_y: int
    shot_pitch_x: int
    shot_pitch_y: int
    sites: list[ReticleSiteCreate] = Field(min_length=1)


class ReticleView(ReticleCreate):
    id: UUID
    layout_id: UUID


class LayoutDetail(ApiModel):
    id: UUID
    code: str
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    valid_dies: list[DieCoordinate]
    frames: list[FrameView]
    reticles: list[ReticleView]


class WaferCreate(ApiModel):
    layout_id: UUID
    lot_code: str = Field(min_length=1, max_length=80)
    wafer_number: int = Field(ge=1)


class WaferView(WaferCreate):
    id: UUID


class WaferSummary(WaferView):
    layout_code: str
    created_at: datetime


class WaferPage(ApiModel):
    items: list[WaferSummary]
    next_cursor: str | None


class WaferDetail(WaferSummary):
    physical_die_count: int
    ingest_batch_count: int
    observation_count: int


class IdentityDuplicateGroup(ApiModel):
    canonical_x: int
    canonical_y: int
    physical_die_ids: list[UUID]
    source_frame_ids: list[UUID]
    observation_count: int


class IdentityAuditView(ApiModel):
    wafer_id: UUID
    physical_die_count: int
    canonical_identity_count: int
    duplicate_identity_count: int
    affected_observation_count: int
    duplicate_groups: list[IdentityDuplicateGroup]
    scanned_at: datetime


class GridAddress(ApiModel):
    kind: Literal["grid"] = "grid"
    x: int
    y: int


class ShotSiteAddress(ApiModel):
    kind: Literal["shot_site"] = "shot_site"
    shot_col: int
    shot_row: int
    site_code: str = Field(min_length=1, max_length=80)


Address = Annotated[GridAddress | ShotSiteAddress, Field(discriminator="kind")]


class ObservationInput(ApiModel):
    record_key: str = Field(min_length=1, max_length=120)
    address: Address
    stage: str = Field(min_length=1, max_length=80)
    result: str = Field(min_length=1, max_length=80)
    measured_at: datetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class BatchIngest(ApiModel):
    frame_id: UUID
    reticle_profile_id: UUID | None = None
    source_system: str = Field(min_length=1, max_length=120)
    observations: list[ObservationInput] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def require_reticle_for_shot_site(self) -> "BatchIngest":
        if any(item.address.kind == "shot_site" for item in self.observations):
            if self.reticle_profile_id is None:
                raise ValueError("reticle_profile_id is required for shot_site addresses")
        return self


class AcceptedObservation(ApiModel):
    observation_id: UUID
    physical_die_id: UUID
    record_key: str
    canonical_x: int
    canonical_y: int


class BatchView(ApiModel):
    batch_id: UUID
    wafer_id: UUID
    accepted: list[AcceptedObservation]


class BatchSummary(ApiModel):
    id: UUID
    wafer_id: UUID
    frame_id: UUID
    reticle_profile_id: UUID | None
    source_system: str
    record_count: int
    created_at: datetime


class BatchPage(ApiModel):
    items: list[BatchSummary]
    next_cursor: str | None


class BatchObservation(ApiModel):
    id: UUID
    physical_die_id: UUID
    canonical_x: int
    canonical_y: int
    record_key: str
    stage: str
    result: str
    source_address: Address
    measured_at: datetime
    attributes: dict[str, Any]


class BatchDetail(BatchSummary):
    observations: list[BatchObservation]


class ObservationView(ApiModel):
    id: UUID
    batch_id: UUID
    record_key: str
    stage: str
    result: str
    measured_at: datetime
    source_address: Address
    attributes: dict[str, Any]


class DieView(ApiModel):
    id: UUID
    wafer_id: UUID
    canonical_x: int
    canonical_y: int
    observations: list[ObservationView]


class ExportRecord(ApiModel):
    physical_die_id: UUID
    canonical_x: int
    canonical_y: int
    raw_x: int
    raw_y: int


class ExportView(ApiModel):
    wafer_id: UUID
    frame_id: UUID
    records: list[ExportRecord]


class ErrorView(ApiModel):
    code: str
    message: str

