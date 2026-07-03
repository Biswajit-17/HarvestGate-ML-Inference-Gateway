"""
security.py — File integrity verification and security utilities.

Verifies SHA-256 hashes of model artifacts and data files at startup
to prevent pickle deserialization attacks (joblib) and data tampering.
"""

import hashlib
import logging
import os

logger = logging.getLogger("harvestgate.security")

# ── Expected SHA-256 Hashes ──
# Recompute these by running: python compute_hashes.py
# Update whenever model artifacts or lookup tables are regenerated.

EXPECTED_HASHES = {
    "harvestml_simulator.onnx": "ed486255f767da28dfd3340187e4147db6b80ed7f3e7dcb082e38419a44dbc97",
    "simulator_preprocessor.joblib": "f9b8d89ed3074ca30b2e336c0f9e12b8d0ca9aa9c1fa21b088b161f04e530cc6",
    "crop_baselines.json": "ac9dcebb2cf5e1af61e53d4205c7a0ed3521d058ddc74969be0487f1161cb3ff",
    "acreage_priors.json": "c6e3e3a15e4df15f4f20289d5d79468f69b1895100cfff1b24faf321e11a133f",
    "state_defaults.json": "d3320b225f3cfe7153d495f5653bfcdb9337eae0ceeb7239afd806140cba0341",
}


def compute_file_hash(file_path: str) -> str:
    """Compute the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_file_integrity(file_path: str) -> bool:
    """
    Verify a file's SHA-256 hash against the expected value.

    Returns True if the file is intact, False if tampered or missing.
    Raises FileNotFoundError if the file doesn't exist.
    """
    if not os.path.exists(file_path):
        logger.error(f"INTEGRITY CHECK FAILED: File not found: {file_path}")
        raise FileNotFoundError(f"Required file not found: {file_path}")

    filename = os.path.basename(file_path)
    expected = EXPECTED_HASHES.get(filename)

    if expected is None:
        logger.warning(f"No expected hash registered for: {filename}")
        return True  # No hash to check against — allow (but warn)

    actual = compute_file_hash(file_path)

    if actual != expected:
        logger.critical(
            f"INTEGRITY CHECK FAILED: {filename}\n"
            f"  Expected: {expected}\n"
            f"  Actual:   {actual}\n"
            f"  This file may have been tampered with. REFUSING TO LOAD."
        )
        return False

    logger.info(f"Integrity verified: {filename}")
    return True


def verify_all_artifacts(model_dir: str, data_dir: str) -> bool:
    """
    Verify integrity of all model artifacts and data files at startup.

    Returns True only if ALL files pass. Logs details for each failure.
    """
    all_passed = True
    files_to_check = [
        os.path.join(model_dir, "harvestml_simulator.onnx"),
        os.path.join(model_dir, "simulator_preprocessor.joblib"),
        os.path.join(data_dir, "crop_baselines.json"),
        os.path.join(data_dir, "acreage_priors.json"),
        os.path.join(data_dir, "state_defaults.json"),
    ]

    for file_path in files_to_check:
        try:
            if not verify_file_integrity(file_path):
                all_passed = False
        except FileNotFoundError:
            all_passed = False

    if all_passed:
        logger.info("All artifact integrity checks passed.")
    else:
        logger.critical(
            "ONE OR MORE INTEGRITY CHECKS FAILED. "
            "The gateway will refuse to start to prevent potential code execution attacks."
        )

    return all_passed
