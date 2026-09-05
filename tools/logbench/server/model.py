"""Generic metric-playback data model.

Deliberately knows nothing about vision, cameras, AprilTags, or FRC. A "spec" is
whatever a domain adapter (see specs/) builds: a time window, some entities, the
metrics belonging to them, and a layout of panels that display them. The web
player renders any spec that validates against this model, so adding a new kind
of playback (shooter tuning, swerve module health, intake state) means writing one
new builder in specs/ and touching nothing in web/.

The wire format is intentionally not the same as these dataclasses -- see
encode.py, which packs sample data columnar + delta-encoded before it ships.
"""
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

# What a track's samples mean, and therefore how panels may draw it.
TrackKind = Literal['scalar', 'bool', 'string', 'enum', 'pose2d', 'intset']

PanelType = Literal['timeseries', 'field', 'readout', 'events', 'tracktoggle']


@dataclass
class Group:
    """An entity metrics belong to -- one camera, one swerve module, the drivetrain.

    Panels use group membership to decide what to show side by side, and the color
    is the entity's identity across every panel (its trail on the field is the same
    color as its trend line)."""
    id: str
    label: str
    color: str


@dataclass
class Track:
    """One metric over time. `id` is the key into PlayerSpec.data."""
    id: str
    label: str
    kind: TrackKind
    group: Optional[str] = None
    unit: Optional[str] = None
    color: Optional[str] = None
    # Fixed y-axis range. None means autoscale. (0, 100) for percentages keeps
    # every camera's trend chart directly comparable, which autoscale would ruin.
    domain: Optional[tuple[float, float]] = None
    # Panels may hide a track by default (the 8 health factors) while keeping it
    # one legend click away.
    hidden: bool = False


@dataclass
class Panel:
    id: str
    type: PanelType
    title: str
    tracks: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlayerSpec:
    title: str
    # Absolute log seconds. The player works in relative time (t - t0) everywhere
    # user-facing; t0 is kept so a timestamp can be tied back to the raw log.
    t0: float
    t1: float
    groups: list[Group] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    panels: list[Panel] = field(default_factory=list)
    # Rows of panel ids -> a responsive grid. [['field','readout'],['trend-Left']]
    layout: list[list[str]] = field(default_factory=list)
    # Panel-agnostic context the front end needs but that isn't time-varying:
    # field dimensions, AprilTag positions, severity thresholds.
    static: dict[str, Any] = field(default_factory=dict)
    # Human-readable notes about what this log was missing. Surfaced identically
    # in the Streamlit tab, the server app, and the standalone export.
    warnings: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(self.t1 - self.t0, 0.001)

    def track(self, track_id: str) -> Optional[Track]:
        return next((t for t in self.tracks if t.id == track_id), None)
