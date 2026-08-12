from datetime import datetime, timezone


def observation(record_key, x, y, stage="sort", result="pass"):
    return {
        "record_key": record_key,
        "address": {"kind": "grid", "x": x, "y": y},
        "stage": stage,
        "result": result,
        "measured_at": datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc).isoformat(),
        "attributes": {"tester": "T-01"},
    }


def test_identity_frame_ingest_query_and_export(client, square_catalog):
    _, identity, _, wafer = square_catalog
    items = [observation(f"r-{x}-{y}", x, y) for y in range(3) for x in range(3)]
    response = client.post(
        f"/api/v1/wafers/{wafer['id']}/observation-batches",
        json={
            "frame_id": identity["id"],
            "source_system": "sort-a",
            "observations": items,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["accepted"]) == 9
    center = next(row for row in body["accepted"] if row["record_key"] == "r-1-1")
    assert (center["canonical_x"], center["canonical_y"]) == (1, 1)

    die = client.get(
        f"/api/v1/wafers/{wafer['id']}/dies",
        params={"canonical_x": 1, "canonical_y": 1},
    )
    assert die.status_code == 200
    assert [row["record_key"] for row in die.json()["observations"]] == ["r-1-1"]

    exported = client.get(
        f"/api/v1/wafers/{wafer['id']}/exports/{identity['id']}"
    ).json()
    assert {(r["raw_x"], r["raw_y"]) for r in exported["records"]} == {
        (x, y) for y in range(3) for x in range(3)
    }


def test_complete_square_r180_maps_expected_coordinates(client, square_catalog):
    _, _, rotate_180, wafer = square_catalog
    items = [observation(f"r-{x}-{y}", x, y) for y in range(3) for x in range(3)]
    response = client.post(
        f"/api/v1/wafers/{wafer['id']}/observation-batches",
        json={
            "frame_id": rotate_180["id"],
            "source_system": "inspection",
            "observations": items,
        },
    )
    assert response.status_code == 201, response.text
    by_key = {row["record_key"]: row for row in response.json()["accepted"]}
    assert (by_key["r-0-0"]["canonical_x"], by_key["r-0-0"]["canonical_y"]) == (2, 2)
    assert (by_key["r-2-2"]["canonical_x"], by_key["r-2-2"]["canonical_y"]) == (0, 0)


def test_invalid_record_rolls_back_whole_batch(client, square_catalog):
    _, identity, _, wafer = square_catalog
    response = client.post(
        f"/api/v1/wafers/{wafer['id']}/observation-batches",
        json={
            "frame_id": identity["id"],
            "source_system": "sort-a",
            "observations": [
                observation("valid-looking", 0, 0),
                observation("outside", 99, 99),
            ],
        },
    )
    assert response.status_code == 422
    query = client.get(
        f"/api/v1/wafers/{wafer['id']}/dies",
        params={"canonical_x": 0, "canonical_y": 0},
    )
    assert query.status_code == 404

