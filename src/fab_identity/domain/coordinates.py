from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Bounds:
    min_x: int
    max_x: int
    min_y: int
    max_y: int

    @property
    def width(self) -> int:
        return self.max_x - self.min_x + 1

    @property
    def height(self) -> int:
        return self.max_y - self.min_y + 1

    def contains(self, point: Point) -> bool:
        return (
            self.min_x <= point.x <= self.max_x
            and self.min_y <= point.y <= self.max_y
        )

    @classmethod
    def enclosing(cls, points: list[Point]) -> "Bounds":
        if not points:
            raise ValueError("at least one point is required")
        return cls(
            min(point.x for point in points),
            max(point.x for point in points),
            min(point.y for point in points),
            max(point.y for point in points),
        )


@dataclass(frozen=True, slots=True)
class FrameDefinition:
    raw_origin: Point
    rotation_deg: int
    mirror_x: bool
    calibration_steps: tuple[dict, ...] = ()

    def __post_init__(self) -> None:
        if self.rotation_deg not in {0, 90, 180, 270}:
            raise ValueError("rotation_deg must be 0, 90, 180, or 270")


@dataclass(frozen=True, slots=True)
class IntegerAffine:
    a: int
    b: int
    c: int
    d: int
    tx: int = 0
    ty: int = 0

    def apply(self, point: Point) -> Point:
        return Point(
            self.a * point.x + self.b * point.y + self.tx,
            self.c * point.x + self.d * point.y + self.ty,
        )

    def then(self, other: "IntegerAffine") -> "IntegerAffine":
        return IntegerAffine(
            other.a * self.a + other.b * self.c,
            other.a * self.b + other.b * self.d,
            other.c * self.a + other.d * self.c,
            other.c * self.b + other.d * self.d,
            other.a * self.tx + other.b * self.ty + other.tx,
            other.c * self.tx + other.d * self.ty + other.ty,
        )

    def inverse(self) -> "IntegerAffine":
        determinant = self.a * self.d - self.b * self.c
        if determinant not in {-1, 1}:
            raise ValueError("transform is not an integer lattice bijection")
        ia, ib = self.d // determinant, -self.b // determinant
        ic, identity = -self.c // determinant, self.a // determinant
        return IntegerAffine(
            ia, ib, ic, identity,
            -(ia * self.tx + ib * self.ty),
            -(ic * self.tx + identity * self.ty),
        )


class CoordinateTransform:
    def __init__(self, geometry: Bounds, frame: FrameDefinition) -> None:
        localize = IntegerAffine(1, 0, 0, 1, -geometry.min_x, -geometry.min_y)
        orient = self._orientation(geometry.width, geometry.height, frame)
        externalize = IntegerAffine(1, 0, 0, 1, frame.raw_origin.x, frame.raw_origin.y)
        self._canonical_to_raw = localize.then(orient).then(externalize)
        self._raw_to_canonical = self._canonical_to_raw.inverse()

    @staticmethod
    def _orientation(width: int, height: int, frame: FrameDefinition) -> IntegerAffine:
        transform = IntegerAffine(1, 0, 0, 1)
        if frame.mirror_x:
            transform = transform.then(IntegerAffine(-1, 0, 0, 1, width - 1, 0))
        return transform.then({
            0: IntegerAffine(1, 0, 0, 1),
            90: IntegerAffine(0, 1, -1, 0, 0, width - 1),
            180: IntegerAffine(-1, 0, 0, -1, width - 1, height - 1),
            270: IntegerAffine(0, -1, 1, 0, height - 1, 0),
        }[frame.rotation_deg])

    def to_raw(self, canonical: Point) -> Point:
        return self._canonical_to_raw.apply(canonical)

    def to_canonical(self, raw: Point) -> Point:
        return self._raw_to_canonical.apply(raw)


