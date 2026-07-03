# Phase 3 — Prometheus & Grafana Monitoring Design & Roadmap

This document outlines the step-by-step implementation plan for integrating a production-grade Prometheus and Grafana monitoring stack into HarvestGate.

---

## 📅 Implementation Steps

### Step 1: Metrics Definitions Module (Phase 3.1)

Create a dedicated metrics module to house all Prometheus metrics.

*   **Location:** Create `gateway/metrics.py` (or monitoring-specific module) to define operational gauges, histograms, and counters:
    *   `gateway_requests_total` (Counter): Total prediction requests, labeled by `endpoint`, `backend` (`onnx` vs. `groq`), and response `status` code.
    *   `gateway_request_duration_seconds` (Histogram): Request latency tracking with buckets configured for sub-millisecond to multi-second ranges. Labeled by `endpoint` and `backend`.
    *   `gateway_cache_lookups_total` (Counter): Labeled by `endpoint` and `result` (`hit` vs. `miss`) to measure cache hit ratio.
    *   `gateway_prediction_values` (Histogram): Distribution of predicted yield output levels to analyze output variance.
    *   `gateway_psi_score` (Gauge): Current feature drift values per input column (prepped for Phase 5).
    *   `gateway_drift_alerts_total` (Counter): Total drift threshold breach events (prepped for Phase 5).

#### Metrics Registry Reference

| # | Metric Name | Type | Labels | Domain |
|---|---|---|---|---|
| 1 | `gateway_requests_total` | Counter | `endpoint`, `method`, `status` | HTTP throughput |
| 2 | `gateway_request_duration_seconds` | Histogram | `endpoint`, `method` | End-to-end latency |
| 3 | `gateway_active_requests` | Gauge | `endpoint` | Concurrency |
| 4 | `gateway_cache_lookups_total` | Counter | `endpoint`, `result` (hit/miss) | Cache efficiency |
| 5 | `gateway_inference_duration_seconds` | Histogram | `backend` (onnx/groq) | Pure inference time |
| 6 | `gateway_prediction_yield_kg_per_ha` | Histogram | — | Yield value distribution |
| 7 | `gateway_climate_fetch_duration_seconds` | Histogram | `api` (nominatim/open_meteo) | External API latency |
| 8 | `gateway_climate_fallbacks_total` | Counter | — | Weather API failures |
| 9 | `gateway_psi_score` | Gauge | `feature` | Drift detection (Phase 5) |
| 10 | `gateway_drift_alerts_total` | Counter | `feature`, `severity` | Drift alerts (Phase 5) |
| 11 | `gateway_rate_limit_rejections_total` | Counter | `endpoint` | Security monitoring |
| 12 | `gateway_payload_rejections_total` | Counter | — | Security monitoring |
| 13 | `gateway_integrity_check_failures_total` | Counter | `artifact` | Security monitoring |
| 14 | `gateway` | Info | — | Static instance metadata |

---

### Step 2: Instrument the Gateway (Phase 3.2)

Integrate metrics capturing inside the FastAPI routing layers in [gateway/main.py](file:///c:/Users/Biswajitrk/Documents/COdezzz/HarvestGate%20-%20ML%20Inference%20Gateway/gateway/main.py):

*   **Scrape Endpoint:** Add a `/metrics` GET endpoint returning `generate_latest()` from the `prometheus_client` registry with the appropriate media type.
*   **Latency & Count Middleware:** Use an ASGI middleware or route wrapper to measure endpoint latencies, increment transaction counts, and catch system error statuses.
*   **Cache Metric Integration:** Increment cache lookup counters inside `/recommend` and `/predict` after cache checking.
*   **Yield Value Recording:** Capture ONNX model output yield floats inside the inference pipeline and record them to the prediction values histogram.

---

### Step 3: Prometheus Scrape Configuration (Phase 3.3)

Add Prometheus to the local Docker architecture:

*   **Configuration File:** Create `monitoring/prometheus/prometheus.yml`:
    *   Configure global evaluation and scrape intervals (default: `15s`).
    *   Define a scrape target `harvestgate-gateway` pointing to `gateway:8000`.
*   **Docker Service:** Add a `prometheus` service inside `docker-compose.yml` pulling `prom/prometheus:latest`, publishing port `9090`, and mounting the scrape configuration file.

---

### Step 4: Grafana Provisioning & Dashboard (Phase 3.4)

Enable out-of-the-box visualization without requiring manual web UI setup:

*   **Datasource Provisioning:** Create `monitoring/grafana/provisioning/datasources/prometheus.yaml` to register Prometheus as the default datasource.
*   **Dashboard Provisioning:** Create `monitoring/grafana/provisioning/dashboards/dashboards.yaml` pointing to local storage.
*   **Dashboard Definition:** Create `monitoring/grafana/dashboards/harvestgate_dashboard.json` with JSON panels showing requests, latency quantiles, cache efficiency, and drift gauges.
*   **Docker Service:** Add a `grafana` service pulling `grafana/grafana:latest`, publishing port `3000`, and mounting the provisioning folder.

---

### Step 5: Verification Testing

Develop a verification methodology to assert metrics capture accuracy:

1.  **Metric Exporters:** Hit `/metrics` directly using `curl` and verify metrics exist.
2.  **Scrape Verification:** Access Prometheus at `http://localhost:9090/targets` and confirm that `harvestgate-gateway` is reporting `UP`.
3.  **Grafana Dashboard Autoload:** Access Grafana at `http://localhost:3000` (default login: admin/admin) and confirm the *HarvestGate Performance Dashboard* is populated with real-time graphs.

---

## 📈 Grafana Dashboard Panel Matrix

| Panel Name | Panel Type | PromQL Query / Metric Expression | Value / Insight |
|---|---|---|---|
| **Request Throughput** | Time Series | `rate(gateway_requests_total[1m])` | API request volume (RPS) |
| **Quantile Latency** | Time Series | `histogram_quantile(0.95, sum(rate(gateway_request_duration_seconds_bucket[5m])) by (le))` | P95 latency thresholds |
| **Cache Hit Ratio** | Gauge | `sum(rate(gateway_cache_lookups_total{result="hit"}[5m])) / sum(rate(gateway_cache_lookups_total[5m]))` | Real-time cache utilization efficiency |
| **Success vs Error Rates** | Bar Gauge | `sum(rate(gateway_requests_total[5m])) by (status)` | System health and HTTP error codes |
| **PSI Feature Drift** | Gauge | `gateway_psi_score` | Input drift alerts (PSI > 0.25) |
| **ONNX vs Groq Split** | Pie Chart | `sum(gateway_requests_total) by (backend)` | Resource routing distribution |
