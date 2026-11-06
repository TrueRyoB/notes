# purpose
Sophisticate aTAM

# additional goal

- even more accurate config for aTAM
    - 12 circumference helix configuration
    - repeating 5 layers
    - threshold to 2 
    - kind=Tube to force the fixed width constraint

# deliverable
    - code that can be reused for kTAM
    - visualization


```python
#!/usr/bin/env python3
"""Simulate the EP-3 five-layer, 12-circumference helical nanotube in rGrow.

The configuration is generated rather than inferred from the old EP-2 CSV:
five axial layers, each with twelve circumferential positions, give 60
functional tile types. A black diagonal seed supplies the west and south
contacts required to bootstrap cooperative right-upward growth at threshold 2.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


CIRCUMFERENCE = 12
LAYER_COUNT = 5
CANVAS_HEIGHT = CIRCUMFERENCE
CANVAS_WIDTH = 160
SEED_X = 5
THRESHOLD = 2.0
NULL_GLUE = "0"
LAYER_PALETTE = ("#2563eb", "#22c55e", "#eab308", "#f97316", "#a855f7")
SEED_COLOR = "#000000"
EDGE_INDEX = {"N": 0, "E": 1, "S": 2, "W": 3}


@dataclass(frozen=True)
class TileSpec:
    """Model-neutral tile; edges are north, east, south, west."""

    name: str
    edges: Tuple[str, str, str, str]
    color: str
    role: str
    layer: int | None = None
    position: int | None = None
    seed_only: bool = False


def tile_name(layer: int, position: int) -> str:
    return f"layer{layer + 1}_{position + 1:02d}"


def horizontal_glue(layer: int, position: int) -> str:
    return f"h_l{layer % LAYER_COUNT}_p{position % CIRCUMFERENCE:02d}"


def vertical_glue(layer: int, position: int) -> str:
    return f"v_l{layer % LAYER_COUNT}_p{position % CIRCUMFERENCE:02d}"


def functional_edges(layer: int, position: int) -> Tuple[str, str, str, str]:
    """Return a tile whose west and south neighbours bind at tau=2.

    At ``(row, column)``, the intended tile is layer ``column mod 5`` and
    position ``row - column mod 12``. This is a right-upward helix on a tube.
    """
    return (
        vertical_glue(layer, position - 1),
        horizontal_glue(layer, position),
        vertical_glue(layer, position),
        horizontal_glue(layer - 1, position + 1),
    )


def seed_edges(index: int) -> Tuple[str, str, str, str]:
    """One-way seed edges for the diagonal right-upward bootstrap front."""
    bootstrap_position = (-SEED_X - 1) % CIRCUMFERENCE
    target_layer_for_east = (SEED_X + index + 1) % LAYER_COUNT
    target_layer_for_north = (SEED_X + index) % LAYER_COUNT
    return (
        vertical_glue(target_layer_for_north, bootstrap_position),
        horizontal_glue(target_layer_for_east - 1, bootstrap_position + 1),
        NULL_GLUE,
        NULL_GLUE,
    )


def make_tile_specs() -> Tuple[TileSpec, ...]:
    """Create 60 functional (5 x 12) tiles and 12 black seed variants."""
    functional = tuple(
        TileSpec(tile_name(layer, position), functional_edges(layer, position),
                 LAYER_PALETTE[layer], "functional", layer, position)
        for layer in range(LAYER_COUNT)
        for position in range(CIRCUMFERENCE)
    )
    seeds = tuple(
        TileSpec(f"seed_{index + 1:02d}", seed_edges(index), SEED_COLOR,
                 "seed", seed_only=True)
        for index in range(CIRCUMFERENCE)
    )
    return functional + seeds


def make_glues(specs: Iterable[TileSpec]) -> List[Tuple[str, str, float]]:
    """All generated glues self-pair with unit strength."""
    names = sorted({edge for spec in specs for edge in spec.edges if edge != NULL_GLUE})
    return [(name, name, 1.0) for name in names]


def make_seed() -> List[Tuple[int, int, str]]:
    """Place 12 black tiles on one lower-left to upper-right helix turn."""
    return [(index, SEED_X + index, f"seed_{index + 1:02d}")
            for index in range(CIRCUMFERENCE)]


def expected_tile_name(row: int, column: int) -> str:
    return tile_name(column % LAYER_COUNT, (row - column) % CIRCUMFERENCE)


def make_tileset(model: str = "atam"):
    """Build the shared Tube topology for either aTAM or kTAM."""
    from rgrow import Tile, TileSet

    specs = make_tile_specs()
    shared = dict(
        tiles=[Tile(list(spec.edges), name=spec.name, color=spec.color) for spec in specs],
        glues=make_glues(specs),
        seed=make_seed(),
        size=(CANVAS_HEIGHT, CANVAS_WIDTH),
        canvas_type="Tube",
    )
    if model == "atam":
        return TileSet(**shared, model="atam", threshold=THRESHOLD)
    if model == "ktam":
        return TileSet(**shared, model="ktam", gse=8.0, gmc=16.0, alpha=1.0)
    raise ValueError(f"Unknown model {model!r}")


def assert_design_invariants(specs: Iterable[TileSpec]) -> None:
    """Verify the requested 5x12 Tube and cooperative diagonal seed."""
    specs_by_name = {spec.name: spec for spec in specs}
    functional = [spec for spec in specs if not spec.seed_only]
    seeds = [spec for spec in specs if spec.seed_only]
    if CIRCUMFERENCE != 12 or LAYER_COUNT != 5:
        raise AssertionError("EP-3 requires exactly 5 layers at circumference 12.")
    if len(functional) != LAYER_COUNT * CIRCUMFERENCE:
        raise AssertionError("Expected 60 functional tiles (5 layers x 12 positions).")
    if len(seeds) != CIRCUMFERENCE or any(seed.color != SEED_COLOR for seed in seeds):
        raise AssertionError("Expected 12 black seed tile variants.")
    if len(make_seed()) != CIRCUMFERENCE:
        raise AssertionError("Seed must cover one 12-cell circumference.")
    if any(column >= CANVAS_WIDTH for _row, column, _name in make_seed()):
        raise AssertionError("Seed exceeds the open growth axis.")

    # Contacts are correct around the wrapped circumference and along all five
    # layers of the repeating helix.
    for row in range(CIRCUMFERENCE):
        for column in range(LAYER_COUNT):
            here = specs_by_name[expected_tile_name(row, column)]
            south = specs_by_name[expected_tile_name(row + 1, column)]
            east = specs_by_name[expected_tile_name(row, column + 1)]
            if here.edges[EDGE_INDEX["S"]] != south.edges[EDGE_INDEX["N"]]:
                raise AssertionError("Broken circumferential contact.")
            if here.edges[EDGE_INDEX["E"]] != east.edges[EDGE_INDEX["W"]]:
                raise AssertionError("Broken axial contact.")

    # Adjacent diagonal seed tiles expose the west and south contacts of the
    # right-upward target, so attachment starts cooperatively at threshold 2.
    seed = make_seed()
    for index in range(CIRCUMFERENCE - 1):
        row, column, seed_name = seed[index]
        south_row, south_column, south_seed_name = seed[index + 1]
        target = specs_by_name[expected_tile_name(row, column + 1)]
        west_seed = specs_by_name[seed_name]
        south_seed = specs_by_name[south_seed_name]
        if (south_row != row + 1 or south_column != column + 1
                or target.edges[EDGE_INDEX["W"]] != west_seed.edges[EDGE_INDEX["E"]]
                or target.edges[EDGE_INDEX["S"]] != south_seed.edges[EDGE_INDEX["N"]]):
            raise AssertionError("Diagonal seed cannot bootstrap right-upward tau=2 growth.")


def write_configuration(specs: Iterable[TileSpec], path: Path) -> None:
    """Write all tiles, glues, and seed coordinates to CSV."""
    specs = tuple(specs)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ("record", "name", "role", "color", "layer", "position", "north", "east", "south", "west", "strength", "x", "y")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for spec in specs:
            north, east, south, west = spec.edges
            writer.writerow({"record": "tile", "name": spec.name, "role": spec.role,
                             "color": spec.color,
                             "layer": spec.layer, "position": spec.position,
                             "north": north, "east": east, "south": south, "west": west})
        for left, right, strength in make_glues(specs):
            writer.writerow({"record": "glue", "north": left, "south": right, "strength": strength})
        for row, column, name in make_seed():
            writer.writerow({"record": "seed", "name": name, "x": column, "y": row})


def write_state(simulation, path: Path) -> None:
    """Dump occupied lattice sites using rGrow's actual tile names."""
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
    """Render the full wrapped circumference and right-upward helix."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    canvas = simulation.canvas_copy()
    design_colors = {spec.name: spec.color for spec in make_tile_specs()}
    colors = [design_colors.get(str(name), "#000000") for name in simulation.tile_names]
    colors[0] = "#ffffff"
    fig, axis = plt.subplots(figsize=(14, 4), constrained_layout=True)
    axis.imshow(canvas, interpolation="none", cmap=ListedColormap(colors),
                vmin=-0.5, vmax=len(colors) - 0.5, origin="upper", aspect="auto")
    names = simulation.name_canvas()
    x0, x1 = max(0, SEED_X - 2), min(CANVAS_WIDTH - 1, SEED_X + 60)
    for y in range(CANVAS_HEIGHT):
        for x in range(x0, x1 + 1):
            if canvas[y, x]:
                label = str(names[y, x]).replace("layer", "L").replace("seed_", "s")
                axis.text(x, y, label, ha="center", va="center", fontsize=4, color="white")
    axis.set_xlim(x0 - 0.5, x1 + 0.5)
    axis.set_ylim(CANVAS_HEIGHT - 0.5, -0.5)
    axis.set_title("EP-3 nanotube: 5 layers x 12 circumference, Tube, aTAM threshold 2")
    axis.set_xlabel("rightward growth axis")
    axis.set_ylabel("wrapped 12-cell circumference")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("atam", "ktam"), default="atam")
    parser.add_argument("--events", type=int, default=2_000)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("protocol3-atam.png"))
    parser.add_argument("--dump-config", type=Path)
    parser.add_argument("--dump-state", type=Path)
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    specs = make_tile_specs()
    assert_design_invariants(specs)
    print("Validated EP-3: 60 functional tiles (5 layers x 12 positions), "
          "12 black diagonal seed tiles, Tube canvas, threshold 2.")
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

```