def _step_affine(step: dict) -> IntegerAffine:
    operation = step.get("op")
    if operation == "translate":
        return IntegerAffine(1, 0, 0, 1, int(step["dx"]), int(step["dy"]))
    if operation == "mirror_x":
        return IntegerAffine(-1, 0, 0, 1)
    if operation == "mirror_y":
        return IntegerAffine(1, 0, 0, -1)
    if operation == "rotate":
        return {
            0: IntegerAffine(1, 0, 0, 1),
            90: IntegerAffine(0, 1, -1, 0),
            180: IntegerAffine(-1, 0, 0, -1),
            270: IntegerAffine(0, -1, 1, 0),
        }[int(step["degrees"])]
    raise ValueError("unknown calibration operation")


def _explicit_affine(steps: tuple[dict, ...]) -> IntegerAffine:
    result = IntegerAffine(1, 0, 0, 1)
    for step in steps:
        result = result.then(_step_affine(step))
    return result


def _legacy_child_affine(geometry: Bounds, frame: FrameDefinition) -> IntegerAffine:
    return IntegerAffine(1, 0, 0, 1).then(
        CoordinateTransform._orientation(geometry.width, geometry.height, frame)
    ).then(IntegerAffine(1, 0, 0, 1, frame.raw_origin.x, frame.raw_origin.y))


def resolve_frame_chain(frame, lookup) -> list:
    chain, seen = [], set()
    current = frame
    while current is not None:
        if current.id in seen:
            raise ValueError("coordinate frame parent cycle")
        seen.add(current.id)
        chain.append(current)
        current = lookup(current.parent_frame_id) if current.parent_frame_id else None
    chain.reverse()
    if any(item.layout_id != chain[0].layout_id for item in chain):
        raise ValueError("coordinate frame parent belongs to another layout")
    return chain


def chain_transform(geometry: Bounds, frames: list) -> IntegerAffine:
    if not frames:
        raise ValueError("at least one coordinate frame is required")
    root = frames[0]
    root_definition = FrameDefinition(
        Point(root.raw_origin_x, root.raw_origin_y),
        root.rotation_deg,
        root.mirror_x,
        tuple(root.calibration_steps or ()),
    )
    total = CoordinateTransform(geometry, root_definition)._canonical_to_raw
    total = total.then(_explicit_affine(root_definition.calibration_steps))
    for frame in frames[1:]:
        definition = FrameDefinition(
            Point(frame.raw_origin_x, frame.raw_origin_y),
            frame.rotation_deg,
            frame.mirror_x,
            tuple(frame.calibration_steps or ()),
        )
        # The public baseline has a deliberate composition-order defect.
        total = _legacy_child_affine(geometry, definition).then(total)
        total = _explicit_affine(definition.calibration_steps).then(total)
    return total


def normalize_observed(raw: Point, frame: FrameDefinition, observed: Bounds) -> Point:
    x = raw.x - frame.raw_origin.x
    y = raw.y - frame.raw_origin.y
    width, height = observed.width, observed.height

    if frame.mirror_x:
        x = width - 1 - x

    if frame.rotation_deg == 90:
        x, y = y, width - 1 - x
    elif frame.rotation_deg == 180:
        x, y = width - 1 - x, height - 1 - y
    elif frame.rotation_deg == 270:
        x, y = height - 1 - y, x

    return Point(x + observed.min_x, y + observed.min_y)


def export_observed(canonical: Point, frame: FrameDefinition, observed: Bounds) -> Point:
    x = canonical.x - observed.min_x
    y = canonical.y - observed.min_y
    width, height = observed.width, observed.height

    if frame.rotation_deg == 90:
        x, y = width - 1 - y, x
    elif frame.rotation_deg == 180:
        x, y = width - 1 - x, height - 1 - y
    elif frame.rotation_deg == 270:
        x, y = y, height - 1 - x

    if frame.mirror_x:
        x = width - 1 - x
    return Point(x + frame.raw_origin.x, y + frame.raw_origin.y)


def flatten_shot_site(
    shot_col: int,
    shot_row: int,
    shot_origin: Point,
    shot_pitch: Point,
    site_offset: Point,
) -> Point:
    return Point(
        shot_origin.x + shot_col * shot_pitch.x + site_offset.x,
        shot_origin.y + shot_row * shot_pitch.y + site_offset.y,
    )

