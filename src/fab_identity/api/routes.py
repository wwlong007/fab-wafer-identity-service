from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from fab_identity.api import schemas
from fab_identity.application.catalog import CatalogService
from fab_identity.application.ingest import IngestService
from fab_identity.application.query import QueryService
from fab_identity.application.reporting import ReportingService
from fab_identity.infrastructure.database import get_session


router = APIRouter(prefix="/api/v1")


@router.get("/layouts", response_model=schemas.LayoutPage)
def list_layouts(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return ReportingService(session).layouts(cursor, limit)


@router.get("/layouts/{layout_id}", response_model=schemas.LayoutDetail)
def get_layout(layout_id: UUID, session: Session = Depends(get_session)):
    return ReportingService(session).layout(layout_id)


@router.post("/layouts", response_model=schemas.LayoutView, status_code=status.HTTP_201_CREATED)
def create_layout(request: schemas.LayoutCreate, session: Session = Depends(get_session)):
    return CatalogService(session).create_layout(request)


@router.post(
    "/layouts/{layout_id}/frames",
    response_model=schemas.FrameView,
    status_code=status.HTTP_201_CREATED,
)
def create_frame(
    layout_id: UUID, request: schemas.FrameCreate, session: Session = Depends(get_session)
):
    return CatalogService(session).create_frame(layout_id, request)


@router.get("/frames/{frame_id}", response_model=schemas.FrameView)
def get_frame(frame_id: UUID, session: Session = Depends(get_session)):
    return ReportingService(session).frame(frame_id)


@router.post(
    "/layouts/{layout_id}/reticles",
    response_model=schemas.ReticleView,
    status_code=status.HTTP_201_CREATED,
)
def create_reticle(
    layout_id: UUID, request: schemas.ReticleCreate, session: Session = Depends(get_session)
):
    return CatalogService(session).create_reticle(layout_id, request)


@router.get("/reticles/{profile_id}", response_model=schemas.ReticleView)
def get_reticle(profile_id: UUID, session: Session = Depends(get_session)):
    return ReportingService(session).reticle(profile_id)


@router.post("/wafers", response_model=schemas.WaferView, status_code=status.HTTP_201_CREATED)
def create_wafer(request: schemas.WaferCreate, session: Session = Depends(get_session)):
    return CatalogService(session).create_wafer(request)


@router.get("/wafers", response_model=schemas.WaferPage)
def list_wafers(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    lot_code: str | None = Query(default=None, max_length=80),
    layout_id: UUID | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return ReportingService(session).wafers(cursor, limit, lot_code, layout_id)


@router.get("/wafers/{wafer_id}", response_model=schemas.WaferDetail)
def get_wafer(wafer_id: UUID, session: Session = Depends(get_session)):
    return ReportingService(session).wafer(wafer_id)


@router.post(
    "/wafers/{wafer_id}/observation-batches",
    response_model=schemas.BatchView,
    status_code=status.HTTP_201_CREATED,
)
def ingest_batch(
    wafer_id: UUID, request: schemas.BatchIngest, session: Session = Depends(get_session)
):
    return IngestService(session).ingest(wafer_id, request)


@router.get("/wafers/{wafer_id}/observation-batches", response_model=schemas.BatchPage)
def list_batches(
    wafer_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    source_system: str | None = Query(default=None, max_length=120),
    frame_id: UUID | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return ReportingService(session).batches(
        wafer_id, cursor, limit, source_system, frame_id
    )


@router.get("/observation-batches/{batch_id}", response_model=schemas.BatchDetail)
def get_batch(batch_id: UUID, session: Session = Depends(get_session)):
    return ReportingService(session).batch(batch_id)


@router.get("/wafers/{wafer_id}/dies", response_model=schemas.DieView)
def get_die(
    wafer_id: UUID,
    canonical_x: int = Query(),
    canonical_y: int = Query(),
    session: Session = Depends(get_session),
):
    return QueryService(session).die(wafer_id, canonical_x, canonical_y)


@router.get("/wafers/{wafer_id}/exports/{frame_id}", response_model=schemas.ExportView)
def export_wafer(wafer_id: UUID, frame_id: UUID, session: Session = Depends(get_session)):
    return QueryService(session).export(wafer_id, frame_id)

