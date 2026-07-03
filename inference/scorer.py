"""
scorer.py — Ecological Suitability Scorer.

Implements biological yield capping, Bayesian acreage priors,
and relative UI normalization to prevent biomass bias and OOD hallucinations.
"""

import json
import math
from typing import Dict, List, Tuple

from gateway.schemas import CropRecommendation
from gateway.security import verify_file_integrity

CROP_DISPLAY_NAMES = {
    "FINGER MILLET": "Ragi",
    "PEARL MILLET": "Bajra",
    "SORGHUM": "Jowar",
    "MAIZE": "Corn",
    "PIGEONPEA": "Tur Dal / Arhar",
    "SESAMUM": "Til",
    "LINSEED": "Flaxseed / Alsi",
    "SAFFLOWER": "Kusum",
    "RAPESEED AND MUSTARD": "Mustard / Sarson",
}


class SuitabilityScorer:

    def __init__(self, baselines_path: str, priors_path: str):
        # 1. Verify file integrity
        if not verify_file_integrity(baselines_path):
            raise ValueError("Baselines file integrity mismatch.")
        if not verify_file_integrity(priors_path):
            raise ValueError("Acreage priors file integrity mismatch.")

        # 2. Load baselines and priors
        with open(baselines_path, "r", encoding="utf-8") as f:
            self.crop_max_yields: Dict[str, float] = json.load(f)

        with open(priors_path, "r", encoding="utf-8") as f:
            self.state_priors: Dict[str, dict] = json.load(f)

    def score_all(self, predictions: List[Tuple[str, float]], state: str) -> List[CropRecommendation]:
        """
        Calculate suitability scores and return Top 5 crop recommendations.

        Args:
            predictions: List of (crop_name, raw_yield) tuples from the model
            state: The state being simulated (used to pull acreage priors)
        """
        # Resolve state to historical name in priors if needed
        lookup_state = state
        if lookup_state.upper() == "ODISHA":
            lookup_state = "Orissa"

        # Get priors for state
        state_data = self.state_priors.get(lookup_state, {})
        crops_priors = state_data.get("crops", {})

        results = []
        for crop, raw_yield in predictions:
            # Get P95 baseline (global maximum limit)
            baseline_max = self.crop_max_yields.get(crop, raw_yield)

            # ── 1. Biological Capping ──
            # XGBoost cannot extrapolate. Cap at biological limits to prevent impossible yields.
            yield_val = min(raw_yield, baseline_max)

            # ── 2. Data-Driven Acreage Prior (Bayesian Weight) ──
            # Penalizes crops not historically grown in this state.
            crop_info = crops_priors.get(crop, {})
            # Use pre-computed logarithmic acreage weight
            acreage_weight = crop_info.get("acreage_weight", 0.1)

            # ── 3. Raw Suitability Score ──
            raw_score = (yield_val / baseline_max) * 100 * acreage_weight

            display_name = CROP_DISPLAY_NAMES.get(crop, crop.title())
            results.append((display_name, yield_val, raw_score, baseline_max))

        # Sort by suitability score descending, then yield descending
        results.sort(key=lambda x: (x[2], x[1]), reverse=True)

        # Take Top 5
        top_5 = results[:5]

        # ── 4. Relative UI Normalization ──
        # Scales the #1 crop to 98.5% for friendly UI presentation.
        highest_score = top_5[0][2]
        if highest_score > 0:
            scale_factor = 98.5 / highest_score
            normalized_top_5 = []
            for crop_disp, y_val, raw_s, b_max in top_5:
                norm_score = raw_s * scale_factor
                norm_score = min(norm_score, 99.5)  # hard safety cap
                normalized_top_5.append(
                    CropRecommendation(
                        crop=crop_disp,
                        expected_yield_kg_per_ha=round(y_val, 1),
                        max_potential_yield=round(b_max, 1),
                        suitability_percentage=round(norm_score, 1),
                    )
                )
            return normalized_top_5
        else:
            # Fallback if all scores are 0
            return [
                CropRecommendation(
                    crop=item[0],
                    expected_yield_kg_per_ha=round(item[1], 1),
                    max_potential_yield=round(item[3], 1),
                    suitability_percentage=10.0,
                )
                for item in top_5
            ]
