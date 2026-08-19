from types import SimpleNamespace

from fab_identity.domain.coordinates import Bounds, Point, chain_transform


def test_parent_chain_is_ordered_and_reversible():
    root = SimpleNamespace(
        id="root",
        layout_id="layout",
        parent_frame_id=None,
        raw_origin_x=0,
        raw_origin_y=0,
        rotation_deg=0,
        mirror_x=False,
        calibration_steps=[{"op": "translate", "dx": 2, "dy": 0}],
    )
    child = SimpleNamespace(
        id="child",
        layout_id="layout",
        parent_frame_id="root",
        raw_origin_x=0,
        raw_origin_y=0,
        rotation_deg=0,
        mirror_x=False,
        calibration_steps=[{"op": "mirror_x"}, {"op": "rotate", "degrees": 90}],
    )
    transform = chain_transform(Bounds(-4, 6, -4, 6), [root, child])
    raw = transform.apply(Point(1, 2))
    assert raw == Point(6, 7)
    assert transform.inverse().apply(raw) == Point(1, 2)
