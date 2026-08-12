from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fab_identity.api import schemas
from fab_identity.domain.errors import ConflictError
from fab_identity.infrastructure import models
from fab_identity.repositories.catalog import CatalogRepository


class CatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = CatalogRepository(session)

    def create_layout(self, request: schemas.LayoutCreate) -> schemas.LayoutView:
        layout = models.WaferLayout(
            code=request.code,
            min_x=request.min_x,
            max_x=request.max_x,
            min_y=request.min_y,
            max_y=request.max_y,
            dies=[
                models.LayoutDie(canonical_x=die.x, canonical_y=die.y)
                for die in request.valid_dies
            ],
        )
        self.session.add(layout)
        self._commit("layout code already exists")
        return schemas.LayoutView(
            id=layout.id,
            code=layout.code,
            min_x=layout.min_x,
            max_x=layout.max_x,
            min_y=layout.min_y,
            max_y=layout.max_y,
            valid_die_count=len(layout.dies),
        )

    def create_frame(self, layout_id, request: schemas.FrameCreate) -> schemas.FrameView:
        self.repository.layout(layout_id)
        frame = models.CoordinateFrame(layout_id=layout_id, **request.model_dump())
        self.session.add(frame)
        self._commit("frame code already exists for this layout")
        return schemas.FrameView(id=frame.id, layout_id=layout_id, **request.model_dump())

    def create_reticle(self, layout_id, request: schemas.ReticleCreate) -> schemas.ReticleView:
        self.repository.layout(layout_id)
        profile = models.ReticleProfile(
            layout_id=layout_id,
            code=request.code,
            shot_origin_x=request.shot_origin_x,
            shot_origin_y=request.shot_origin_y,
            shot_pitch_x=request.shot_pitch_x,
            shot_pitch_y=request.shot_pitch_y,
            sites=[models.ReticleSite(**site.model_dump()) for site in request.sites],
        )
        self.session.add(profile)
        self._commit("reticle code or site code already exists")
        return schemas.ReticleView(id=profile.id, layout_id=layout_id, **request.model_dump())

    def create_wafer(self, request: schemas.WaferCreate) -> schemas.WaferView:
        self.repository.layout(request.layout_id)
        wafer = models.Wafer(**request.model_dump())
        self.session.add(wafer)
        self._commit("wafer already exists for this lot and number")
        return schemas.WaferView(id=wafer.id, **request.model_dump())

    def _commit(self, conflict_message: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(conflict_message) from exc

