"""
monitoring/metrics.py — Centralized Prometheus Metrics Registry for HarvestGate.

All metric objects are defined here and imported by gateway endpoints,
middleware, and background tasks. This single-source approach prevents
scattered metric definitions and ensures consistent naming conventions.

Naming convention: gateway_<domain>_<metric_type>
Labels follow Prometheus best practices (lowercase, underscored).
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# ──────────────────────────────────────────────────────────────────────
# 1. HTTP Request Metrics
# ──────────────────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total HTTP requests received by the gateway.",
    ["endpoint", "method", "status"],
)

REQUEST_LATENCY = Histogram(
    "gateway_request_duration_seconds",
    "End-to-end request latency in seconds.",
    ["endpoint", "method"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ACTIVE_REQUESTS = Gauge(
    "gateway_active_requests",
    "Number of requests currently being processed.",
    ["endpoint"],
)

# ──────────────────────────────────────────────────────────────────────
# 2. Cache Performance Metrics
# ──────────────────────────────────────────────────────────────────────

CACHE_LOOKUPS = Counter(
    "gateway_cache_lookups_total",
    "Total cache lookup attempts, labeled by result.",
    ["endpoint", "result"],  # result: "hit" or "miss"
)

# ──────────────────────────────────────────────────────────────────────
# 3. Inference & Prediction Metrics
# ──────────────────────────────────────────────────────────────────────

INFERENCE_LATENCY = Histogram(
    "gateway_inference_duration_seconds",
    "Time spent in ONNX model inference (excluding cache/network).",
    ["backend"],  # backend: "onnx" or "groq"
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

PREDICTION_VALUES = Histogram(
    "gateway_prediction_yield_kg_per_ha",
    "Distribution of predicted crop yield values (Kg/ha).",
    buckets=[500, 1000, 2000, 3000, 4000, 5000, 7500, 10000, 25000, 50000, 100000],
)

# ──────────────────────────────────────────────────────────────────────
# 4. Climate Resolver Metrics
# ──────────────────────────────────────────────────────────────────────

CLIMATE_FETCH_LATENCY = Histogram(
    "gateway_climate_fetch_duration_seconds",
    "Latency for Open-Meteo and Nominatim API calls.",
    ["api"],  # api: "nominatim" or "open_meteo"
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

CLIMATE_FALLBACKS = Counter(
    "gateway_climate_fallbacks_total",
    "Number of times the climate resolver fell back to historical defaults.",
)

# ──────────────────────────────────────────────────────────────────────
# 5. Drift Detection Metrics (wired in Phase 5)
# ──────────────────────────────────────────────────────────────────────

PSI_SCORE = Gauge(
    "gateway_psi_score",
    "Current Population Stability Index (PSI) drift score per feature.",
    ["feature"],  # feature: "N", "P", "K", "annual_rainfall", etc.
)

DRIFT_ALERTS = Counter(
    "gateway_drift_alerts_total",
    "Total number of drift threshold breach events.",
    ["feature", "severity"],  # severity: "moderate" or "significant"
)

# ──────────────────────────────────────────────────────────────────────
# 6. Security & Rate Limiting Metrics
# ──────────────────────────────────────────────────────────────────────

RATE_LIMIT_REJECTIONS = Counter(
    "gateway_rate_limit_rejections_total",
    "Requests rejected due to rate limiting (HTTP 429).",
    ["endpoint"],
)

PAYLOAD_REJECTIONS = Counter(
    "gateway_payload_rejections_total",
    "Requests rejected due to oversized payload (HTTP 413).",
)

INTEGRITY_CHECK_FAILURES = Counter(
    "gateway_integrity_check_failures_total",
    "SHA-256 integrity verification failures at startup.",
    ["artifact"],  # artifact: filename that failed
)

# ──────────────────────────────────────────────────────────────────────
# 7. System Info (static metadata exposed once)
# ──────────────────────────────────────────────────────────────────────

GATEWAY_INFO = Info(
    "gateway",
    "Static metadata about the HarvestGate gateway instance.",
)
