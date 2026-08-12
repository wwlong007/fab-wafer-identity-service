import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault(
    "FAB_DATABASE_URL",
    "postgresql+psycopg://fab_identity:fab_identity@localhost:55432/fab_identity_test",
)

from fab_identity.infrastructure.database import engine  # noqa: E402
from fab_identity.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE observations, ingest_batches, physical_dies, wafers, "
                "reticle_sites, reticle_profiles, coordinate_frames, layout_dies, "
                "wafer_layouts CASCADE"
            )
        )
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def full_mask(min_x: int, max_x: int, min_y: int, max_y: int):
    return [
        {"x": x, "y": y}
        for y in range(min_y, max_y + 1)
        for x in range(min_x, max_x + 1)
    ]


@pytest.fixture
def square_catalog(client):
    layout = client.post(
        "/api/v1/layouts",
        json={
            "code": "MPW-3X3",
            "min_x": 0,
            "max_x": 2,
            "min_y": 0,
            "max_y": 2,
            "valid_dies": full_mask(0, 2, 0, 2),
        },
    ).json()
    identity = client.post(
        f"/api/v1/layouts/{layout['id']}/frames",
        json={
            "code": "SORT-A",
            "raw_origin_x": 0,
            "raw_origin_y": 0,
            "rotation_deg": 0,
            "mirror_x": False,
        },
    ).json()
    rotate_180 = client.post(
        f"/api/v1/layouts/{layout['id']}/frames",
        json={
            "code": "INSPECT-180",
            "raw_origin_x": 0,
            "raw_origin_y": 0,
            "rotation_deg": 180,
            "mirror_x": False,
        },
    ).json()
    wafer = client.post(
        "/api/v1/wafers",
        json={"layout_id": layout["id"], "lot_code": "LOT-2401", "wafer_number": 7},
    ).json()
    return layout, identity, rotate_180, wafer

