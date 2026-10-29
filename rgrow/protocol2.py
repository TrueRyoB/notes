#!/usr/bin/env python3
"""Simulate the revised EP-2 right-upward nanotube net with rGrow aTAM.

The source of truth is the labeled CSV in experimental-protocol-2.md.  The
three blue seed tiles are blue2, blue4, and blue6.  They sit on the lower-left
diagonal of the net; subsequent copies advance up and to the right.  red1--4
are functional tiles: their N/E/S/W bonds come from the cells adjacent to them
in that CSV, just as for every coloured tile.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


# Literal transcription of the revised CSV, omitting only its all-blank first
# line. Coordinates use (row, column), so north means row - 1 and east means
# column + 1. Repeated labels demonstrate right-upward propagation.
CSV_ROWS = (
    ("", "", "", "", "red4", "green1", "", "", ""),
    ("", "", "", "red3", "blue1", "green2", "green3", "", ""),
    ("", "", "red2", "yellow1", "blue2", "blue3", "green4", "green5", ""),
    ("", "red1", "green1", "yellow2", "yellow3", "blue4", "blue5", "green6", "green7"),
    ("", "blue1", "green2", "green3", "yellow4", "yellow5", "blue6", "blue7", "red1"),
    ("", "blue2", "blue3", "green4", "green5", "yellow6", "yellow7", "red3", ""),
    ("", "", "blue4", "blue5", "green6", "green7", "red2", "", ""),
    ("", "", "", "blue6", "blue7", "red1", "", "", ""),
    ("", "", "", "", "red3", "", "", "", ""),
)

# User-specified seed locations in CSV_ROWS: the lower-left diagonal.
SEED_TEMPLATE_POSITIONS = {
    "blue2": (5, 1),
    "blue4": (6, 2),
    "blue6": (7, 3),
}

CANVAS_HEIGHT = 64
CANVAS_WIDTH = 160
SEED_Y = 42
SEED_X = 5
NULL_GLUE = "0"
PALETTE = {
    "blue": "#2563eb", "green": "#22c55e", "yellow": "#eab308",
    "red": "#dc2626", "seed": "#1d4ed8",
}

DIRECTIONS = (
    ("N", -1, 0, "S"), ("E", 0, 1, "W"),
    ("S", 1, 0, "N"), ("W", 0, -1, "E"),
)
EDGE_INDEX = {"N": 0, "E": 1, "S": 2, "W": 3}


@dataclass(frozen=True)
class TileSpec:
    """Model-neutral tile; edge ordering is north, east, south, west."""

    name: str
    edges: Tuple[str, str, str, str]
    color: str
    role: str
    seed_only: bool = False


class UnionFind:
    """Merge tile-side variables that represent the same CSV contact."""

    def __init__(self) -> None:
        self.parent: Dict[Tuple[str, str], Tuple[str, str]] = {}

    def find(self, item: Tuple[str, str]) -> Tuple[str, str]:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, first: Tuple[str, str], second: Tuple[str, str]) -> None:
        first_root, second_root = self.find(first), self.find(second)
        if first_root != second_root:
            self.parent[second_root] = first_root


def tile_role(name: str) -> str:
    for role in ("blue", "green", "yellow", "red"):
        if name.startswith(role):
            return role
    raise ValueError(f"Unknown CSV tile name {name!r}")


def cells() -> Dict[Tuple[int, int], str]:
    """Return all nonblank literal source cells, keyed by (row, column)."""
    return {
        (row, column): name
        for row, source_row in enumerate(CSV_ROWS)
        for column, name in enumerate(source_row)
        if name
    }


def functional_tile_names() -> List[str]:
    """The 7 blue, 7 green, 7 yellow, and 4 red functional tiles."""
    return sorted(
        set(cells().values()),
        key=lambda name: (tile_role(name), int(name[len(tile_role(name)):])),
    )


def derive_glue_edges() -> Dict[str, Tuple[str, str, str, str]]:
    """Give every literal CSV contact a reusable, strength-one glue.

    A tile label can occur several times in the diagram. Its named side has to
    be identical at every occurrence, so all equivalent side variables are
    unioned before glue identities are assigned. This makes red1--4 ordinary
    bonding tiles rather than nonbinding fold annotations.
    """
    source = cells()
    components = UnionFind()
    used_sides = set()
    for (row, column), name in source.items():
        for direction, dy, dx, opposite in DIRECTIONS:
            neighbour = source.get((row + dy, column + dx))
            if neighbour is not None:
                own_side = (name, direction)
                neighbour_side = (neighbour, opposite)
                components.union(own_side, neighbour_side)
                used_sides.add(own_side)
                used_sides.add(neighbour_side)

    roots = sorted({components.find(side) for side in used_sides})
    glue_for_root = {root: f"g{index:02d}" for index, root in enumerate(roots, 1)}
    result: Dict[str, Tuple[str, str, str, str]] = {}
    for name in functional_tile_names():
        result[name] = tuple(
            glue_for_root[components.find((name, direction))]
            if (name, direction) in used_sides else NULL_GLUE
            for direction in ("N", "E", "S", "W")
        )  # type: ignore[assignment]
    return result


def make_tile_specs() -> Tuple[TileSpec, ...]:
    """Make functional CSV tiles and three one-way blue seed variants.

    The seed variants are blue tiles, never red substitutes. Their south/west
    glues are blanked so tau=1 cannot initiate the mirrored down-left net.
    North/east bonds remain those of blue2, blue4, and blue6 respectively.
    """
    edges = derive_glue_edges()
    functional = tuple(
        TileSpec(name, edges[name], PALETTE[tile_role(name)], tile_role(name))
        for name in functional_tile_names()
    )
    seeds = []
    for name in SEED_TEMPLATE_POSITIONS:
        north, east, _south, _west = edges[name]
        seeds.append(TileSpec(
            f"seed_{name}", (north, east, NULL_GLUE, NULL_GLUE),
            PALETTE["seed"], "seed", seed_only=True,
        ))
    return functional + tuple(seeds)


def make_glues(specs: Iterable[TileSpec]) -> List[Tuple[str, str, float]]:
    """All observed contacts are self-pairing, unit-strength aTAM bonds."""
    names = sorted({edge for spec in specs for edge in spec.edges if edge != NULL_GLUE})
    return [(name, name, 1.0) for name in names]


def make_seed() -> List[Tuple[int, int, str]]:
    """Place blue2, blue4, blue6 on the stated diagonal seed row."""
    origin_row, origin_column = SEED_TEMPLATE_POSITIONS["blue2"]
    return [
        (SEED_Y + row - origin_row, SEED_X + column - origin_column, f"seed_{name}")
        for name, (row, column) in SEED_TEMPLATE_POSITIONS.items()
    ]


def make_tileset(model: str = "atam"):
    """Build aTAM or kTAM while retaining the same CSV-derived design."""
    from rgrow import Tile, TileSet

    specs = make_tile_specs()
    shared = dict(
        tiles=[Tile(list(spec.edges), name=spec.name, color=spec.color) for spec in specs],
        glues=make_glues(specs),
        seed=make_seed(),
        size=(CANVAS_HEIGHT, CANVAS_WIDTH),
        # canvas_type="Square",
        canvas_type="Tube",
    )
    if model == "atam":
        # Current rGrow aTAM reads threshold rather than the legacy tau field.
        return TileSet(**shared, model="atam", threshold=1.0)
    if model == "ktam":
        # Tile identities/glues are unchanged; calibrate these kinetic values.
        return TileSet(**shared, model="ktam", gse=8.0, gmc=16.0, alpha=1.0)
    raise ValueError(f"Unknown model {model!r}")


def assert_design_invariants(specs: Iterable[TileSpec]) -> None:
    """Verify CSV contacts, red functionality, and the user-specified seed."""
    specs_by_name = {spec.name: spec for spec in specs}
    functional = functional_tile_names()
    if len(functional) != 25:
        raise AssertionError(f"Expected 25 functional tiles, found {len(functional)}")
    if {f"red{number}" for number in range(1, 5)} - set(functional):
        raise AssertionError("red1--red4 must be functional tiles.")
    if set(SEED_TEMPLATE_POSITIONS) != {"blue2", "blue4", "blue6"}:
        raise AssertionError("Seed must be blue2, blue4, blue6.")

    source = cells()
    for (row, column), name in source.items():
        for direction, dy, dx, opposite in DIRECTIONS:
            neighbour = source.get((row + dy, column + dx))
            if neighbour is None:
                continue
            first = specs_by_name[name].edges[EDGE_INDEX[direction]]
            second = specs_by_name[neighbour].edges[EDGE_INDEX[opposite]]
            if first == NULL_GLUE or first != second:
                raise AssertionError(f"Bad contact: {name}.{direction} -> {neighbour}.{opposite}")


def write_configuration(specs: Iterable[TileSpec], path: Path) -> None:
    """Dump tiles, glues, literal source cells, and seed coordinates as CSV."""
    specs = tuple(specs)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ("record", "name", "role", "north", "east", "south", "west", "strength", "x", "y")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for spec in specs:
            north, east, south, west = spec.edges
            writer.writerow({"record": "tile", "name": spec.name, "role": spec.role,
                             "north": north, "east": east, "south": south, "west": west})
        for left, right, strength in make_glues(specs):
            writer.writerow({"record": "glue", "north": left, "south": right, "strength": strength})
        for (row, column), name in cells().items():
            writer.writerow({"record": "csv_cell", "name": name, "x": column, "y": row})
        for row, column, name in make_seed():
            writer.writerow({"record": "seed", "name": name, "x": column, "y": row})


def write_state(simulation, path: Path) -> None:
    """Dump all occupied lattice sites with rGrow's actual tile names."""
    canvas = simulation.canvas_copy()
    names = list(simulation.tile_names)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("x", "y", "tile_id", "tile_name"))
        writer.writeheader()
        for y, row in enumerate(canvas):
            for x, tile_id in enumerate(row):
                tile_id = int(tile_id)
                if tile_id:
                    name = names[tile_id] if tile_id < len(names) else "UNKNOWN"
                    writer.writerow({"x": x, "y": y, "tile_id": tile_id, "tile_name": name})


