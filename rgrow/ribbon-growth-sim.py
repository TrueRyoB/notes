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
from datetime import datetime
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
HOLD_TEMPERATURES_C = (43.0, 47.0)
HOLD_SECONDS = 2 * 60 * 60
# Split each hold into bounded simulation intervals so long evolve calls can
# report progress while preserving the continuous state between intervals.
PROGRESS_INTERVAL_SECONDS = 10 * 60
# Record five equally spaced observations in each two-hour temperature hold.
MEASUREMENTS_PER_HOLD = 5
MEASUREMENT_INTERVAL_SECONDS = HOLD_SECONDS // MEASUREMENTS_PER_HOLD
REPEATS = 2

# The CSV specifies relative tile appearances, not absolute concentrations.
# This uses 100 nM per appearance as an explicit placeholder baseline.
CONCENTRATION_PER_APPEARANCE_M = 100e-9
SEED_TILE_CONCENTRATION_M = 0.0
BLOCKER_CONCENTRATION_M = 1_000e-9
SEGMENT_1_DOMAIN_BP = 10
SEGMENT_2_DOMAIN_BP = 11

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
    "H10": SEED_TILES | SEGMENT_2_TILES | INTERFACE_2_TILES,
}

TILE_ROLE_BY_NAME = {
    "a": ("seed", "top"), "b": ("seed", "middle"), "c": ("seed", "bottom"),
    "d": ("A", "top"), "e": ("A", "middle"), "f": ("A", "bottom"),
    "g": ("B", "top"), "h": ("B", "middle"), "i": ("B", "bottom"),
    "j": ("C", "top"), "k": ("C", "middle"), "l": ("C", "bottom"),
    "m": ("D", "top"), "n": ("D", "middle"), "o": ("D", "bottom"),
}
# Counts in the CSV's displayed seed,A,B,C,D,A-continuation layout. 
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
# 4,096 is considered the safe limit as of this experiemnt
CANVAS_LENGTH = 4_096
SEED_COLUMN = 32
# Square canvases reserve two cells at each edge.  Keep the 12-tile ribbon
# inside that usable region.
CANVAS_MARGIN = 2
RIBBON_ROW_START = CANVAS_MARGIN
CANVAS_HEIGHT = RIBBON_WIDTH + 2 * CANVAS_MARGIN
LAST_USABLE_COLUMN = CANVAS_LENGTH - CANVAS_MARGIN - 1


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


