from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fab_identity.domain.errors import NotFoundError
from fab_identity.infrastructure import models


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def layout(self, layout_id: UUID) -> models.WaferLayout:
        layout = self.session.scalar(
            select(models.WaferLayout)
            .where(models.WaferLayout.id == layout_id)
            .options(selectinload(models.WaferLayout.dies))
        )
        if layout is None:
            raise NotFoundError(f"layout {layout_id} was not found")
        return layout

    def frame(self, frame_id: UUID) -> models.CoordinateFrame:
        frame = self.session.scalar(
            select(models.CoordinateFrame).where(models.CoordinateFrame.id == frame_id)
        )
        if frame is None:
            raise NotFoundError(f"coordinate frame {frame_id} was not found")
        return frame

    def reticle(self, profile_id: UUID) -> models.ReticleProfile:
        profile = self.session.scalar(
            select(models.ReticleProfile)
            .where(models.ReticleProfile.id == profile_id)
            .options(selectinload(models.ReticleProfile.sites))
        )
        if profile is None:
            raise NotFoundError(f"reticle profile {profile_id} was not found")
        return profile

    def wafer(self, wafer_id: UUID) -> models.Wafer:
        wafer = self.session.scalar(
            select(models.Wafer)
            .where(models.Wafer.id == wafer_id)
            .options(selectinload(models.Wafer.layout).selectinload(models.WaferLayout.dies))
        )
        if wafer is None:
            raise NotFoundError(f"wafer {wafer_id} was not found")
        return wafer

