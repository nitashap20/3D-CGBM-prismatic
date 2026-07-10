"""
RS3 Combined Axial + Lateral Stress-Strain Extraction Script
==============================================================
Works for ANY prismatic RS3 model — no code editing required.

HOW IT WORKS:
    1. Looks for a config file (rs3_combined_config.json) in the same folder as this script.
    2. If config file found → reads settings from it silently.
    3. If config file NOT found → asks you questions interactively at runtime
       (all geometry questions — height, X width, Y width — are asked together).

WHAT IT CALCULATES:
    - Stress         : average SigmaZZ (Total) over all rock/specimen nodes (MPa)
    - Axial Strain    : (avg top node Z-disp − avg bottom node Z-disp) / specimen height,
                        NEGATED so compressive displacement → positive strain.
    - Lateral Strain X: (avg left-face X-disp − avg right-face X-disp) / specimen width in X
    - Lateral Strain Y: (avg left-face Y-disp − avg right-face Y-disp) / specimen width in Y
                        (NOT negated — sign as computed directly from displacement difference,
                        confirmed correct by inspection.)

OUTPUT:
    - ONE combined CSV file containing stage, stress, axial strain, lateral strain X,
      lateral strain Y, and all supporting displacement/node-count columns.
    - THREE plots:
        1. Axial only        : Stress (MPa) vs Axial Strain
        2. Lateral only       : Stress (MPa) vs Lateral Strain X and Y (two series)
        3. Combined           : Stress (MPa) vs Axial Strain, Lateral Strain X,
                                 and Lateral Strain Y — all three series on one chart

UNITS ASSUMED:
    - Everything is in meters (m) and MPa, matching the RS3 model's own
      Project Settings (Units > Length = m, Units > Stress = MPa).
    - All geometry values in the config (specimen height, X width, Y width,
      layer tolerance, displacement increment) are entered directly in METERS —
      no conversion happens anywhere in this script.

NOTE ON PLATENS:
    If your model has steel platens/fixtures (e.g. loading caps) that should NOT
    be included in either the axial or lateral strain calculation, list their
    entity names in the config so they get excluded from BOTH calculations.

TO USE WITH A NEW MODEL:
    Option A (config file): copy rs3_combined_config.json, edit the values, run script.
    Option B (interactive): delete or rename rs3_combined_config.json, run script, answer prompts.
"""

import csv
import json
import os
import sys

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Config loading — file first, then interactive fallback
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "rs3_combined_config.json")


def ask(prompt, default=None):
    """Ask user a question, show default, return stripped answer."""
    if default is not None:
        full_prompt = f"  {prompt} [{default}]: "
    else:
        full_prompt = f"  {prompt}: "
    answer = input(full_prompt).strip().strip('"').strip("'").strip()
    return answer if answer else str(default) if default is not None else ""


def ask_model_path(prompt):
    """Ask for the model path — auto-detects .rs3v3 if a folder path is given."""
    full_prompt = f"  {prompt}: "
    answer = input(full_prompt).strip().strip('"').strip("'").strip()

    # Auto-fix: if user pasted a folder path, find the .rs3v3 file inside it
    if os.path.isdir(answer):
        rs3_files = [f for f in os.listdir(answer) if f.endswith(".rs3v3")]
        if len(rs3_files) == 1:
            answer = os.path.join(answer, rs3_files[0])
            print(f"  [Auto-detected model file: {answer}]")
        elif len(rs3_files) > 1:
            print(f"  Multiple .rs3v3 files found: {rs3_files}")
            print(f"  Please re-run and enter the full path including filename.")
        else:
            print(f"  No .rs3v3 file found in that folder. Please re-run and enter the full path.")

    return answer


