# Phase 4 — OpenRouter LLM Integration & Routing Design & Roadmap

This document outlines the step-by-step implementation plan for integrating the OpenRouter LLM API to generate natural language agronomic advisories, and implementing intelligent routing and fault tolerance.

---

## 📅 Implementation Steps

### Step 1: Implement OpenRouter Runner (Phase 4.1)

Create the LLM wrapper to interface with OpenRouter's unified endpoint.

*   **Location:** Create `inference/openrouter_runner.py` containing the `OpenRouterRunner` class.
*   **Model selection:** Use `meta-llama/llama-3.1-8b-instruct:free` (extremely fast, low latency, reasoning capable, and free to use).
*   **Structured Prompts:** Construct secure, structured prompts instructing the model to behave as an expert agronomist:
    *   `explain_prediction`: Explains single crop yield outcomes based on explicit soil/climate inputs.
    *   `explain_recommendation`: Explains location-based Top 5 crop recommendations.
*   **Graceful Degradation:** Wrap all client requests in exception blocks. If the `OPENROUTER_API_KEY` is missing or the API returns an error/times out, degrade gracefully by returning a static disclaimer without crashing the main prediction flow.

---

### Step 2: Implement Router & Circuit Breaker (Phase 4.2)

Create the intelligent routing module to protect application availability and API quotas.

*   **Routing Logic:**
    *   If `explain=False` (default): Execute ONNX inference locally (<10ms latency, zero external calls).
    *   If `explain=True`: Execute local ONNX inference first, then pass outputs to `OpenRouterRunner` for explanation (~500ms to 1.5s latency).
*   **Circuit Breaker implementation:**
    *   Keep a rolling track of consecutive OpenRouter API failures.
    *   If **3 consecutive requests fail**, trip the circuit breaker.
    *   When tripped, enter **Open State** for 60 seconds where all `explain=True` queries bypass the API immediately and return a predefined local advisory fallback.

---

### Step 3: Wire into Gateway & Telemetry (Phase 4.3)

Update the API endpoints in [gateway/main.py](file:///c:/Users/Biswajitrk/Documents/COdezzz/HarvestGate%20-%20ML%20Inference%20Gateway/gateway/main.py):

*   **Endpoints:** Wire the explanation logic into `POST /recommend`, `POST /predict`, and `/predict/explain`.
*   **Rate Limits:** Enforce strict, distinct limits via `SlowAPI`:
    *   `explain=True` requests: Cap at **10 requests/minute** per IP (to prevent API key exhaustion/abuse).
*   **Telemetry tracking:**
    *   Track API duration in the `gateway_inference_duration_seconds{backend="openrouter"}` histogram.
    *   Add a counter for OpenRouter API timeouts/failures.

---

### Step 4: Verification Testing

Create a script `verify_openrouter_fallback.py` to confirm the integration:

1.  **API key detection:** Verify gateway degrades gracefully to fallback advisories when `OPENROUTER_API_KEY` is cleared from `.env`.
2.  **Circuit Breaker tripping:** Simulate API failure or inject bad API keys, trigger 3 consecutive failures, and assert the gateway trips into local fallback mode instantly.
3.  **Strict Rate Limits:** Spam the explain endpoint and confirm a `429` is triggered after 10 requests.
4.  **Prompt Injection:** Attempt to hijack the LLM prompt via soil/state variables and confirm that input validation (Phase 1 Pydantic whitelists) blocks it.

---

## 🔒 Phase 4 Security Hardening Matrix

| Security Rule | Risk Addressed | Implementation Detail |
|---|---|---|
| **Pydantic Whitelists** | Prompt injection/hijacking | Only literal categorical types (`StateName`, `SoilType`) reach LLM context |
| **Output Truncation** | Prompt leak, long completion billing charges | Strict truncation of LLM response string to 500 characters |
| **Secret Masking** | API key leak in logs/responses | Key loaded only from environment, never exposed in debug metrics or endpoints |
| **Explain Rate Capping** | Resource exhaustion / API billing abuse | 10 req/min limit strictly enforced on explain endpoints |
| **Circuit Breaker** | Cascading timeouts, resource starvation | Tripping after 3 failures stops gateway waiting on slow endpoints |
