"""
onnx_runner.py — Inference runner using ONNX Runtime and scikit-learn preprocessor.

Performs batch predictions for all 19 crops in a single forward pass,
and single crop predictions when specified.
"""

import os
from typing import Dict, List, Tuple
import joblib
import numpy as np
import onnxruntime as rt
import pandas as pd

from gateway.security import verify_file_integrity

# ── Feature Config ──
ALL_CROPS = [
    "BARLEY",
    "CASTOR",
    "CHICKPEA",
    "COTTON",
    "FINGER MILLET",
    "GROUNDNUT",
    "LINSEED",
    "MAIZE",
    "PEARL MILLET",
    "PIGEONPEA",
    "RAPESEED AND MUSTARD",
    "RICE",
    "SAFFLOWER",
    "SESAMUM",
    "SORGHUM",
    "SOYABEAN",
    "SUGARCANE",
    "SUNFLOWER",
    "WHEAT",
]

FEATURES = [
    "N (Kg/ha)",
    "P (Kg/ha)",
    "K (Kg/ha)",
    "Annual Rainfall (mm)",
    "Kharif Rainfall (mm)",
    "Rabi Rainfall (mm)",
    "Irrigation Ratio",
    "Primary Soil Type",
    "State Name",
    "Crop",
]


class ONNXRunner:

    def __init__(self, model_path: str, preprocessor_path: str):
        # 1. Integrity check (Defense-in-depth before pickling)
        if not verify_file_integrity(model_path):
            raise SecurityError("Model artifact hash mismatch. Loading aborted.")
        if not verify_file_integrity(preprocessor_path):
            raise SecurityError("Preprocessor artifact hash mismatch. Loading aborted.")

        # 2. Load artifacts
        # We ignore version mismatch warnings during load (handled by scikit-learn warnings system)
        self.preprocessor = joblib.load(preprocessor_path)
        self.session = rt.InferenceSession(model_path)
        self.input_name = self.session.get_inputs()[0].name

    def _prepare_inputs(self, env_profile: dict, crops: List[str]) -> np.ndarray:
        """Helper to build and preprocess a DataFrame for prediction."""
        # Duplicate env profile for each crop
        rows = [env_profile.copy() for _ in crops]
        df = pd.DataFrame(rows)
        df["Crop"] = crops

        # Ensure column order matches exactly what ColumnTransformer expects
        df = df[FEATURES]

        # Transform and cast to float32
        features = self.preprocessor.transform(df).astype(np.float32)
        return features

    def predict_single(self, env_profile: dict, crop: str) -> float:
        """
        Predict yield for a single crop in a given environment.

        Returns expected yield in Kg/ha.
        """
        features = self._prepare_inputs(env_profile, [crop])
        result = self.session.run(None, {self.input_name: features})
        raw_yield = float(result[0].item())

        # Security check: clamp output to realistic limits
        return max(0.0, raw_yield)

    def predict_all_crops(self, env_profile: dict) -> List[Tuple[str, float]]:
        """
        Simulate yields for all 19 crops simultaneously under the same environment.

        Returns list of (crop_name, raw_yield_float) tuples.
        """
        features = self._prepare_inputs(env_profile, ALL_CROPS)
        result = self.session.run(None, {self.input_name: features})

        # result[0] is an array of shape (19, 1)
        predictions = result[0].flatten()

        results = []
        for crop, yield_val in zip(ALL_CROPS, predictions):
            results.append((crop, max(0.0, float(yield_val))))

        return results


class SecurityError(Exception):
    """Raised when an integrity check fails at model load time."""

    pass