def ask_list(prompt):
    """Ask for a comma-separated list, return as Python list of strings."""
    raw = ask(prompt + " (comma-separated, or leave blank for NONE)")
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def load_config():
    """
    Load config from JSON file if it exists, otherwise prompt interactively.
    Returns a dict with all required settings.
    """
    if os.path.exists(CONFIG_PATH):
        print(f"\n[CONFIG] Found config file: {CONFIG_PATH}")
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        print("[CONFIG] Settings loaded from file:\n")
        for k, v in cfg.items():
            print(f"    {k}: {v}")
        print()
        return cfg

    # ── Interactive mode ──────────────────────────────────────────────────────
    print("\n" + "="*65)
    print("  RS3 Combined Axial + Lateral Script — Interactive Setup")
    print("  (No config file found — answering these questions once will")
    print("   let the script run. Save a config file to skip this next time.)")
    print("="*65 + "\n")

    cfg = {}

    cfg["model_path"] = ask_model_path(
        "Full path to your .rs3v3 model file (you can paste the folder path)"
    )

    model_dir = os.path.dirname(os.path.abspath(cfg["model_path"]))
    cfg["output_folder"] = ask(
        "Output folder for CSV and plots",
        model_dir
    )

    cfg["port"] = int(ask("RS3 scripting server port eg:", 60064))

    cfg["num_stages"] = int(ask("Number of stages eg:", 15))

    cfg["platen_entity_names"] = ask_list(
        "Entity names of platens/fixtures to EXCLUDE from rock nodes\n"
        "    (e.g. Box 3_1, Box 2_3 — leave blank if no platens)"
    )

    cfg["vertical_axis"] = ask("Loading axis (X / Y / Z) eg:", "Z").upper()

    # ── Geometry — all dimensions asked together ────────────────────────────
    print("\n  --- Specimen geometry (all dimensions in meters) ---")
    cfg["expected_rock_height"] = float(ask("Specimen height (along loading axis) in meters eg:", 0.05))
    cfg["specimen_width_x"]     = float(ask("Specimen width in X direction in meters eg:", 0.02))
    cfg["specimen_width_y"]     = float(ask("Specimen width in Y direction in meters eg:", 0.02))

    cfg["layer_tolerance"] = float(ask(
        "Layer tolerance for face/node detection in meters eg:", 0.00001
    ))

    cfg["displacement_increment"] = float(ask(
        "Displacement increment per stage in meters (negative = compression) eg:", -0.000005
    ))

    # Ask if user wants to save config for next time
    print()
    save = ask("Save these settings to rs3_combined_config.json for next time? (yes/no)", "yes")
    if save.lower() in ("yes", "y"):
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=4)
        print(f"[CONFIG] Saved to: {CONFIG_PATH}\n")
    else:
        print("[CONFIG] Settings not saved — you will be prompted again next run.\n")

    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Main extraction logic
# ─────────────────────────────────────────────────────────────────────────────

def get_coord(node, axis):
    return {"X": node.XCoordinate, "Y": node.YCoordinate, "Z": node.ZCoordinate}[axis]