def make_blocker_concentrations(
    tile_concentration_scale: float,
) -> dict[str, float]:
    """Give every non-null directed tile edge its own blocker strand.

    KBlock models blockers as independent strands that bind a single exposed
    glue.  Supplying both a glue and its ``*`` complement gives the north,
    east, south, and west orientations separate matching blockers.  Each tile
    receives blockers on all of its non-null edges, and therefore on at least
    two edges.  The common scale factor preserves the blocker-to-tile ratio
    when ``--tile-concentration-scale`` changes.
    """
    blocker_glues = {
        glue
        for tile_name in TILE_ROLE_BY_NAME
        for glue in tile_glues(tile_name)
        if glue != "null"
    }
    blockers_per_tile = {
        tile_name: sum(glue != "null" for glue in tile_glues(tile_name))
        for tile_name in TILE_ROLE_BY_NAME
    }
    if min(blockers_per_tile.values()) < 2:
        raise ValueError("Every tile must have blockers on at least two edges.")
    return {
        glue: BLOCKER_CONCENTRATION_M * tile_concentration_scale
        for glue in blocker_glues
    }


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
        blocker_conc=make_blocker_concentrations(tile_concentration_scale),
        seed={
            (RIBBON_ROW_START + row, SEED_COLUMN): tile_name
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
        ribbon_column = canvas[
            RIBBON_ROW_START:RIBBON_ROW_START + RIBBON_WIDTH,
            column,
        ]
        if not np.all(ribbon_column != 0):
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
    state = State((CANVAS_HEIGHT, CANVAS_LENGTH), "Square", "None")
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
            progressed_seconds = 0
            previous_measurement_seconds = 0
            next_measurement_seconds = MEASUREMENT_INTERVAL_SECONDS
            measurement_index = 0
            while progressed_seconds < HOLD_SECONDS:
                interval_seconds = min(
                    PROGRESS_INTERVAL_SECONDS,
                    HOLD_SECONDS - progressed_seconds,
                    next_measurement_seconds - progressed_seconds,
                )
                system.evolve(state, for_time=interval_seconds)
                progressed_seconds += interval_seconds
                print(
                    f"{model_name:>3} | cycle {cycle}/{REPEATS} | "
                    f"{temperature_c:g} C | hold "
                    f"{progressed_seconds / HOLD_SECONDS:.0%} "
                    f"({progressed_seconds / 60:g}/{HOLD_SECONDS / 60:g} min)",
                    flush=True,
                )
                if progressed_seconds != next_measurement_seconds:
                    continue

                measurement_index += 1
                canvas = state.canvas_view
                if np.any(canvas[:, LAST_USABLE_COLUMN]):
                    raise RuntimeError(
                        f"{model_name} reached the canvas edge during cycle {cycle}; "
                        "increase CANVAS_LENGTH before trusting this trajectory."
                    )
                current_length = ribbon_length(state)
                measurement_seconds = progressed_seconds - previous_measurement_seconds
                growth_rate = (current_length - previous_length) / (measurement_seconds / 3600.0)
                elapsed_hours = hold_start_hours + progressed_seconds / 3600.0
                cumulative_growth_rate = (current_length - initial_length) / elapsed_hours
                rows.append(
                    {
                        "model": model_name,
                        "tile_concentration_scale": tile_concentration_scale,
                        "segment_1_domain_bp": SEGMENT_1_DOMAIN_BP,
                        "segment_2_domain_bp": SEGMENT_2_DOMAIN_BP,
                        "cycle": cycle,
                        "hold_in_cycle": hold_index,
                        "measurement_in_hold": measurement_index,
                        "temperature_c": temperature_c,
                        "hold_seconds": HOLD_SECONDS,
                        "measurement_seconds": measurement_seconds,
                        "hold_start_hours": hold_start_hours,
                        "hold_end_hours": hold_start_hours + HOLD_SECONDS / 3600.0,
                        "measurement_start_hours": hold_start_hours + previous_measurement_seconds / 3600.0,
                        "measurement_end_hours": elapsed_hours,
                        "elapsed_hours": elapsed_hours,
                        "rgrow_state_time_hours": state.time / 3600.0,
                        "ribbon_length_columns": current_length,
                        "growth_columns": current_length - initial_length,
                        "growth_rate_columns_per_hour": growth_rate,
                        "cumulative_growth_rate_columns_per_hour": cumulative_growth_rate,
                        "tile_count": state.n_tiles,
                        "event_count": state.total_events,
                    }
                )
                print(
                    f"{model_name:>3} | cycle {cycle}/{REPEATS} | "
                    f"{temperature_c:g} C | {state.time / 3600:.1f} h | "
                    f"length {current_length} complete columns | "
                    f"dG/dt {growth_rate:g} columns/h",
                    flush=True,
                )
                previous_length = current_length
                previous_measurement_seconds = progressed_seconds
                next_measurement_seconds += MEASUREMENT_INTERVAL_SECONDS
    return rows


def add_growth_sum_prediction(rows: list[dict[str, object]]) -> None:
    """Attach cumulative and per-hold residuals for G(H00)=G(H01)+G(H10)."""
    by_timeline: dict[tuple[int, int, int], dict[str, dict[str, object]]] = {}
    for row in rows:
        key = (
            int(row["cycle"]),
            int(row["hold_in_cycle"]),
            int(row["measurement_in_hold"]),
        )
        by_timeline.setdefault(key, {})[str(row["model"])] = row

    for models in by_timeline.values():
        if not {"H00", "H01", "H10"}.issubset(models):
            continue
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


def set_rate_axis_scale(
    axis: plt.Axes,
    series: Iterable[Iterable[float]],
) -> str:
    """Use log scaling while retaining zero or negative rates with symlog."""
    values = np.array([value for values in series for value in values], dtype=float)
    values = values[np.isfinite(values)]
    if np.all(values > 0):
        axis.set_yscale("log")
        return "logarithmic"

    positive_values = values[values > 0]
    linthresh = float(positive_values.min() / 10) if len(positive_values) else 1e-12
    axis.set_yscale("symlog", linthresh=linthresh)
    return "symmetric logarithmic"


def write_csv(rows: Iterable[dict[str, object]], path: Path) -> None:
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_plot(rows: list[dict[str, object]], path: Path) -> None:
    """Save selected-model growth curves and available control predictions."""
    models = {
        name: sorted(
            (row for row in rows if row["model"] == name),
            key=lambda row: (
                int(row["cycle"]),
                int(row["hold_in_cycle"]),
                int(row.get("measurement_in_hold", 1)),
            ),
        )
        for name in MODEL_TILE_SETS
        if any(row["model"] == name for row in rows)
    }
    reference_rows = next(iter(models.values()))
    has_prediction = {"H00", "H01", "H10"}.issubset(models)
    x = [float(row["elapsed_hours"]) for row in reference_rows]

    figure_rows = 4 if has_prediction else 3
    fig, axes = plt.subplots(figure_rows, 1, figsize=(13, 4 * figure_rows), constrained_layout=True)
    growth_ax, rate_ax = axes[:2]
    cumulative_rate_ax = axes[2]
    fig.suptitle(
        f"TP-EP-1 simulation: tile concentrations at {reference_rows[0]['tile_concentration_scale']:g}x nominal",
        fontsize=14,
    )
    temperatures = sorted({float(row["temperature_c"]) for row in reference_rows})
    temperature_palette = plt.get_cmap("Pastel1", len(temperatures))
    temp_colors = {
        temperature: temperature_palette(index)
        for index, temperature in enumerate(temperatures)
    }
    hold_rows: dict[tuple[int, int], dict[str, object]] = {}
    for row in reference_rows:
        hold_rows.setdefault((int(row["cycle"]), int(row["hold_in_cycle"])), row)
    for row in hold_rows.values():
        x0 = float(row["hold_start_hours"])
        x1 = float(row["hold_end_hours"])
        growth_ax.axvspan(
            x0,
            x1,
            color=temp_colors[float(row["temperature_c"])],
            alpha=0.45,
            linewidth=0,
        )

    derivative_ax = growth_ax.twinx()
    derivative_series: list[list[float]] = []
    for model_name, model_rows in models.items():
        growth = [float(row["growth_columns"]) for row in model_rows]
        growth_line, = growth_ax.plot(
            [0.0, *x],
            [0.0, *growth],
            "o-",
            label=f"{model_name} cumulative growth",
        )
        derivative = [plot_number(row["growth_rate_columns_per_hour"]) for row in model_rows]
        derivative_series.append(derivative)
        derivative_ax.step(
            [0.0, *x],
            [derivative[0], *derivative],
            where="post",
            color=growth_line.get_color(),
            linestyle="--",
            alpha=0.8,
            label=f"{model_name} dG/dt",
        )
    if has_prediction:
        h00 = models["H00"]
        predicted = [float(row["H01_plus_H10_growth_columns"]) for row in h00]
        growth_ax.plot([0.0, *x], [0.0, *predicted], "s--", label="H01 + H10 predicted")
        predicted_derivative = [
            plot_number(row["H01_plus_H10_rate_columns_per_hour"])
            for row in h00
        ]
        derivative_series.append(predicted_derivative)
        derivative_ax.step(
            [0.0, *x],
            [predicted_derivative[0], *predicted_derivative],
            where="post",
            color="black",
            linestyle=":",
            label="H01 + H10 dG/dt",
        )
    derivative_scale = set_rate_axis_scale(derivative_ax, derivative_series)
    growth_ax.set_title("Cumulative ribbon growth and its derivative dG/dt")
    growth_ax.set_ylabel("Growth (complete 12-tile columns)")
    derivative_ax.set_ylabel(f"dG/dt (complete columns/hour; {derivative_scale} scale)")
    growth_ax.grid(True, alpha=0.25)
    growth_ax.legend(loc="upper left")
    derivative_ax.legend(loc="upper right")

    positions = np.array(x)
    sample_spacing = float(np.diff(np.array([0.0, *x])).min())
    rate_series = [
        (f"{model_name} measured", [plot_number(row["growth_rate_columns_per_hour"]) for row in model_rows])
        for model_name, model_rows in models.items()
    ]
    if has_prediction:
        rate_series.append((
            "H01 + H10 predicted",
            [plot_number(row["H01_plus_H10_rate_columns_per_hour"]) for row in models["H00"]],
        ))
    width = 0.8 * sample_spacing / len(rate_series)
    for index, (label, rates) in enumerate(rate_series):
        offset = (index - (len(rate_series) - 1) / 2) * width
        rate_ax.bar(positions + offset, rates, width, label=label)
    rate_scale = set_rate_axis_scale(rate_ax, (rates for _, rates in rate_series))
    rate_ax.set_title(f"Growth rate during each measurement interval ({rate_scale} scale)")
    rate_ax.set_ylabel("Growth rate (complete columns/hour)")
    rate_ax.set_xlabel("Elapsed time (hours)")
    rate_ax.grid(True, axis="y", alpha=0.25)
    rate_ax.legend()

    cumulative_rate_series: list[list[float]] = []
    for model_name, model_rows in models.items():
        cumulative_rates = [
            float(row["cumulative_growth_rate_columns_per_hour"])
            for row in model_rows
        ]
        cumulative_rate_series.append(cumulative_rates)
        cumulative_rate_ax.plot(x, cumulative_rates, "o-", label=f"{model_name} measured")
    if has_prediction:
        predicted_cumulative_rates = [
            float(row["H01_plus_H10_growth_columns"]) / float(row["elapsed_hours"])
            for row in models["H00"]
        ]
        cumulative_rate_series.append(predicted_cumulative_rates)
        cumulative_rate_ax.plot(
            x,
            predicted_cumulative_rates,
            "s--",
            label="H01 + H10 predicted",
        )
    cumulative_rate_scale = set_rate_axis_scale(cumulative_rate_ax, cumulative_rate_series)
    cumulative_rate_ax.set_title(
        f"Cumulative average growth rate since the seed ({cumulative_rate_scale} scale)"
    )
    cumulative_rate_ax.set_xlabel("Elapsed time (hours)")
    cumulative_rate_ax.set_ylabel("Average complete columns/hour")
    cumulative_rate_ax.grid(True, alpha=0.25)
    cumulative_rate_ax.legend()

    if has_prediction:
        residual_ax = axes[3]
        rate_residuals = [plot_number(row["H00_minus_component_rate_columns_per_hour"]) for row in models["H00"]]
        residual_ax.bar(positions, rate_residuals, 0.8 * sample_spacing, color=[
            "#9ca3af" if np.isnan(value) else "#2563eb" if value >= 0 else "#dc2626"
            for value in rate_residuals
        ])
        residual_ax.axhline(0, color="black", linewidth=1)
        residual_ax.set_title("Prediction residual: H00 - (H01 + H10)")
        residual_ax.set_ylabel("Rate residual (complete columns/hour)")
        residual_ax.set_xlabel("Elapsed time (hours)")
        residual_ax.grid(True, axis="y", alpha=0.25)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name(f"{timestamp}-tp-ep-1-results.csv"),
        help="CSV path for length measurements (default: timestamped path next to this script)",
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
    parser.add_argument(
        "--models",
        nargs="+",
        choices=tuple(MODEL_TILE_SETS),
        default=tuple(MODEL_TILE_SETS),
        help="models to simulate; use '--models H01' for a one-model debug plot (default: all)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    all_rows: list[dict[str, object]] = []
    for model_name in args.models:
        all_rows.extend(run_model(model_name, args.tile_concentration_scale))

    add_growth_sum_prediction(all_rows)
    write_csv(all_rows, args.output)
    figure_path = args.figure or args.output.with_suffix(".png")
    write_plot(all_rows, figure_path)
    print(f"Wrote {len(all_rows)} hold measurements to {args.output}")
    print(f"Wrote prediction plot to {figure_path}")


if __name__ == "__main__":
    main()
