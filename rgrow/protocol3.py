#!/usr/bin/env python3
"""Build the tile design encoded by ``tile-config-sample.cpp``.

This module creates the logical tile table, its aTAM side-glue design, and
Seed coordinates.  It provides an rGrow tube canvas adapter but does not run
a simulation unless the caller requests it.
"""

from __future__ import annotations

import argparse
import csv
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Tuple


CIRCUMFERENCE = 6
LAYER_COUNT = 5
SEED_LAYER_COUNT = 2
W = CIRCUMFERENCE
L = LAYER_COUNT
H = 2 * L if L % 2 else L
SEEDH = SEED_LAYER_COUNT
FIRST_SEED_ID = H * W
NO_TILE = -1
TAU = 2
GLUE_STRENGTH = 1
CANVAS_TYPE = "tube-diagonals"
CANVAS_WIDTH = 160
# CANVAS_WIDTH=10
RGROW_TUBE_DIAGONALS_GUARD_COLUMNS = 2
PHASE_COLORS = ("#2563eb", "#22c55e", "#eab308", "#f97316", "#a855f7")
SEED_COLOR = "#111827"

# Main.cpp indexes sides as N=0, E=1, W=2, S=3.
# Coordinates are kept unwrapped; wrapping is a simulator's job.
DIRECTIONS = ("N", "E", "W", "S")
RGROW_DIRECTIONS = ("N", "E", "S", "W")
OPPOSITE = {"N": "S", "E": "W", "W": "E", "S": "N"}
Coordinate = Tuple[int, int]  # (y, x)


@dataclass(frozen=True)
class Tile:
    """One tile type and the four logical IDs from the C++ adjacency table."""

    id: int
    kind: str  # "regular" or "seed"
    row: int   # regular phase or seed depth
    position: int
    neighbours: Tuple[int, int, int, int]  # N, E, W, S


@dataclass(frozen=True)
class FrontierInterface:
    """A final-Seed side and the regular tile type named by the C++ table."""

    seed_id: int
    direction: str
    target_id: int
    coordinate: Coordinate


@dataclass(frozen=True)
class TileDesign:
    tiles: Mapping[int, Tile]
    seed_coordinates: Mapping[int, Coordinate]
    frontier: Tuple[FrontierInterface, ...]


@dataclass(frozen=True)
class Glue:
    """One unit-strength aTAM glue assigned to a paired side interface."""

    name: str
    strength: int = GLUE_STRENGTH


@dataclass(frozen=True)
class ATAMTile:
    """A logical tile with its N/E/W/S aTAM side glues."""

    tile: Tile
    glues: Tuple[Glue | None, Glue | None, Glue | None, Glue | None]


@dataclass(frozen=True)
class ATAMDesign:
    """The aTAM design data; no simulator-specific interpretation is included."""

    tau: int
    tiles: Mapping[int, ATAMTile]
    seed_coordinates: Mapping[int, Coordinate]
    frontier: Tuple[FrontierInterface, ...]


@dataclass(frozen=True)
class Canvas:
    """The rGrow canvas requested for the aTAM simulation."""

    canvas_type: str = CANVAS_TYPE
    circumference: int = CIRCUMFERENCE
    width: int = CANVAS_WIDTH

    @property
    def size(self) -> Tuple[int, int]:
        return (self.circumference, self.width)

    @property
    def half_circumference(self) -> int:
        return self.circumference // 2

    @property
    def first_usable_x(self) -> int:
        """First valid axial column for rGrow's ``tube-diagonals`` canvas."""
        return RGROW_TUBE_DIAGONALS_GUARD_COLUMNS + self.half_circumference

    @property
    def default_seed_origin(self) -> Coordinate:
        """Keep the initial N-directed Seed growth away from the top seam."""
        return (self.circumference - 1, self.first_usable_x)

    def seed_coordinate(self, y: int, x: int) -> Coordinate:
        """Canonical canvas coordinate for an unwrapped BFS Seed coordinate."""
        return (y % self.circumference, x)

    def move(self, coordinate: Coordinate, direction: str) -> Coordinate:
        """Apply rGrow's ``CanvasTubeDiagonals`` transition for one side."""
        y, x = coordinate
        half = self.half_circumference
        if direction == "N":
            return ((self.circumference - 1, x - half) if y == 0 else (y - 1, x))
        if direction == "E":
            return ((self.circumference - 1, x - half + 1)
                    if y == 0 else (y - 1, x + 1))
        if direction == "W":
            return ((0, x + half - 1)
                    if y == self.circumference - 1 else (y + 1, x - 1))
        if direction == "S":
            return ((0, x + half)
                    if y == self.circumference - 1 else (y + 1, x))
        raise ValueError(f"Unknown direction {direction!r}")


