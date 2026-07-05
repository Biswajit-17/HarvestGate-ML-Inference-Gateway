# Phase 6 — Dockerization & Deployment Design & Roadmap

This document outlines the step-by-step implementation plan for containerizing the HarvestGate ML Inference Gateway, orchestrating the full telemetric/cache stack via Docker Compose, and deploying to production.

---

## 📅 Implementation Steps

### Step 1: Create Gateway Dockerfile (Phase 6.1)

Create a production-ready, minimal Docker container to run the FastAPI gateway application.

*   **Location:** Create `Dockerfile` in the repository root.
*   **Base Image:** Use `python:3.11-slim` to minimize the image footprint (~120MB raw size) and reduce vulnerability surface area.
*   **Build Optimization:** Install Python dependencies using `--no-cache-dir` to prevent pip cache inflation.
*   **Healthcheck:** Implement a native `HEALTHCHECK` using `curl` to query the `/health` endpoint so container orchestrators can monitor gateway health.
*   **Context Optimization:** Create a `.dockerignore` file to exclude local virtual environments (`venv/`), git history (`.git/`), cache files (`__pycache__/`, `*.pyc`), local secrets (`.env`), and testing scripts.

---

### Step 2: Configure Docker Compose Orchestration (Phase 6.2)

Integrate the FastAPI gateway container into the existing services inside [docker-compose.yml](file:///c:/Users/Biswajitrk/Documents/COdezzz/HarvestGate%20-%20ML%20Inference%20Gateway/docker-compose.yml).

*   **Gateway Service:**
    *   Build context pointing to the root directory.
    *   Expose port `8000:8000`.
    *   Map environment variables using `.env` substitution.
    *   Establish dependency (`depends_on: ["redis"]`) so cache services initialize first.
*   **Internal Network Communication:** Ensure that the gateway uses the internal service DNS hostname to connect to Redis (`redis://:password@redis:6379`) instead of localhost.

---

### Step 3: Configure Prometheus Scraping (Phase 6.3)

Update the scraping target configuration inside [prometheus.yml](file:///c:/Users/Biswajitrk/Documents/COdezzz/HarvestGate%20-%20ML%20Inference%20Gateway/monitoring/prometheus/prometheus.yml) to function within the containerized bridge network.

*   **Target Updates:** Modify the scrape target for the `harvestgate-gateway` job from `"host.docker.internal:8000"` to `"gateway:8000"`.
*   **Benefit:** Resolves metrics directly within the private Docker network rather than looping back through the host machine.

---

### Step 4: Write Comprehensive README & Deployment Guides (Phase 6.4)

Create `README.md` at the project root to document the full codebase and deployment instructions.

*   **System Architecture:** Explain the data flow between Gateway, Redis, ONNX Runtime, OpenRouter, and Prometheus/Grafana.
*   **Quickstart Guide:** Detail instructions on running the entire containerized stack using `docker compose up --build`.
*   **API Reference:** Provide curl examples for `/predict`, `/predict/explain`, and `/health` endpoints.
*   **Deployment Guidelines:** Outline setup steps for deploying to Railway or Render (such as binding ports and configuring environment variables).

---

## 🔒 Phase 6 Security Hardening Matrix

| Security Rule | Risk Addressed | Implementation Detail |
|---|---|---|
| **Minimal Base Image** | Host OS vulnerability exploitation | Using `python:3.11-slim` strips out compilers, build tooling, and GUI packages. |
| **Non-Root Execution** | Container breakout to host root access | Create a dedicated system user/group inside the Dockerfile to run the Uvicorn worker. |
| **Secure .dockerignore** | Credentials leakage and cache pollution | Excludes `.env`, private SSH keys, and `venv` directories from being baked into the Docker image. |
| **Private Docker Network** | Inter-service traffic interception | Redis, Prometheus, and Grafana communicate on a closed bridge network, exposing only ports 8000, 9090, and 3000 to the host. |
| **Docker Healthcheck** | Silent service failures | `HEALTHCHECK` queries `/health` every 30s to automatically restart unhealthy container instances. |
