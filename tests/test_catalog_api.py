from conftest import full_mask


def test_health_and_catalog_crud(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    layout_response = client.post(
        "/api/v1/layouts",
        json={
            "code": "ENG-5X5",
            "min_x": -2,
            "max_x": 2,
            "min_y": -2,
            "max_y": 2,
            "valid_dies": full_mask(-2, 2, -2, 2),
        },
    )
    assert layout_response.status_code == 201
    layout = layout_response.json()
    assert layout["valid_die_count"] == 25

    frame_response = client.post(
        f"/api/v1/layouts/{layout['id']}/frames",
        json={
            "code": "PROBER-01",
            "raw_origin_x": 0,
            "raw_origin_y": 0,
            "rotation_deg": 90,
            "mirror_x": True,
        },
    )
    assert frame_response.status_code == 201
    assert frame_response.json()["layout_id"] == layout["id"]

    reticle_response = client.post(
        f"/api/v1/layouts/{layout['id']}/reticles",
        json={
            "code": "RT-QUAD",
            "shot_origin_x": 0,
            "shot_origin_y": 0,
            "shot_pitch_x": 2,
            "shot_pitch_y": 2,
            "sites": [
                {"code": "A", "offset_x": 0, "offset_y": 0},
                {"code": "B", "offset_x": 1, "offset_y": 0},
            ],
        },
    )
    assert reticle_response.status_code == 201
    assert len(reticle_response.json()["sites"]) == 2

    wafer_response = client.post(
        "/api/v1/wafers",
        json={"layout_id": layout["id"], "lot_code": "LOT-ENG", "wafer_number": 1},
    )
    assert wafer_response.status_code == 201


def test_catalog_rejects_invalid_geometry_and_duplicates(client):
    payload = {
        "code": "BAD",
        "min_x": 0,
        "max_x": 1,
        "min_y": 0,
        "max_y": 1,
        "valid_dies": [{"x": 4, "y": 0}],
    }
    assert client.post("/api/v1/layouts", json=payload).status_code == 422

    payload["valid_dies"] = full_mask(0, 1, 0, 1)
    assert client.post("/api/v1/layouts", json=payload).status_code == 201
    response = client.post("/api/v1/layouts", json=payload)
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"