def regular_id(phase: int, position: int) -> int:
    """C++ ``mapping(i, j)`` for a regular tile."""
    return (phase % H) * W + position % W


def seed_id(depth: int, position: int) -> int:
    """Seed IDs are contiguous immediately after the regular tile IDs."""
    return FIRST_SEED_ID + depth * W + position % W


def build_tiles() -> Dict[int, Tile]:
    """Translate the C++ normal and Seed adjacency loops without reinterpretation."""
    tiles: Dict[int, Tile] = {}

    for phase in range(H):
        for position in range(W):
            neighbours = tuple(
                regular_id(
                    phase + 1 if direction in ("N", "E") else phase - 1,
                    position + (direction_index % 2) - (phase % 2),
                )
                for direction_index, direction in enumerate(DIRECTIONS)
            )
            tile_id = regular_id(phase, position)
            tiles[tile_id] = Tile(tile_id, "regular", phase, position, neighbours)

    for depth in range(SEEDH):
        for position in range(W):
            neighbours = []
            for direction_index, direction in enumerate(DIRECTIONS):
                next_position = position + (direction_index % 2) - (depth % 2)
                if depth == 0 and direction in ("W", "S"):
                    target = NO_TILE
                elif direction in ("N", "E") and depth + 1 == SEEDH:
                    target = regular_id(0, next_position)
                elif direction in ("N", "E"):
                    target = seed_id(depth + 1, next_position)
                else:
                    target = seed_id(depth - 1, next_position)
                neighbours.append(target)
            tile_id = seed_id(depth, position)
            tiles[tile_id] = Tile(tile_id, "seed", depth, position, tuple(neighbours))

    return tiles


def assign_seed_coordinates(
    tiles: Mapping[int, Tile], canvas: Canvas = Canvas(), origin: Coordinate | None = None
) -> Tuple[Dict[int, Coordinate], Tuple[FrontierInterface, ...]]:
    """Assign Seed positions by breadth-first traversal from Seed (0, 0).

    A tile is positioned the first time BFS reaches it.  Its stored logical
    neighbours are never rewritten or inferred from a coordinate formula.
    Regular tiles reached from the final Seed row are recorded as frontier
    interfaces; this design program does not assign a global regular-tile net.
    """
    root = seed_id(0, 0)
    origin = canvas.default_seed_origin if origin is None else origin
    coordinates: Dict[int, Coordinate] = {root: origin}
    frontier = []
    queue = deque([root])

    while queue:
        current_id = queue.popleft()
        current = tiles[current_id]
        y, x = coordinates[current_id]
        for direction, target_id in zip(DIRECTIONS, current.neighbours):
            if target_id == NO_TILE:
                continue
            target_coordinate = canvas.move((y, x), direction)
            target = tiles[target_id]
            if target.kind == "regular":
                frontier.append(
                    FrontierInterface(current_id, direction, target_id, target_coordinate)
                )
            elif target_id not in coordinates:
                coordinates[target_id] = target_coordinate
                queue.append(target_id)

    return coordinates, tuple(frontier)


def build_design(origin: Coordinate | None = None, canvas: Canvas = Canvas()) -> TileDesign:
    tiles = build_tiles()
    seed_coordinates, frontier = assign_seed_coordinates(tiles, canvas, origin)
    return TileDesign(tiles, seed_coordinates, frontier)


