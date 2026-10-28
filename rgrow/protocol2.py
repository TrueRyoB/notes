#!/usr/bin/env python3
"""Validate the experimental-protocol-2 nanotube net with rGrow's aTAM model.

The protocol CSV is an *unrolled* nanotube.  This program models its logical
assembly as a 4-row strip: green, yellow, and blue are the three two-column
layers, and the four red labels are the complementary edge pairs used when the
strip is folded into a tube.

The design data is intentionally model-neutral.  ``make_tile_specs`` and
``make_glues`` are shared by the aTAM and kTAM factories; only the model
parameters belong in ``make_tileset``.  The default is aTAM at tau=1.

Example
-------
    python protocol2.py --events 2000 --output protocol2-atam.png

The PNG is a planar net.  Its top and bottom red labels identify the edges
that must be hybridized/folded to make the physical nanotube; rGrow's planar
square canvas does not itself create those non-local closure bonds.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


# Geometry read from experimental-protocol-2.md.
TUBE_WIDTH = 4
LAYER_HEIGHT = 2
LAYER_NAMES = ("green", "yellow", "blue")
N_LAYERS = len(LAYER_NAMES)
PERIOD_COLUMNS = LAYER_HEIGHT * N_LAYERS

CANVAS_HEIGHT = TUBE_WIDTH + 4
CANVAS_WIDTH = 160
SEED_X = 4
SEED_Y = 2

NULL_GLUE = "0"
PALETTE = {
    "seed": "#4b5563",
    "green": "#22c55e",
    "yellow": "#eab308",
    "blue": "#2563eb",
}


@dataclass(frozen=True)
class TileSpec:
    """A model-independent tile definition.

    ``edges`` are ordered north, east, south, west, as required by rGrow.
    ``fold_north`` and ``fold_south`` are deliberately separate from ``edges``:
    they are DNA-design/physical-fold information, not planar aTAM bonds.
    """

    name: str
    edges: tuple[str, str, str, str]
    color: str
    layer: str
    row: int
    phase: int
    fold_north: Optional[str] = None
    fold_south: Optional[str] = None


def phase_layer(phase: int) -> str:
    """Return the CSV color band for a column in the six-column period."""
    return LAYER_NAMES[phase // LAYER_HEIGHT]


def horizontal_glue(phase: int, row: int) -> str:
    """Unique directed-context glue from a phase to its successor."""
    return f"h_p{phase}_r{row}"


def vertical_glue(phase: int, upper_row: int) -> str:
    """Glue between adjacent rows in one phase (upper row is named)."""
    return f"v_p{phase}_r{upper_row}"


def fold_pair(row: int) -> str:
    """Name the red CSV edge pair assigned to this circumference position."""
    return f"red{row + 1}"


def make_tile_specs() -> tuple[TileSpec, ...]:
    """Create the seed plus one reusable tile type per period/row context.

    A tile's west glue identifies both its row and previous phase.  Therefore
    every positive-strength tau=1 attachment still has a unique intended tile
    type.  Vertical glues encode the same phase/row context and let completed
    columns be checked as a two-dimensional net.
    """
    specs: list[TileSpec] = []

    # A four-tile seed exposes the first column of the green layer.
    for row in range(TUBE_WIDTH):
        north = NULL_GLUE if row == 0 else vertical_glue(-1, row - 1)
        south = NULL_GLUE if row == TUBE_WIDTH - 1 else vertical_glue(-1, row)
        specs.append(
            TileSpec(
                name=f"seed_r{row}",
                edges=(north, horizontal_glue(0, row), south, NULL_GLUE),
                color=PALETTE["seed"],
                layer="seed",
                row=row,
                phase=-1,
            )
        )

    for phase in range(PERIOD_COLUMNS):
        layer = phase_layer(phase)
        next_phase = (phase + 1) % PERIOD_COLUMNS
        for row in range(TUBE_WIDTH):
            north = NULL_GLUE if row == 0 else vertical_glue(phase, row - 1)
            south = NULL_GLUE if row == TUBE_WIDTH - 1 else vertical_glue(phase, row)
            specs.append(
                TileSpec(
                    name=f"p{phase}_{layer}_r{row}",
                    edges=(
                        north,
                        horizontal_glue(next_phase, row),
                        south,
                        horizontal_glue(phase, row),
                    ),
                    color=PALETTE[layer],
                    layer=layer,
                    row=row,
                    phase=phase,
                    # These are the red1--red4 entries in the supplied CSV.
                    # The red labels repeat along the tube axis.  They are
                    # phase-indexed so the two unrolled boundary edges have
                    # all four complementary labels, as in the CSV.
                    fold_north=fold_pair(phase % TUBE_WIDTH) if row == 0 else None,
                    fold_south=f"{fold_pair(phase % TUBE_WIDTH)}*" if row == TUBE_WIDTH - 1 else None,
                )
            )
    return tuple(specs)


def make_glues(specs: Iterable[TileSpec]) -> list[tuple[str, str, float]]:
    """Return unit-strength self-pairing rGrow glues for the planar net."""
    names = sorted({edge for spec in specs for edge in spec.edges if edge != NULL_GLUE})
    return [(name, name, 1.0) for name in names]


def make_seed() -> list[tuple[int, int, str]]:
    """Put the four-tile seed in a single vertical column."""
    return [(SEED_Y + row, SEED_X, f"seed_r{row}") for row in range(TUBE_WIDTH)]


def make_tileset(model: str = "atam"):
    """Build an rGrow tile set, retaining the same design for kTAM.

    The aTAM values are the requested logical validation: every non-null bond
    has strength 1 and an attachment threshold tau=1.  kTAM uses the same
    ``Tile`` objects, glues, and seed but requires experimentally calibrated
    kinetic values, so they are exposed as explicit placeholders rather than
    silently pretending to be experimental parameters.
    """
    # Deferred so --check-only is useful on a machine that has not installed
    # rGrow yet.
    from rgrow import Tile, TileSet

    specs = make_tile_specs()
    tiles = [Tile(list(spec.edges), name=spec.name, color=spec.color) for spec in specs]
    shared = dict(
        tiles=tiles,
        glues=make_glues(specs),
        seed=make_seed(),
        size=(CANVAS_HEIGHT, CANVAS_WIDTH),
        canvas_type="Square",
    )
    if model == "atam":
        return TileSet(**shared, model="atam", tau=1.0)
    if model == "ktam":
        # Replace gse/gmc with measurements before making kinetic claims.
        return TileSet(**shared, model="ktam", gse=8.0, gmc=16.0, alpha=1.0)
    raise ValueError(f"Unknown model {model!r}; choose 'atam' or 'ktam'.")


def assert_design_invariants(specs: Iterable[TileSpec]) -> None:
    """Fail early if a later edit breaks the CSV geometry or tau=1 routing."""
    specs = tuple(specs)
    active = [spec for spec in specs if spec.phase >= 0]
    assert len(active) == TUBE_WIDTH * PERIOD_COLUMNS
    assert {spec.layer for spec in active} == set(LAYER_NAMES)
    assert all(spec.edges.count(NULL_GLUE) <= 2 for spec in active)

    # Each exposed horizontal glue has exactly one intended receiving tile.
    for phase in range(PERIOD_COLUMNS):
        for row in range(TUBE_WIDTH):
            glue = horizontal_glue(phase, row)
            receivers = [spec for spec in specs if spec.edges[3] == glue]
            if len(receivers) != 1:
                raise AssertionError(f"{glue} has {len(receivers)} west-side receivers")

    # Fold labels form four complementary pairs, and never become planar bonds.
    north = {spec.fold_north for spec in active if spec.fold_north}
    south = {spec.fold_south for spec in active if spec.fold_south}
    expected = {fold_pair(row) for row in range(TUBE_WIDTH)}
    if north != expected or south != {f"{name}*" for name in expected}:
        raise AssertionError("The four red fold-edge pairs are incomplete.")


def draw_net(simulation, output: Path) -> None:
    """Write a readable aTAM-state visual with the four fold labels."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    canvas = simulation.canvas_copy()
    # rGrow versions differ on whether ``tile_colors`` returns CSS colors or
    # 0--255 RGBA tuples.  Use the design palette keyed by tile name instead,
    # so rendering is independent of that representation.  Tile number zero
    # is the empty canvas; rGrow's tile numbers start at one.
    design_color = {spec.name: spec.color for spec in make_tile_specs()}
    colors = ["#ffffff"] + [
        design_color.get(str(tile_name), "#000000")
        for tile_name in simulation.tile_names
    ]
    fig, axis = plt.subplots(figsize=(14, 4.5), constrained_layout=True)
    axis.imshow(canvas, interpolation="none", cmap=ListedColormap(colors), origin="upper")
    axis.set_title("EP-2 nanotube net: aTAM, $\\tau=1$ (unrolled before folding)")
    axis.set_xlabel("growth direction: repeated green / yellow / blue 2-column layers")
    axis.set_ylabel("tube circumference (4 tiles)")
    axis.set_yticks([SEED_Y + row for row in range(TUBE_WIDTH)], labels=[str(row + 1) for row in range(TUBE_WIDTH)])
    axis.set_xlim(SEED_X - 1.5, min(CANVAS_WIDTH - 1, SEED_X + 48))
    axis.set_ylim(SEED_Y + TUBE_WIDTH + 1.2, SEED_Y - 1.2)
    for column in range(SEED_X + 1, SEED_X + 49):
        phase = (column - SEED_X - 1) % PERIOD_COLUMNS
        label = fold_pair(phase % TUBE_WIDTH)
        axis.text(column, SEED_Y - 0.36, label, color="#dc2626", ha="center", va="bottom", fontsize=6)
        axis.text(column, SEED_Y + TUBE_WIDTH + 0.36, f"{label}*", color="#dc2626", ha="center", va="top", fontsize=6)
    axis.text(
        0.5,
        -0.22,
        "Red labels are the complementary fold-edge pairs from the CSV; they are metadata, not planar aTAM glues.",
        transform=axis.transAxes,
        ha="center",
        va="top",
        fontsize=9,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("atam", "ktam"), default="atam")
    parser.add_argument("--events", type=int, default=2_000, help="attachment/detachment events to simulate")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("protocol2-atam.png"),
        help="PNG path for the unrolled-net visualization",
    )
    parser.add_argument("--check-only", action="store_true", help="validate the reusable design without importing/running rGrow")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    specs = make_tile_specs()
    assert_design_invariants(specs)
    print(f"Validated {len(specs)} tile types: 4-wide, 2-column layers, 3 layers, four fold pairs.")
    if args.check_only:
        return
    tileset = make_tileset(args.model)
    simulation = tileset.to_simulation()
    # ``to_simulation`` creates the system but, in current rGrow releases,
    # does not create an assembly state.  The state is where the TileSet seed
    # is placed, so it must exist before evolve() can address state 0.
    simulation.add_state()
    simulation.evolve(for_events=args.events)
    draw_net(simulation, args.output)
    print(f"Simulated {simulation.state_events()} events with {args.model}; wrote {args.output}")


if __name__ == "__main__":
    main()