def main():
    # Load config
    cfg = load_config()

    model_path          = cfg["model_path"]
    output_folder        = os.path.abspath(cfg["output_folder"])
    port                 = int(cfg["port"])
    num_stages           = int(cfg["num_stages"])
    platen_names         = cfg["platen_entity_names"]   # list, can be empty
    vertical_axis        = cfg["vertical_axis"]

    # Everything below is in meters (matches the RS3 model's length unit) and
    # MPa (matches the RS3 model's stress unit) - no conversion needed anywhere.
    expected_height      = float(cfg["expected_rock_height"])
    specimen_width_x     = float(cfg["specimen_width_x"])
    specimen_width_y     = float(cfg["specimen_width_y"])
    layer_tolerance      = float(cfg["layer_tolerance"])
    disp_increment       = float(cfg["displacement_increment"])
    height_check_tol     = 0.001   # 1 mm tolerance, expressed in meters

    # Derive output paths from model name
    model_basename       = os.path.splitext(os.path.basename(model_path))[0]
    output_csv           = os.path.join(output_folder, f"{model_basename}_combined_stress_strain.csv")
    output_plot_axial    = os.path.join(output_folder, f"{model_basename}_axial_plot.png")
    output_plot_lateral  = os.path.join(output_folder, f"{model_basename}_lateral_plot.png")
    output_plot_combined = os.path.join(output_folder, f"{model_basename}_combined_plot.png")

    # ── Connect to RS3 ────────────────────────────────────────────────────────
    from rs3.RS3Modeler import RS3Modeler
    from rs3.results.ResultEnums import SolidsDataType

    STRESS_DATA_TYPE         = SolidsDataType.SIGMA_ZZ_TOTAL
    DISPLACEMENT_Z_TYPE      = SolidsDataType.DISPLACEMENT_Z
    DISPLACEMENT_X_TYPE      = SolidsDataType.DISPLACEMENT_X
    DISPLACEMENT_Y_TYPE      = SolidsDataType.DISPLACEMENT_Y

    print(f"Connecting to RS3 on port {port}...")
    modeler = RS3Modeler(port)
    model   = modeler.openFile(model_path)
    print("Connected successfully.\n")

    stage_numbers       = list(range(1, num_stages + 1))
    required_data_types = {
        STRESS_DATA_TYPE,
        DISPLACEMENT_Z_TYPE,
        DISPLACEMENT_X_TYPE,
        DISPLACEMENT_Y_TYPE,
    }

    print(f"Fetching results for {num_stages} stages — please wait...")
    mesh_results = model.Results.getMeshResults(
        stageNumber=stage_numbers,
        requiredDataTypes=required_data_types,
    )
    print("Done.\n")

    # ── Identify exclusion nodes (platens) ────────────────────────────────────
    excluded_node_ids = set()

    if platen_names:
        print("--- Identifying exclusion nodes ---")
        for name in platen_names:
            try:
                nodes = mesh_results[0].getMeshNodeResults(entityName=name)
                print(f"  '{name}': {len(nodes)} nodes excluded")
                for n in nodes:
                    excluded_node_ids.add(n.NodeID)
            except Exception as e:
                print(f"  WARNING: Could not find entity '{name}' — skipping. ({e})")
        print(f"  Total excluded nodes: {len(excluded_node_ids)}\n")
    else:
        print("--- No exclusion entities specified — using ALL nodes as specimen ---\n")

    # ── Rock/specimen geometry ────────────────────────────────────────────────
    print("--- Specimen geometry ---")
    all_s1      = mesh_results[0].getMeshNodeResults()
    rock_s1     = [n for n in all_s1 if n.NodeID not in excluded_node_ids]
    print(f"  Total nodes     : {len(all_s1)}")
    print(f"  Specimen nodes  : {len(rock_s1)}")
    print(f"  Excluded nodes  : {len(all_s1) - len(rock_s1)}")

    rock_z      = [get_coord(n, vertical_axis) for n in rock_s1]
    rock_top    = max(rock_z)
    rock_bottom = min(rock_z)
    rock_height = rock_top - rock_bottom

    rock_x      = [get_coord(n, "X") for n in rock_s1]
    rock_x_max  = max(rock_x)
    rock_x_min  = min(rock_x)

    rock_y      = [get_coord(n, "Y") for n in rock_s1]
    rock_y_max  = max(rock_y)
    rock_y_min  = min(rock_y)

    print(f"  Top {vertical_axis}           : {rock_top:.6f} m")
    print(f"  Bottom {vertical_axis}        : {rock_bottom:.6f} m")
    print(f"  Height          : {rock_height:.6f} m  (expected {expected_height:.6f} m)")
    print(f"  X range         : {rock_x_min:.6f} to {rock_x_max:.6f} m  (width {rock_x_max - rock_x_min:.6f} m, expected {specimen_width_x:.6f} m)")
    print(f"  Y range         : {rock_y_min:.6f} to {rock_y_max:.6f} m  (width {rock_y_max - rock_y_min:.6f} m, expected {specimen_width_y:.6f} m)")

    if abs(rock_height - expected_height) > height_check_tol:
        print("  *** WARNING: height differs from expected by >1 mm.")
        print("      Check platen entity names in config. ***")
    else:
        print("  Height OK.\n")

    # ── Loop over all stages ──────────────────────────────────────────────────
    print("--- Processing stages ---")
    results_table = []

    for i, stage_num in enumerate(stage_numbers):
        all_nodes       = mesh_results[i].getMeshNodeResults()
        specimen_nodes  = [n for n in all_nodes if n.NodeID not in excluded_node_ids]

        # Average SigmaZZ over all specimen nodes → abs() = compression positive
        stress_values  = [n.getResult(STRESS_DATA_TYPE) for n in specimen_nodes]
        avg_stress_raw = sum(stress_values) / len(stress_values)
        stress_MPa     = abs(avg_stress_raw)   # already MPa, no conversion needed

        # ── Axial strain: top/bottom layer nodes ─────────────────────────────
        top_disps = [
            n.getResult(DISPLACEMENT_Z_TYPE) for n in specimen_nodes
            if abs(get_coord(n, vertical_axis) - rock_top) <= layer_tolerance
        ]
        bottom_disps = [
            n.getResult(DISPLACEMENT_Z_TYPE) for n in specimen_nodes
            if abs(get_coord(n, vertical_axis) - rock_bottom) <= layer_tolerance
        ]

        if not top_disps or not bottom_disps:
            print(
                f"\n  *** Stage {stage_num}: {len(top_disps)} top nodes, "
                f"{len(bottom_disps)} bottom nodes. ***"
                f"\n  Try increasing 'layer_tolerance' in config (currently {layer_tolerance})."
            )
            sys.exit(1)

        avg_top_disp    = sum(top_disps)    / len(top_disps)
        avg_bottom_disp = sum(bottom_disps) / len(bottom_disps)

        # Negate so compressive (negative Z) displacement → positive strain
        axial_strain = -((avg_top_disp - avg_bottom_disp) / rock_height)

        expected_top = stage_num * disp_increment

        # ── Lateral strain: X direction ──────────────────────────────────────
        right_disps_x = [
            n.getResult(DISPLACEMENT_X_TYPE) for n in specimen_nodes
            if abs(get_coord(n, "X") - rock_x_max) <= layer_tolerance
        ]
        left_disps_x = [
            n.getResult(DISPLACEMENT_X_TYPE) for n in specimen_nodes
            if abs(get_coord(n, "X") - rock_x_min) <= layer_tolerance
        ]

        # ── Lateral strain: Y direction ──────────────────────────────────────
        right_disps_y = [
            n.getResult(DISPLACEMENT_Y_TYPE) for n in specimen_nodes
            if abs(get_coord(n, "Y") - rock_y_max) <= layer_tolerance
        ]
        left_disps_y = [
            n.getResult(DISPLACEMENT_Y_TYPE) for n in specimen_nodes
            if abs(get_coord(n, "Y") - rock_y_min) <= layer_tolerance
        ]

        if not right_disps_x or not left_disps_x or not right_disps_y or not left_disps_y:
            print(
                f"\n  *** Stage {stage_num}: lateral nodes — "
                f"X right={len(right_disps_x)}, X left={len(left_disps_x)}, "
                f"Y right={len(right_disps_y)}, Y left={len(left_disps_y)}. ***"
                f"\n  Try increasing 'layer_tolerance' in config (currently {layer_tolerance})."
            )
            sys.exit(1)

        avg_right_x = sum(right_disps_x) / len(right_disps_x)
        avg_left_x  = sum(left_disps_x)  / len(left_disps_x)
        avg_right_y = sum(right_disps_y) / len(right_disps_y)
        avg_left_y  = sum(left_disps_y)  / len(left_disps_y)

        # (avg left disp − avg right disp) / width — sign confirmed correct, no negation
        lateral_strain_x = (avg_left_x - avg_right_x) / specimen_width_x
        lateral_strain_y = (avg_left_y - avg_right_y) / specimen_width_y

        results_table.append({
            "Stage"               : stage_num,
            "AverageStress_MPa"   : round(stress_MPa,       6),
            "AxialStrain"         : round(axial_strain,      8),
            "LateralStrain_X"     : round(lateral_strain_x,  8),
            "LateralStrain_Y"     : round(lateral_strain_y,  8),
            "AvgTopDisp_m"        : round(avg_top_disp,      9),
            "AvgBottomDisp_m"     : round(avg_bottom_disp,   9),
            "ExpectedTopDisp_m"   : round(expected_top,      9),
            "AvgLeftDispX_m"      : round(avg_left_x,        9),
            "AvgRightDispX_m"     : round(avg_right_x,       9),
            "AvgLeftDispY_m"      : round(avg_left_y,        9),
            "AvgRightDispY_m"     : round(avg_right_y,       9),
            "NumSpecimenNodes"    : len(specimen_nodes),
            "NumTopLayerNodes"    : len(top_disps),
            "NumBottomLayerNodes" : len(bottom_disps),
            "NumXLeftNodes"       : len(left_disps_x),
            "NumXRightNodes"      : len(right_disps_x),
            "NumYLeftNodes"       : len(left_disps_y),
            "NumYRightNodes"      : len(right_disps_y),
        })

        print(
            f"  Stage {stage_num:>2}: "
            f"stress={stress_MPa:>8.4f} MPa | "
            f"axial_strain={axial_strain:.6f} | "
            f"lat_X={lateral_strain_x:.6f} | "
            f"lat_Y={lateral_strain_y:.6f} | "
            f"nodes={len(specimen_nodes)}"
        )

    # ── Write combined CSV ────────────────────────────────────────────────────
    print(f"\n--- Writing CSV ---")
    os.makedirs(output_folder, exist_ok=True)
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results_table[0].keys()))
        writer.writeheader()
        writer.writerows(results_table)
    print(f"  Saved: {output_csv}")

    # ── Plots ─────────────────────────────────────────────────────────────────
    print(f"\n--- Generating plots ---")
    try:
        import matplotlib.pyplot as plt

        stresses    = [r["AverageStress_MPa"] for r in results_table]
        axial_strs  = [r["AxialStrain"]       for r in results_table]
        lat_x_strs  = [r["LateralStrain_X"]   for r in results_table]
        lat_y_strs  = [r["LateralStrain_Y"]   for r in results_table]
        num_nodes   = results_table[0]["NumSpecimenNodes"]

        # ── Plot 1: Axial only ───────────────────────────────────────────────
        plt.figure(figsize=(7, 5))
        plt.plot(axial_strs, stresses, marker="o", linewidth=2, color="steelblue")
        plt.xlabel("Axial Strain", fontsize=12)
        plt.ylabel("Average Axial Stress (MPa)", fontsize=12)
        plt.title(
            f"Stress vs. Axial Strain — {model_basename}\n"
            f"(SigmaZZ avg over {num_nodes} specimen nodes)",
            fontsize=12
        )
        plt.xlim(left=0)
        plt.ylim(bottom=0)
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(output_plot_axial, dpi=200)
        print(f"  Saved: {output_plot_axial}")

        # ── Plot 2: Lateral only (X and Y) ───────────────────────────────────
        plt.figure(figsize=(7, 5))
        plt.plot(lat_x_strs, stresses, marker="o", linewidth=2, color="steelblue", label="Lateral Strain X")
        plt.plot(lat_y_strs, stresses, marker="s", linewidth=2, color="firebrick", label="Lateral Strain Y")
        plt.xlabel("Lateral Strain", fontsize=12)
        plt.ylabel("Average Axial Stress (MPa)", fontsize=12)
        plt.title(
            f"Stress vs. Lateral Strain — {model_basename}\n"
            f"(SigmaZZ avg over {num_nodes} specimen nodes)",
            fontsize=12
        )
        plt.ylim(bottom=0)
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(output_plot_lateral, dpi=200)
        print(f"  Saved: {output_plot_lateral}")

        # ── Plot 3: Combined — diverging axes meeting at a shared origin ─────
        # Both curves start from the SAME point (stress=0, strain=0) and fan
        # outward in opposite directions: lateral strain to the LEFT of center
        # (using its own scale, e.g. 0 to -1.75), axial strain to the RIGHT of
        # center (using its own scale, e.g. 0 to 0.002). This is done by
        # remapping each strain value into a shared [-1, 1] plot coordinate:
        #   lateral_strain (always <= 0) -> normalized to [-1, 0]
        #   axial_strain   (always >= 0) -> normalized to [0, 1]
        # then drawing custom tick labels that show the TRUE strain values at
        # each position, so the visual axis is shared but each side keeps its
        # own real units.

        max_axial   = max(axial_strs) if max(axial_strs) > 0 else 1e-12
        max_lateral = max(abs(min(lat_x_strs + lat_y_strs)), abs(min(lat_x_strs)), abs(min(lat_y_strs)))
        max_lateral = max_lateral if max_lateral > 0 else 1e-12

        def remap_axial(v):
            # 0 -> 0, max_axial -> +1
            return v / max_axial

        def remap_lateral(v):
            # 0 -> 0, -max_lateral -> -1  (v is already <= 0)
            return v / max_lateral

        plot_axial_x  = [remap_axial(v)   for v in axial_strs]
        plot_lat_x_x  = [remap_lateral(v) for v in lat_x_strs]
        plot_lat_y_x  = [remap_lateral(v) for v in lat_y_strs]

        fig, ax = plt.subplots(figsize=(8, 5.5))

        ax.plot(plot_lat_x_x, stresses, marker="s", linewidth=2, color="firebrick",  label="Lateral Strain X")
        ax.plot(plot_lat_y_x, stresses, marker="^", linewidth=2, color="seagreen",   label="Lateral Strain Y")
        ax.plot(plot_axial_x, stresses, marker="o", linewidth=2, color="steelblue",  label="Axial Strain")

        ax.axvline(0, color="black", linewidth=1)
        ax.set_xlim(-1.05, 1.05)
        ax.set_ylim(bottom=0)
        ax.set_ylabel("Average Axial Stress (MPa)", fontsize=12)
        ax.set_xlabel("Strain  (left: Lateral  |  right: Axial)", fontsize=12)

        # Custom ticks: 5 on each side, labeled with TRUE strain values
        n_ticks = 5
        left_fracs  = [-(i / n_ticks) for i in range(n_ticks, -1, -1)]   # -1 ... 0
        right_fracs = [(i / n_ticks) for i in range(0, n_ticks + 1)]     # 0 ... 1
        tick_positions = left_fracs + right_fracs[1:]
        tick_labels = (
            [f"{frac * max_lateral:.3f}" for frac in left_fracs]
            + [f"{frac * max_axial:.5f}" for frac in right_fracs[1:]]
        )
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=45, ha="right")

        ax.grid(True)
        ax.legend(loc="best")

        plt.title(
            f"Stress vs. Strain (Axial + Lateral) — {model_basename}\n"
            f"(SigmaZZ avg over {num_nodes} specimen nodes)",
            fontsize=12
        )

        plt.tight_layout()
        plt.savefig(output_plot_combined, dpi=200)
        print(f"  Saved: {output_plot_combined}")

        plt.show()

    except ImportError:
        print("  matplotlib not found. Install with: pip install matplotlib")

    print("\n--- All done ---")
    model.close(False)
    modeler.closeProgram()
    print("Script completed successfully.")


if __name__ == "__main__":
    main()