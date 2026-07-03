# Phase 1 — Core Inference Design & Roadmap

This document outlines the step-by-step implementation plan for establishing the scaffolding, data loading, preprocessing, model loading, and core FastAPI gateway for HarvestGate.

---

## 📅 Implementation Steps

### Step 1: Scaffold Dependencies & Folders (Phase 1.1)

Set up the basic virtual environment and directory structure.

*   **Virtual Environment:** Initialize a Python virtual environment and configure dependencies in `requirements.txt` (FastAPI, ONNX Runtime, scikit-learn, joblib, pandas, numpy, uvicorn).
*   **Directory Structure:** Establish folders for the core modules:
    *   `gateway/` for API endpoints and schemas.
    *   `models/` for binary files.
    *   `data/` for pre-computed metadata.
    *   `inference/` for runtimes.

---

### Step 2: Model & Preprocessor Verification (Phase 1.2)

Import the converted ONNX model and the scikit-learn ColumnTransformer:

*   **Artifact Mapping:** Copy the tuned yield prediction model `harvestml_simulator.onnx` and preprocessing transformer `simulator_preprocessor.joblib` to `models/`.
*   **Lookup Extraction:** Extract state-level baseline crop priorities and acreage distributions into JSON configuration files in the `data/` folder.
*   **Model Integrity Check:** Compute SHA-256 signatures for each artifact at deployment, saving them to `.env`. Create a security verify script (`gateway/security.py`) to validate hashes on gateway startup.

---

### Step 3: Pydantic Request & Response Schemas (Phase 1.3)

Build the strict validation schemas to parse incoming client requests in `gateway/schemas.py`:

*   **Recommend Schemas:**
    *   `RecommendRequest`: Expects `state`, `district`, `soil_type`, and an optional `explain` boolean.
    *   `RecommendResponse`: Returns a list of crop names, predicted yield scores, caching indicators, and latencies.
*   **Predict Schemas:**
    *   `PredictRequest`: Expects numeric parameters (`N`, `P`, `K`, rainfall, irrigation) and categorical values (`soil_type`, `state`, `crop`).
    *   `PredictResponse`: Returns the single predicted yield value, backing model (`onnx`), cache indicators, and latencies.
*   **Data Validation:** Apply strict category whitelisting (state and soil validations) and numeric bounds.

---

### Step 4: Implement ONNX Inference Session Runner (Phase 1.4)

Create `inference/onnx_runner.py` containing the `ONNXRunner` class:

*   **Execution Runtime:** Use `onnxruntime.InferenceSession` to run predictions.
*   **Pre-Processing Pipeline:** Load the scikit-learn preprocessor pipeline using `joblib`.
*   **Dimension Binding:** Accept raw client JSON dictionary, convert to a Pandas DataFrame, feed into the preprocessor `transform()`, and cast the resulting numeric array to `np.float32` matching input tensor specifications.

---

### Step 5: Implement FastAPI Inference Gateway (Phase 1.5)

Create [gateway/main.py](file:///c:/Users/Biswajitrk/Documents/COdezzz/HarvestGate%20-%20ML%20Inference%20Gateway/gateway/main.py) representing the core API gateway:

*   **Lifespan Management:** Run SHA-256 integrity validation on artifacts. Load the preprocessor and models into global memory variables during startup.
*   **Endpoints:**
    *   `POST /recommend`: Serves crop suggestions based on location-specific historical climate defaults.
    *   `POST /predict`: Preprocesses input features and runs model inference to return numeric yield predictions.
    *   `GET /health`: Checks that model files are loaded in memory.
*   **Security Controls:**
    *   Inject SlowAPI rate limits (e.g., 60/min on inference).
    *   Add custom middleware to cap incoming request body size to **2KB** to prevent memory exhaustion DoS.
    *   Intercept global exceptions to mask raw tracebacks from client responses.

---

### Step 6: Verification Testing

Develop validation script `verify_phase1_security.py` to assert core gateway mechanics:

1.  **Integrity Validation:** Corrupt a baseline file and assert the server aborts startup.
2.  **Boundary Rejection:** Send nutrient values out of bounds and verify `422` error codes.
3.  **DOS Payload Size Check:** Send a payload larger than 2KB and verify a `413 Request Entity Too Large` error is returned.

---

## 🔒 Phase 1 Security Hardening Matrix

| Security Rule | Risk Addressed | Implementation Detail |
|---|---|---|
| **SHA-256 Integrity Verification** | Model tampering, local code injection | Compares files against hardcoded env signatures on boot |
| **Whitelisting & Escaping** | SQL injection, XSS parameter tampering | Strict type checking and value checks on categories |
| **Numeric Range Constraints** | Out-of-bounds input crash | Pydantic validation checks on nutrient limits |
| **Traceback Masking** | Infrastructure signature leak | Capture all standard errors and return generic error details |
| **Payload Cap** | Memory exhaustion DoS | 2KB limit middleware throws 413 error |