def build_atam_design(
    origin: Coordinate | None = None, canvas: Canvas = Canvas()
) -> ATAMDesign:
    """Create the tau=2 aTAM design with paired, unit-strength side glues."""
    design = build_design(origin, canvas)
    parent: Dict[Tuple[int, str], Tuple[int, str]] = {}

    def find(side: Tuple[int, str]) -> Tuple[int, str]:
        parent.setdefault(side, side)
        if parent[side] != side:
            parent[side] = find(parent[side])
        return parent[side]

    def union(left: Tuple[int, str], right: Tuple[int, str]) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    # A.direction and B.opposite(direction) must use the same glue when the
    # C++ table says that A.direction targets B.
    for source_id, tile in design.tiles.items():
        for direction, target_id in zip(DIRECTIONS, tile.neighbours):
            if target_id != NO_TILE:
                union((source_id, direction), (target_id, OPPOSITE[direction]))

    component_members: Dict[Tuple[int, str], list[Tuple[int, str]]] = {}
    for side in parent:
        component_members.setdefault(find(side), []).append(side)
    component_name = {}
    for root, members in component_members.items():
        tile_id, direction = min(members)
        component_name[root] = f"g_t{tile_id}_{direction.lower()}"

    atam_tiles: Dict[int, ATAMTile] = {}
    for tile_id, tile in design.tiles.items():
        glues = tuple(
            None if target_id == NO_TILE else Glue(component_name[find((tile_id, direction))])
            for direction, target_id in zip(DIRECTIONS, tile.neighbours)
        )
        atam_tiles[tile_id] = ATAMTile(tile, glues)
    return ATAMDesign(TAU, atam_tiles, design.seed_coordinates, design.frontier)


def to_rgrow_tileset(design: ATAMDesign, canvas: Canvas = Canvas()):
    """Convert this aTAM design to an rGrow TileSet without running it.

    rGrow Seed coordinates are unsigned.  The axial coordinate is translated
    only when needed to remove a negative value.  The circumferential
    coordinate is reduced by ``canvas.circumference``, which is the tube
    boundary condition rather than an additional placement formula.
    """
    import sys

    source_directory = str(Path(__file__).resolve().parent)
    sys.path[:] = [entry for entry in sys.path
                   if Path(entry or ".").resolve() != Path(source_directory)]
    from rgrow import Tile as RGrowTile, TileSet

    def tile_name(tile_id: int) -> str:
        return f"tile_{tile_id}"

    rgrow_tiles = []
    glue_names = set()
    for atam_tile in design.tiles.values():
        glue_by_direction = dict(zip(DIRECTIONS, atam_tile.glues))
        edges = []
        for direction in RGROW_DIRECTIONS:
            glue = glue_by_direction[direction]
            edge = "0" if glue is None else glue.name
            edges.append(edge)
            if glue is not None:
                glue_names.add(glue.name)
        rgrow_tiles.append(RGrowTile(edges, name=tile_name(atam_tile.tile.id)))

    min_x = min(x for _y, x in design.seed_coordinates.values())
    x_shift = canvas.first_usable_x - min_x
    seed = [
        (*canvas.seed_coordinate(y, x + x_shift), tile_name(tile_id))
        for tile_id, (y, x) in design.seed_coordinates.items()
    ]
    glues = [(name, name, GLUE_STRENGTH) for name in sorted(glue_names)]
    return TileSet(
        tiles=rgrow_tiles,
        glues=glues,
        seed=seed,
        size=canvas.size,
        canvas_type=canvas.canvas_type,
        model="atam",
        threshold=design.tau,
    )


def make_simulation(origin: Coordinate | None = None, canvas: Canvas = Canvas()):
    """Build an rGrow simulation.  The caller decides whether to evolve it."""
    return to_rgrow_tileset(build_atam_design(origin, canvas), canvas).to_simulation()


