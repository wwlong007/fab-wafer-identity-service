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

    def __post_init__(self) -> None:
        if self.rotation_deg not in {0, 90, 180, 270}:
            raise ValueError("rotation_deg must be 0, 90, 180, or 270")


def normalize_observed(raw: Point, frame: FrameDefinition, observed: Bounds) -> Point:
    """Normalize an equipment point using the currently observed batch extent.

    Equipment adapters historically supplied only sparse batches, so this helper
    reconstructs a local extent from those records. Each adapter owns its inverse.
    """
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
    """Legacy export formula maintained separately from ingest normalization."""
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

