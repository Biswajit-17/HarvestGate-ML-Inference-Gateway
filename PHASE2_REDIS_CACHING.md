# Phase 2 — Redis Caching Layer Design & Roadmap

This document outlines the step-by-step implementation plan for integrating a secure, non-blocking Redis caching layer into HarvestGate.

---

## 📅 Implementation Steps

### Step 1: Secure Redis Container Setup (Phase 2.1)

Deploy a hardened Redis instance using Docker Compose for local development.

* **Image:** `redis:7-alpine` (lightweight, minimal attack surface).
* **Hardening:**
  * Enforce authentication using the `--requirepass` command parameter.
  * Map Redis ports locally (`6379:6379`) for development (will be internal-only in the final production stage).
  * Rename dangerous administrative commands to prevent unauthorized access.
* **Environment variables:**
  * Add `REDIS_PASSWORD=harvestgate_secure_temp_pass_2026` to `.env`.
  * Update `REDIS_URL=redis://:harvestgate_secure_temp_pass_2026@localhost:6379`.

---

### Step 2: Implement Async Cache Manager (Phase 2.2)

Create [gateway/cache.py](file:///c:/Users/Biswajitrk/Documents/COdezzz/HarvestGate%20-%20ML%20Inference%20Gateway/gateway/cache.py) containing the `CacheManager` class:

* **Non-blocking Event Loop:** Use `redis.asyncio` to prevent I/O blocking.
* **Collision-Resistant Keys:** Generate cache keys by sorting payload dictionary keys, serializing to JSON, and computing a **SHA-256** hash (replaces weak MD5).
  * Format: `recommend:<sha256_hash>` or `predict:<sha256_hash>`.
* **Graceful Degradation:** Wrap connection hooks in `try-except` blocks. If Redis goes offline, the gateway logs a warning and disables caching, allowing the API to run directly (fail-safe).
* **Standard operations:**
  * `set(key, val_dict, ttl_seconds)`
  * `get(key) -> Optional[dict]`
  * `ping() -> bool` (used for the health check)

---

### Step 3: Gateway Endpoint Integration (Phase 2.3)

Update [gateway/main.py](file:///c:/Users/Biswajitrk/Documents/COdezzz/HarvestGate%20-%20ML%20Inference%20Gateway/gateway/main.py) to hook into the Cache Manager:

* **Lifespan Initialization:** Startup triggers connection pool creation; shutdown closes all sockets gracefully.
* **Read-Through / Write-Through Caching:**
  1. Intercept incoming request.
  2. Compute request signature SHA-256 hash.
  3. Query Redis -> if **HIT**, return immediately with `cached: true` and latency `< 2ms`.
  4. If **MISS**, run ONNX inference (and climate queries), save result in Redis with a **1-hour TTL**, and return `cached: false`.
* **Health Monitoring:** Update `GET /health` to run `ping()` and report true status of `redis_connected`.

---

### Step 4: Verification Testing

Develop a temporary validation script `test_cache.py` to confirm cache mechanics:

1. **Inference Latency Drop:** Assert first request is >50ms (`cached: false`) and second request is <5ms (`cached: true`).
2. **TTL Expiry:** Insert a key with a 2-second TTL, sleep 3 seconds, and assert the cache entry has expired.
3. **Graceful Failover:** Turn off the Redis docker container and assert `/recommend` still works successfully by falling back to live predictions.

---

## 🔒 Security Hardening Matrix

| Security Rule | Risk Addressed | Implementation Detail |
|---|---|---|
| **Redis AUTH** | Unauthorized access, data exfiltration | Password protection via `REDIS_PASSWORD` in `.env` |
| **Command Renaming** | Cache wiping, server compromise | Renaming `FLUSHALL` and `CONFIG` commands to `""` |
| **SHA-256 Keys** | Cache poisoning via collisions | Keys are collision-resistant SHA-256 hashes |
| **Internal Networking** | Unauthorized connections | Container does not publish ports publicly in production profiles |
| **Request Capping** | Memory exhaustion | Requests larger than 2KB are blocked prior to caching |