def draw_canvas(
    simulation, design: ATAMDesign, canvas: Canvas, output: Path, annotate: bool = False
) -> None:
    """Save the current rGrow canvas as a PNG after the caller evolves it."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    import numpy as np

    tile_count = len(design.tiles)
    colors_by_name = {"empty": "#ffffff"}
    labels_by_name = {}
    for ordinal, atam_tile in enumerate(design.tiles.values()):
        tile = atam_tile.tile
        name = f"tile_{tile.id}"
        base_color = SEED_COLOR if tile.kind == "seed" else PHASE_COLORS[tile.row % L]
        alpha = round(255 * (0.35 + 0.65 * (ordinal + 1) / tile_count))
        colors_by_name[name] = f"{base_color}{alpha:02x}"
        labels_by_name[name] = str(tile.id)

    tile_names = list(simulation.tile_names)
    colors = [colors_by_name.get(str(name), "#94a3b8") for name in tile_names]
    if colors:
        colors[0] = "#ffffff"

    raw_image = simulation.canvas_copy()
    raw_rows, raw_columns = raw_image.shape
    display_size = raw_rows + raw_columns
    image = np.zeros((display_size, display_size), dtype=raw_image.dtype)
    # CanvasTubeDiagonals.draw renders raw (row, column) at
    # display (row + column, column).  Match that transform here.
    for row, values in enumerate(raw_image):
        for column, tile_index in enumerate(values):
            image[row + column, column] = tile_index

    figure, axis = plt.subplots(figsize=(10, 10), constrained_layout=True)
    axis.imshow(image, interpolation="none", cmap=ListedColormap(colors),
                vmin=-0.5, vmax=len(colors) - 0.5, origin="upper", aspect="auto")
    axis.set_title(f"aTAM: tau={design.tau}; {canvas.canvas_type}; "
                   f"circumference={canvas.circumference}")
    axis.set_xlabel("tube-diagonal display column")
    axis.set_ylabel("tube-diagonal display row")
    if annotate:
        for row, values in enumerate(raw_image):
            for column, tile_index in enumerate(values):
                if int(tile_index):
                    name = str(tile_names[int(tile_index)])
                    axis.text(column, row + column, labels_by_name.get(name, name),
                              ha="center", va="center", fontsize=5, color="#000000")
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=200)
    plt.close(figure)


def write_design(design: ATAMDesign, path: Path) -> None:
    """Write the aTAM tile design and BFS-assigned Seed coordinates as CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("record", "id", "kind", "row", "position", "direction",
                        "target_id", "glue", "strength", "tau", "y", "x"),
        )
        writer.writeheader()
        writer.writerow({"record": "atam", "tau": design.tau})
        for atam_tile in design.tiles.values():
            tile = atam_tile.tile
            for direction, target_id, glue in zip(DIRECTIONS, tile.neighbours,
                                                  atam_tile.glues):
                writer.writerow({"record": "edge", "id": tile.id, "kind": tile.kind,
                                 "row": tile.row, "position": tile.position,
                                 "direction": direction, "target_id": target_id,
                                 "glue": glue.name if glue else None,
                                 "strength": glue.strength if glue else 0})
        for tile_id, (y, x) in design.seed_coordinates.items():
            writer.writerow({"record": "seed_coordinate", "id": tile_id,
                             "y": y, "x": x})
        for interface in design.frontier:
            writer.writerow({"record": "frontier", "id": interface.seed_id,
                             "direction": interface.direction,
                             "target_id": interface.target_id,
                             "y": interface.coordinate[0], "x": interface.coordinate[1]})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="CSV path for the generated tile design")
    parser.add_argument("--origin-y", type=int)
    parser.add_argument("--origin-x", type=int)
    parser.add_argument("--simulate", action="store_true",
                        help="build and evolve the rGrow aTAM simulation")
    parser.add_argument("--events", type=int, default=2_000)
    parser.add_argument("--circumference", type=int, default=CIRCUMFERENCE)
    parser.add_argument("--canvas-width", type=int, default=CANVAS_WIDTH)
    parser.add_argument("--plot", type=Path,
                        help="PNG path for the canvas after --simulate")
    parser.add_argument("--tile-labels", action="store_true",
                        help="write tile IDs into occupied cells of --plot")
    args = parser.parse_args()
    if (args.origin_y is None) != (args.origin_x is None):
        parser.error("--origin-y and --origin-x must be supplied together")
    canvas = Canvas(circumference=args.circumference, width=args.canvas_width)
    origin = None if args.origin_y is None else (args.origin_y, args.origin_x)
    design = build_atam_design(origin, canvas)
    write_design(design, args.output)
    if args.plot and not args.simulate:
        parser.error("--plot requires --simulate")
    if args.simulate:
        simulation = to_rgrow_tileset(design, canvas).to_simulation()
        simulation.add_state()
        simulation.evolve(for_events=args.events)
        if args.plot:
            draw_canvas(simulation, design, canvas, args.plot, args.tile_labels)


if __name__ == "__main__":
    main()
