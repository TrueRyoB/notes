#!/usr/bin/env python3
"""Run the CSV's 12-wide, right-growing ribbon in the H00/H01/H10 controls.

Tile types a-o encode the seed and the top/interior/bottom tiles in columns
A, B, C, and D. H00 enables all tiles; H01 enables the seed, A, and B; H10
enables the seed, C, and D. All models use the same tile definitions and glue
matching. Each is held for two hours at 41/47 C for six cycles.

The CSV specifies sticky-end lengths and adjacency, but not actual sequences
or absolute concentrations. Representative sequences and concentration per
tile appearance are explicit assumptions and must be replaced/calibrated for
quantitative experimental predictions.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rgrow import State
from rgrow.kblock import KBlock, KBlockParams, KBlockTile
from rgrow.rgrow import string_dna_dg_ds


# Geometry from the supplied tile-configuration CSV.
RIBBON_WIDTH = 12  # one seed column: top cap + 10 interior + bottom cap
HOLD_TEMPERATURES_C = (41.0, 47.0)
HOLD_SECONDS = 2 * 60 * 60
REPEATS = 6

# The CSV specifies relative tile appearances, not absolute concentrations.
# This uses 100 nM per appearance as an explicit placeholder baseline.
CONCENTRATION_PER_APPEARANCE_M = 100e-9
SEED_TILE_CONCENTRATION_M = 0.0
BLOCKER_CONCENTRATION_M = 1_000e-9
SEGMENT_1_DOMAIN_BP = 10
SEGMENT_2_DOMAIN_BP = 9

# The CSV's columns are the seed, A, B, C, D, then A continuing the cycle.
# A = segment 1, B = interface 1, C = segment 2, D = interface 2.
SEED_TILES = {"a", "b", "c"}
SEGMENT_1_TILES = {"d", "e", "f"}
INTERFACE_1_TILES = {"g", "h", "i"}
SEGMENT_2_TILES = {"j", "k", "l"}
INTERFACE_2_TILES = {"m", "n", "o"}
MODEL_TILE_SETS = {
    "H00": SEED_TILES | SEGMENT_1_TILES | INTERFACE_1_TILES | SEGMENT_2_TILES | INTERFACE_2_TILES,
    "H01": SEED_TILES | SEGMENT_1_TILES | INTERFACE_1_TILES,
    # Controls only change tile availability. They retain the CSV's exact
    # seed and adjacency; no tile glues are rewritten for a control.
    "H10": SEED_TILES | SEGMENT_2_TILES | INTERFACE_2_TILES,
}

TILE_ROLE_BY_NAME = {
    "a": ("seed", "top"), "b": ("seed", "middle"), "c": ("seed", "bottom"),
    "d": ("A", "top"), "e": ("A", "middle"), "f": ("A", "bottom"),
    "g": ("B", "top"), "h": ("B", "middle"), "i": ("B", "bottom"),
    "j": ("C", "top"), "k": ("C", "middle"), "l": ("C", "bottom"),
    "m": ("D", "top"), "n": ("D", "middle"), "o": ("D", "bottom"),
}
# Counts in the CSV's displayed seed,A,B,C,D,A-continuation layout. Interior
# tiles occur ten times per column; the A tile types occur in both A columns.
TILE_APPEARANCE_COUNTS = {
    "d": 1, "e": 10, "f": 1,
    "g": 1, "h": 10, "i": 1,
    "j": 1, "k": 10, "l": 1,
    "m": 1, "n": 10, "o": 1,
}
# The CSV gives sticky-end lengths, not sequences. These representative
# sequences preserve 9/10 nt lengths for temperature-dependent energies, but
# are placeholders and do not provide sequence-specific validation.
DOMAIN_SEQUENCES = {
    9: ("ACTGCTAGT", "GATCGTACG"),
    10: ("ACTGCTAGTA", "GATCGTACGA"),
}

# The seed is placed near the left edge; its right-facing edge initiates growth
# to the right. A finite open canvas avoids periodic wraparound.
CANVAS_LENGTH = 4_096
SEED_COLUMN = 32


def make_binding_sequences() -> dict[str, str]:
    """Assign sequence energies to unique glue identities of the CSV design."""
    seq9 = DOMAIN_SEQUENCES[9][0]
    seq10 = DOMAIN_SEQUENCES[10][0]
    glues: dict[str, str] = {}
    for row in ("top", "middle", "bottom"):
        glues[f"da_{row}"] = seq10  # seed or D -> A
        glues[f"ab_{row}"] = seq10  # A -> B
        glues[f"bc_{row}"] = seq9   # B -> C
        glues[f"cd_{row}"] = seq9   # C -> D
    for role in ("seed", "A", "B", "C", "D"):
        glues[f"v_{role}"] = seq9
    return glues


def tile_glues(tile_name: str) -> tuple[str, str, str, str]:
    """Return (north, east, south, west) glues for one CSV tile type."""
    role, row = TILE_ROLE_BY_NAME[tile_name]
    vertical = f"v_{role}"
    north = "null" if row == "top" else f"{vertical}*"
    south = "null" if row == "bottom" else vertical
    row_suffix = row

    # H00's D->A glue is also used by seed->A. Thus the same A tile type d/e/f
    # works at both appearances shown in the CSV.
    right_glue = {
        "seed": "da",
        "A": "ab",
        "B": "bc",
        "C": "cd",
        "D": "da",
    }[role]
    left_glue = {
        "seed": "null",
        "A": "da*",
        "B": "ab*",
        "C": "bc*",
        "D": "cd*",
    }[role]
    east = "null" if right_glue == "null" else f"{right_glue}_{row_suffix}"
    west = "null" if left_glue == "null" else f"{left_glue.rstrip('*')}_{row_suffix}" + ("*" if left_glue.endswith("*") else "")
    return north, east, south, west


def make_system(
    model_name: str,
    tile_concentration_scale: float,
) -> KBlock:
    """Build an H model; inactive tile types retain zero concentration."""
    binding_sequences = make_binding_sequences()
    tile_defs = tuple(
        (name, tile_glues(name), color)
        for (name, color) in zip(
            TILE_ROLE_BY_NAME,
            ("purple", "purple", "purple", "red", "red", "red", "blue", "blue", "blue", "green", "green", "green", "orange", "orange", "orange"),
        )
    )
    tiles = [
        KBlockTile(
            name,
            (
                (
                    SEED_TILE_CONCENTRATION_M
                    if name in SEED_TILES
                    else CONCENTRATION_PER_APPEARANCE_M * TILE_APPEARANCE_COUNTS[name]
                ) * tile_concentration_scale
                if name in MODEL_TILE_SETS[model_name]
                else 0.0
            ),
            glues,
            color,
        )
        for name, glues, color in tile_defs
    ]

    params = KBlockParams(
        tiles=tiles,
        blocker_conc={glue_name: BLOCKER_CONCENTRATION_M for glue_name in binding_sequences},
        seed={
            (row, SEED_COLUMN): tile_name
            for row, tile_name in enumerate(("a", *(["b"] * 10), "c"))
        },
        binding_strength=binding_sequences,
        temp=HOLD_TEMPERATURES_C[0],
        no_partially_blocked_attachments=True,
    )
    return KBlock(params)


def ribbon_length(state: State) -> int:
    """Count contiguous, fully occupied 12-tile columns from the seed rightward."""
    canvas = state.canvas_view
    length = 0
    for column in range(SEED_COLUMN, CANVAS_LENGTH):
        if not np.all(canvas[:, column] != 0):
            break
        length += 1
    return length


def set_hold_temperature(
    system: KBlock,
    state: State,
    temperature_c: float,
    binding_sequences: dict[str, str],
) -> None:
    """Update both temperature and each sequence-derived glue energy."""
    system.temperature = temperature_c
    glue_links = np.array(system.glue_links, copy=True)
    glue_names = system.bond_names
    for glue_name, sequence in binding_sequences.items():
        dg_37, ds = string_dna_dg_ds(sequence)
        dg_at_temperature = float(dg_37) - (temperature_c - 37.0) * float(ds)
        glue_index = glue_names.index(glue_name)
        inverse_index = glue_names.index(f"{glue_name}*")
        glue_links[glue_index, inverse_index] = dg_at_temperature
        glue_links[inverse_index, glue_index] = dg_at_temperature
    # Setting glue_links refreshes KBlock's energy caches; update_state refreshes
    # the event rates attached to this existing assembly.
    system.glue_links = glue_links
    system.update_state(state)


def run_model(
    model_name: str,
    tile_concentration_scale: float,
) -> list[dict[str, object]]:
    binding_sequences = make_binding_sequences()
    system = make_system(model_name, tile_concentration_scale)
    state = State((RIBBON_WIDTH, CANVAS_LENGTH), "Square", "None")
    system.setup_state(state)
    system.update_state(state)

    rows: list[dict[str, object]] = []
    previous_length = ribbon_length(state)
    initial_length = previous_length
    current_temperature = HOLD_TEMPERATURES_C[0]
    for cycle in range(1, REPEATS + 1):
        for hold_index, temperature_c in enumerate(HOLD_TEMPERATURES_C, start=1):
            # KBlock.temperature is a settable Celsius parameter. The same
            # assembly continues across instantaneous temperature transitions.
            if temperature_c != current_temperature:
                set_hold_temperature(system, state, temperature_c, binding_sequences)
                current_temperature = temperature_c
            hold_number = (cycle - 1) * len(HOLD_TEMPERATURES_C) + hold_index - 1
            hold_start_hours = hold_number * HOLD_SECONDS / 3600.0
            system.evolve(state, for_time=HOLD_SECONDS)
            canvas = state.canvas_view
            if np.any(canvas[:, -1]):
                raise RuntimeError(
                    f"{model_name} reached the canvas edge during cycle {cycle}; "
                    "increase CANVAS_LENGTH before trusting this trajectory."
                )
            current_length = ribbon_length(state)
            # Divide by the prescribed hold duration, including a zero-event
            # hold where rgrow may return early because no events are possible.
            growth_rate = (current_length - previous_length) / (HOLD_SECONDS / 3600.0)
            rows.append(
                {
                    "model": model_name,
                    "tile_concentration_scale": tile_concentration_scale,
                    "segment_1_domain_bp": SEGMENT_1_DOMAIN_BP,
                    "segment_2_domain_bp": SEGMENT_2_DOMAIN_BP,
                    "cycle": cycle,
                    "hold_in_cycle": hold_index,
                    "temperature_c": temperature_c,
                    "hold_seconds": HOLD_SECONDS,
                    "hold_start_hours": hold_start_hours,
                    "hold_end_hours": hold_start_hours + HOLD_SECONDS / 3600.0,
                    "elapsed_hours": hold_start_hours + HOLD_SECONDS / 3600.0,
                    "rgrow_state_time_hours": state.time / 3600.0,
                    "ribbon_length_columns": current_length,
                    "growth_columns": current_length - initial_length,
                    "growth_rate_columns_per_hour": growth_rate,
                    "tile_count": state.n_tiles,
                    "event_count": state.total_events,
                }
            )
            print(
                f"{model_name:>3} | cycle {cycle}/{REPEATS} | "
                f"{temperature_c:g} C | {state.time / 3600:.1f} h | "
                f"length {current_length} complete columns | "
                f"rate {growth_rate if growth_rate != '' else 'n/a'} columns/h",
                flush=True,
            )
            previous_length = current_length
    return rows


def add_growth_sum_prediction(rows: list[dict[str, object]]) -> None:
    """Attach cumulative and per-hold residuals for G(H00)=G(H01)+G(H10)."""
    by_timeline: dict[tuple[int, int], dict[str, dict[str, object]]] = {}
    for row in rows:
        key = (int(row["cycle"]), int(row["hold_in_cycle"]))
        by_timeline.setdefault(key, {})[str(row["model"])] = row

    for models in by_timeline.values():
        h00, h01, h10 = models["H00"], models["H01"], models["H10"]
        component_growth = float(h01["growth_columns"]) + float(h10["growth_columns"])
        h00["H01_plus_H10_growth_columns"] = component_growth
        h00["H00_minus_component_growth_columns"] = float(h00["growth_columns"]) - component_growth
        rates = [
            models[name]["growth_rate_columns_per_hour"]
            for name in ("H00", "H01", "H10")
        ]
        if all(rate != "" for rate in rates):
            component_rate = float(rates[1]) + float(rates[2])
            h00["H01_plus_H10_rate_columns_per_hour"] = component_rate
            h00["H00_minus_component_rate_columns_per_hour"] = float(rates[0]) - component_rate
        else:
            h00["H01_plus_H10_rate_columns_per_hour"] = ""
            h00["H00_minus_component_rate_columns_per_hour"] = ""


def plot_number(value: object) -> float:
    """Convert a measured value for plotting, preserving unavailable rates as gaps."""
    return float("nan") if value == "" else float(value)


def write_csv(rows: Iterable[dict[str, object]], path: Path) -> None:
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_plot(rows: list[dict[str, object]], path: Path) -> None:
    """Save prediction and per-hold growth rates in an easy-to-check figure."""
    models = {
        name: sorted(
            (row for row in rows if row["model"] == name),
            key=lambda row: (int(row["cycle"]), int(row["hold_in_cycle"])),
        )
        for name in MODEL_TILE_SETS
    }
    h00, h01, h10 = models["H00"], models["H01"], models["H10"]
    x = [float(row["elapsed_hours"]) for row in h00]
    predicted = [float(row["H01_plus_H10_growth_columns"]) for row in h00]

    fig, (growth_ax, rate_ax, residual_ax) = plt.subplots(
        3, 1, figsize=(13, 12), constrained_layout=True, sharex=False
    )
    fig.suptitle(
        f"TP-EP-1 diagnostic: tile concentrations at {h00[0]['tile_concentration_scale']:g}x nominal",
        fontsize=14,
    )
    temp_colors = {41.0: "#dbeafe", 47.0: "#ffedd5"}
    for row in h00:
        x0 = float(row["hold_start_hours"])
        x1 = float(row["hold_end_hours"])
        growth_ax.axvspan(
            x0,
            x1,
            color=temp_colors[float(row["temperature_c"])],
            alpha=0.45,
            linewidth=0,
        )

    h00_growth = [float(r["growth_columns"]) for r in h00]
    h01_growth = [float(r["growth_columns"]) for r in h01]
    h10_growth = [float(r["growth_columns"]) for r in h10]
    growth_ax.plot([0.0, *x], [0.0, *h00_growth], "o-", label="H00 measured")
    growth_ax.plot([0.0, *x], [0.0, *predicted], "s--", label="H01 + H10 predicted")
    growth_ax.plot([0.0, *x], [0.0, *h01_growth], ":", label="H01 measured", alpha=0.8)
    growth_ax.plot([0.0, *x], [0.0, *h10_growth], ":", label="H10 measured", alpha=0.8)
    growth_ax.set_title("Cumulative ribbon growth at each hold boundary")
    growth_ax.set_ylabel("Growth (complete 12-tile columns)")
    growth_ax.grid(True, alpha=0.25)
    growth_ax.legend(ncol=2)

    labels = [f"{int(r['cycle'])}\n{float(r['temperature_c']):g} C" for r in h00]
    positions = np.arange(len(h00))
    width = 0.19
    h00_rates = [plot_number(r["growth_rate_columns_per_hour"]) for r in h00]
    h01_rates = [plot_number(r["growth_rate_columns_per_hour"]) for r in h01]
    h10_rates = [plot_number(r["growth_rate_columns_per_hour"]) for r in h10]
    summed_rates = [plot_number(r["H01_plus_H10_rate_columns_per_hour"]) for r in h00]
    rate_ax.bar(positions - 1.5 * width, h00_rates, width, label="H00 measured")
    rate_ax.bar(positions - 0.5 * width, h01_rates, width, label="H01 measured")
    rate_ax.bar(positions + 0.5 * width, h10_rates, width, label="H10 measured")
    rate_ax.bar(positions + 1.5 * width, summed_rates, width, label="H01 + H10 predicted")
    rate_ax.set_title("Growth rate during each two-hour temperature hold")
    rate_ax.set_ylabel("Growth rate (complete columns/hour)")
    rate_ax.set_xticks(positions, labels)
    rate_ax.grid(True, axis="y", alpha=0.25)
    rate_ax.legend()

    rate_residuals = [plot_number(r["H00_minus_component_rate_columns_per_hour"]) for r in h00]
    residual_ax.bar(positions, rate_residuals, color=[
        "#9ca3af" if np.isnan(value) else "#2563eb" if value >= 0 else "#dc2626"
        for value in rate_residuals
    ])
    residual_ax.axhline(0, color="black", linewidth=1)
    residual_ax.set_title("Prediction residual: H00 - (H01 + H10)")
    residual_ax.set_ylabel("Rate residual (complete columns/hour)")
    residual_ax.set_xlabel("Cycle and hold temperature")
    residual_ax.set_xticks(positions, labels)
    residual_ax.grid(True, axis="y", alpha=0.25)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("tp-ep-1-results.csv"),
        help="CSV path for length measurements (default: next to this script)",
    )
    parser.add_argument(
        "--figure",
        type=Path,
        help="PNG path for the prediction plot (default: CSV path with .png suffix)",
    )
    parser.add_argument(
        "--tile-concentration-scale",
        type=float,
        default=1.0,
        help="scale active tile concentrations (suggested calibration grid: 0.5, 1, 2; default: 1)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    all_rows: list[dict[str, object]] = []
    for model_name in MODEL_TILE_SETS:
        all_rows.extend(
            run_model(
                model_name,
                args.tile_concentration_scale,
            )
        )
    add_growth_sum_prediction(all_rows)
    write_csv(all_rows, args.output)
    figure_path = args.figure or args.output.with_suffix(".png")
    write_plot(all_rows, figure_path)
    print(f"Wrote {len(all_rows)} hold measurements to {args.output}")
    print(f"Wrote prediction plot to {figure_path}")


if __name__ == "__main__":
    main()