def draw_net(simulation, output: Path) -> None:
    """Render the evolving, right-upward net with actual tile labels."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    canvas = simulation.canvas_copy()
    design_colors = {spec.name: spec.color for spec in make_tile_specs()}
    colors = [design_colors.get(str(name), "#000000") for name in simulation.tile_names]
    colors[0] = "#ffffff"
    fig, axis = plt.subplots(figsize=(14, 7), constrained_layout=True)
    axis.imshow(canvas, interpolation="none", cmap=ListedColormap(colors),
                vmin=-0.5, vmax=len(colors) - 0.5, origin="upper")
    names = simulation.name_canvas()
    y0, y1 = max(0, SEED_Y - 18), min(CANVAS_HEIGHT - 1, SEED_Y + 8)
    x0, x1 = max(0, SEED_X - 3), min(CANVAS_WIDTH - 1, SEED_X + 60)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if canvas[y, x]:
                axis.text(x, y, str(names[y, x]).replace("seed_", "s_"),
                          ha="center", va="center", fontsize=5, color="white")
    axis.set_xlim(x0 - 0.5, x1 + 0.5)
    axis.set_ylim(y1 + 0.5, y0 - 0.5)
    axis.set_title("EP-2 CSV net: right-upward growth, aTAM threshold 1")
    axis.set_xlabel("rightward component of growth")
    axis.set_ylabel("upward component of growth")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("atam", "ktam"), default="atam")
    parser.add_argument("--events", type=int, default=2_000)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("protocol2-atam.png"))
    parser.add_argument("--dump-config", type=Path)
    parser.add_argument("--dump-state", type=Path)
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    specs = make_tile_specs()
    assert_design_invariants(specs)
    print("Validated revised CSV: 25 functional tiles (including red1--red4) and 3 blue seed tiles.")
    if args.dump_config:
        write_configuration(specs, args.dump_config)
        print(f"Wrote configuration to {args.dump_config}")
    if args.check_only:
        return
    simulation = make_tileset(args.model).to_simulation()
    simulation.add_state()
    simulation.evolve(for_events=args.events)
    if args.dump_state:
        write_state(simulation, args.dump_state)
        print(f"Wrote state to {args.dump_state}")
    if not args.no_plot:
        draw_net(simulation, args.output)
    print(f"Simulated {simulation.state_events()} events; wrote {args.output}")


if __name__ == "__main__":
    main()
