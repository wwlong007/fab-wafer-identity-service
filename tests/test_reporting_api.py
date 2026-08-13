from datetime import datetime, timezone
from uuid import UUID

from conftest import full_mask


def create_layout(client, code):
    response = client.post(
        "/api/v1/layouts",
        json={
            "code": code,
            "min_x": 0,
            "max_x": 1,
            "min_y": 0,
            "max_y": 1,
            "valid_dies": full_mask(0, 1, 0, 1),
        },
    )
    assert response.status_code == 201
    return response.json()


def test_layout_list_cursor_and_detail(client):
    layouts = [create_layout(client, f"LAYOUT-{index}") for index in range(3)]
    first = client.get("/api/v1/layouts", params={"limit": 2})
    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    assert first.json()["next_cursor"]

    second = client.get(
        "/api/v1/layouts",
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )
    assert second.status_code == 200
    returned_ids = {
        row["id"] for row in first.json()["items"] + second.json()["items"]
    }
    assert returned_ids == {row["id"] for row in layouts}
    assert second.json()["next_cursor"] is None

    frame = client.post(
        f"/api/v1/layouts/{layouts[0]['id']}/frames",
        json={
            "code": "FRAME-A",
            "raw_origin_x": 19,
            "raw_origin_y": -23,
            "rotation_deg": 90,
            "mirror_x": True,
        },
    ).json()
    reticle = client.post(
        f"/api/v1/layouts/{layouts[0]['id']}/reticles",
        json={
            "code": "RETICLE-A",
            "shot_origin_x": 4,
            "shot_origin_y": 7,
            "shot_pitch_x": 2,
            "shot_pitch_y": 3,
            "sites": [{"code": "S1", "offset_x": 1, "offset_y": 0}],
        },
    ).json()
    detail = client.get(f"/api/v1/layouts/{layouts[0]['id']}")
    assert detail.status_code == 200
    assert {tuple((row["x"], row["y"])) for row in detail.json()["valid_dies"]} == {
        (0, 0),
        (1, 0),
        (0, 1),
        (1, 1),
    }
    assert [row["id"] for row in detail.json()["frames"]] == [frame["id"]]
    assert [row["id"] for row in detail.json()["reticles"]] == [reticle["id"]]
    assert client.get(f"/api/v1/frames/{frame['id']}").json()["code"] == "FRAME-A"
    assert client.get(f"/api/v1/reticles/{reticle['id']}").json()["sites"][0]["code"] == "S1"


def test_wafer_filters_summary_and_batch_audit(client):
    layout = create_layout(client, "AUDIT-LAYOUT")
    frame = client.post(
        f"/api/v1/layouts/{layout['id']}/frames",
        json={
            "code": "IDENTITY",
            "raw_origin_x": 0,
            "raw_origin_y": 0,
            "rotation_deg": 0,
            "mirror_x": False,
        },
    ).json()
    wafers = []
    for number, lot in ((1, "LOT-A"), (2, "LOT-A"), (3, "LOT-B")):
        wafers.append(
            client.post(
                "/api/v1/wafers",
                json={"layout_id": layout["id"], "lot_code": lot, "wafer_number": number},
            ).json()
        )

    filtered = client.get("/api/v1/wafers", params={"lot_code": "LOT-A"})
    assert filtered.status_code == 200
    assert {row["id"] for row in filtered.json()["items"]} == {
        wafers[0]["id"],
        wafers[1]["id"],
    }

    batch_response = client.post(
        f"/api/v1/wafers/{wafers[0]['id']}/observation-batches",
        json={
            "frame_id": frame["id"],
            "source_system": "sort-a",
            "observations": [
                {
                    "record_key": f"record-{x}-{y}",
                    "address": {"kind": "grid", "x": x, "y": y},
                    "stage": "sort",
                    "result": "pass",
                    "measured_at": datetime(2026, 8, 13, tzinfo=timezone.utc).isoformat(),
                    "attributes": {"program": "CP-01"},
                }
                for y in range(2)
                for x in range(2)
            ],
        },
    )
    assert batch_response.status_code == 201
    batch_id = batch_response.json()["batch_id"]

    summary = client.get(f"/api/v1/wafers/{wafers[0]['id']}")
    assert summary.status_code == 200
    assert summary.json()["physical_die_count"] == 4
    assert summary.json()["ingest_batch_count"] == 1
    assert summary.json()["observation_count"] == 4

    batches = client.get(
        f"/api/v1/wafers/{wafers[0]['id']}/observation-batches",
        params={"source_system": "sort-a", "frame_id": frame["id"]},
    )
    assert batches.status_code == 200
    assert [row["id"] for row in batches.json()["items"]] == [batch_id]

    detail = client.get(f"/api/v1/observation-batches/{batch_id}")
    assert detail.status_code == 200
    audited = next(
        row for row in detail.json()["observations"] if row["record_key"] == "record-1-0"
    )
    assert audited["canonical_x"] == 1
    assert audited["canonical_y"] == 0
    assert audited["source_address"] == {
        "kind": "grid",
        "x": 1,
        "y": 0,
    }


def test_invalid_cursor_and_request_id_contract(client):
    invalid = client.get("/api/v1/layouts", params={"cursor": "not-a-cursor"})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_error"

    supplied = "3c957626-408a-4c78-9d45-b18f78753c5f"
    response = client.get("/healthz", headers={"X-Request-ID": supplied})
    assert response.headers["X-Request-ID"] == supplied

    generated = client.get("/healthz", headers={"X-Request-ID": "invalid"})
    assert UUID(generated.headers["X-Request-ID"])


def test_identity_audit_reports_cross_frame_duplicate_groups(client, square_catalog):
    _, identity, rotate_180, wafer = square_catalog
    measured_at = datetime(2026, 8, 13, tzinfo=timezone.utc).isoformat()
    physical_die_ids = []
    for frame, raw, record_key in (
        (identity, (0, 0), "sort-identity"),
        (rotate_180, (2, 2), "inspect-identity"),
    ):
        response = client.post(
            f"/api/v1/wafers/{wafer['id']}/observation-batches",
            json={
                "frame_id": frame["id"],
                "source_system": frame["code"],
                "observations": [
                    {
                        "record_key": record_key,
                        "address": {"kind": "grid", "x": raw[0], "y": raw[1]},
                        "stage": "audit",
                        "result": "pass",
                        "measured_at": measured_at,
                    }
                ],
            },
        )
        assert response.status_code == 201, response.text
        physical_die_ids.append(response.json()["accepted"][0]["physical_die_id"])

    response = client.get(f"/api/v1/wafers/{wafer['id']}/identity-audit")
    assert response.status_code == 200
    audit = response.json()
    distinct_die_count = len(set(physical_die_ids))
    assert audit["physical_die_count"] == distinct_die_count
    assert audit["canonical_identity_count"] == 1
    assert audit["duplicate_identity_count"] == distinct_die_count - 1
    if distinct_die_count == 1:
        assert audit["affected_observation_count"] == 0
        assert audit["duplicate_groups"] == []
    else:
        assert audit["affected_observation_count"] == 2
        assert len(audit["duplicate_groups"]) == 1
        group = audit["duplicate_groups"][0]
        assert (group["canonical_x"], group["canonical_y"]) == (0, 0)
        assert set(group["physical_die_ids"]) == set(physical_die_ids)
        assert set(group["source_frame_ids"]) == {identity["id"], rotate_180["id"]}
        assert group["observation_count"] == 2
