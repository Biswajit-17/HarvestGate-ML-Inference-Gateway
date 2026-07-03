"""
generate_lookups.py — One-time script to extract lookup tables from the HarvestML
master dataset for use in the HarvestGate inference gateway.

Produces three JSON files:
  1. crop_baselines.json   — 95th percentile yield per crop (19 entries)
  2. acreage_priors.json   — Mean planted area per (state, crop) for Bayesian prior
  3. state_defaults.json   — Historical NPK & irrigation averages per state,
                             along with lists of districts and district-level defaults.

Source: master_dataset_clean.csv (66,645 rows × 18 columns, 2000–2017)

Usage:
    python data/generate_lookups.py
"""

import json
import math
import os
import sys

import numpy as np
import pandas as pd


# ── Paths ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

SOURCE_CSV = os.path.join(
    os.path.dirname(PROJECT_ROOT),
    "ML Based Crop Recommendation System",
    "data",
    "processed",
    "master_dataset_clean.csv",
)

OUTPUT_DIR = SCRIPT_DIR  # data/ directory


def load_master_data() -> pd.DataFrame:
    """Load and validate the master dataset."""
    if not os.path.exists(SOURCE_CSV):
        print(f"ERROR: Master dataset not found at:\n  {SOURCE_CSV}")
        print("Make sure the HarvestML project is at the expected location.")
        sys.exit(1)

    df = pd.read_csv(SOURCE_CSV)
    print(f"Loaded master dataset: {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"  Crops:  {df['Crop'].nunique()} unique")
    print(f"  States: {df['State Name'].nunique()} unique")
    print(f"  Districts: {df['Dist Name'].nunique()} unique")
    print(f"  Years:  {df['Year'].min()} - {df['Year'].max()}")
    print()
    return df


def generate_crop_baselines(df: pd.DataFrame) -> dict:
    """
    Compute the 95th percentile yield for each crop.
    Used in the Suitability Score to cap biological maximums and as
    the denominator in the raw score formula.

    Source logic (from app/main.py line 58):
        crop_max_yields = master_data.groupby('Crop')['Yield (Kg per ha)'].quantile(0.95).to_dict()
    """
    baselines = (
        df.groupby("Crop")["Yield (Kg per ha)"]
        .quantile(0.95)
        .round(1)
        .to_dict()
    )
    print(f"[1/3] crop_baselines.json — {len(baselines)} crops")
    for crop, p95 in sorted(baselines.items()):
        print(f"       {crop:30s} → {p95:>10,.1f} Kg/ha")
    print()
    return baselines


def generate_acreage_priors(df: pd.DataFrame) -> dict:
    """
    Compute the Bayesian Acreage Prior for each (state, crop) pair.
    This is the historical mean planted area, used to penalize crops
    that are rarely or never grown in a particular state.

    Source logic (from app/main.py lines 489-502):
        crop_mean_area  = crop_state_data['Area (1000 ha)'].mean()
        max_state_area  = state_data.groupby('Crop')['Area (1000 ha)'].mean().max()
        acreage_weight  = log1p(crop_mean_area) / log1p(max_state_area)

    Output structure:
    {
        "StateName": {
            "max_state_area": float,
            "crops": {
                "CROP": {"mean_area": float, "acreage_weight": float},
                ...
            }
        },
        ...
    }
    """
    all_crops = sorted(df["Crop"].unique())
    all_states = sorted(df["State Name"].unique())

    priors = {}
    for state in all_states:
        state_data = df[df["State Name"] == state]

        # Mean area per crop in this state
        crop_areas = (
            state_data.groupby("Crop")["Area (1000 ha)"]
            .mean()
            .to_dict()
        )
        max_state_area = max(crop_areas.values()) if crop_areas else 1.0

        crops_dict = {}
        for crop in all_crops:
            mean_area = crop_areas.get(crop, 0.0)
            if mean_area > 0 and max_state_area > 0:
                weight = math.log1p(mean_area) / math.log1p(max_state_area)
            else:
                weight = 0.1  # Default penalty for zero-data crops
            crops_dict[crop] = {
                "mean_area": round(mean_area, 3),
                "acreage_weight": round(weight, 4),
            }

        priors[state] = {
            "max_state_area": round(max_state_area, 3),
            "crops": crops_dict,
        }

    print(f"[2/3] acreage_priors.json — {len(priors)} states x {len(all_crops)} crops")
    # Show a sample: top 3 crops for the first state
    sample_state = all_states[0]
    sample_crops = sorted(
        priors[sample_state]["crops"].items(),
        key=lambda x: x[1]["acreage_weight"],
        reverse=True,
    )[:3]
    print(f"       Sample ({sample_state}):")
    for crop, info in sample_crops:
        print(
            f"         {crop:30s} area={info['mean_area']:>8,.1f}  "
            f"weight={info['acreage_weight']:.4f}"
        )
    print()
    return priors


def generate_state_defaults(df: pd.DataFrame) -> dict:
    """
    Compute per-state and per-district historical averages for NPK, rainfall,
    and irrigation. Also extracts the lists of valid districts per state.

    Structure:
    {
        "State Name": {
            "state_defaults": {
                "n_avg": float,
                "p_avg": float,
                ...
            },
            "districts": {
                "District Name": {
                    "n_avg": float,
                    "p_avg": float,
                    ...
                },
                ...
            }
        }
    }
    """
    states = sorted(df["State Name"].unique())
    defaults = {}

    for state in states:
        state_data = df[df["State Name"] == state]

        # 1. State Averages
        state_avg = {
            "n_avg": round(float(state_data["N (Kg/ha)"].mean()), 1),
            "p_avg": round(float(state_data["P (Kg/ha)"].mean()), 1),
            "k_avg": round(float(state_data["K (Kg/ha)"].mean()), 1),
            "annual_rainfall_avg": round(float(state_data["Annual Rainfall (mm)"].mean()), 1),
            "kharif_rainfall_avg": round(float(state_data["Kharif Rainfall (mm)"].mean()), 1),
            "rabi_rainfall_avg": round(float(state_data["Rabi Rainfall (mm)"].mean()), 1),
            "irrigation_ratio_avg": round(float(state_data["Irrigation Ratio"].mean()), 3),
        }

        # 2. District Averages
        districts_dict = {}
        dist_names = sorted(state_data["Dist Name"].dropna().unique())
        for dist in dist_names:
            dist_data = state_data[state_data["Dist Name"] == dist]
            districts_dict[dist] = {
                "n_avg": round(float(dist_data["N (Kg/ha)"].mean()), 1),
                "p_avg": round(float(dist_data["P (Kg/ha)"].mean()), 1),
                "k_avg": round(float(dist_data["K (Kg/ha)"].mean()), 1),
                "annual_rainfall_avg": round(float(dist_data["Annual Rainfall (mm)"].mean()), 1),
                "kharif_rainfall_avg": round(float(dist_data["Kharif Rainfall (mm)"].mean()), 1),
                "rabi_rainfall_avg": round(float(dist_data["Rabi Rainfall (mm)"].mean()), 1),
                "irrigation_ratio_avg": round(float(dist_data["Irrigation Ratio"].mean()), 3),
            }

        defaults[state] = {
            "state_defaults": state_avg,
            "districts": districts_dict,
        }

    print(f"[3/3] state_defaults.json — {len(defaults)} states")
    # Show a couple of samples
    for s in ["Uttar Pradesh", "Maharashtra"]:
        if s in defaults:
            d = defaults[s]["state_defaults"]
            dists = list(defaults[s]["districts"].keys())
            print(
                f"       {s:20s} → N={d['n_avg']:.1f}  P={d['p_avg']:.1f}  "
                f"K={d['k_avg']:.1f}  Dists={len(dists)} (e.g. {dists[:2]})"
            )
    print()
    return defaults


def save_json(data: dict, filename: str) -> str:
    """Save a dict as a formatted JSON file and return the path."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved: {filename} ({size_kb:.1f} KB)")
    return path


def main():
    print("=" * 60)
    print("  HarvestGate — Generating Lookup Tables")
    print("=" * 60)
    print()

    # Load source data
    df = load_master_data()

    # Generate all three lookup tables
    baselines = generate_crop_baselines(df)
    priors = generate_acreage_priors(df)
    defaults = generate_state_defaults(df)

    # Save to JSON
    print("-" * 40)
    save_json(baselines, "crop_baselines.json")
    save_json(priors, "acreage_priors.json")
    save_json(defaults, "state_defaults.json")

    print()
    print("=" * 60)
    print("  All lookup tables generated successfully!")
    print("  These files are loaded by the gateway at startup.")
    print("  Re-run this script only if the training data changes.")
    print("=" * 60)


if __name__ == "__main__":
    main()
