"""
cache.py — Async Redis Cache Manager.

Handles authenticated async Redis operations, deterministic SHA-256 cache key
generation, and graceful failover logic (non-blocking gateway degradation).
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as aioredis

logger = logging.getLogger("harvestgate.cache")


class CacheManager:

    def __init__(self, redis_url: str, default_ttl: int = 3600):
        """
        Initialize the CacheManager.

        Args:
            redis_url: Authentication Redis URL (e.g. redis://:password@host:port)
            default_ttl: Cache TTL in seconds (default 3600s / 1 hour)
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.client: Optional[aioredis.Redis] = None
        self.is_connected = False

    async def connect(self) -> bool:
        """
        Initialize the connection pool and connect to Redis.

        Returns True on success, False if connection failed (graceful degradation).
        """
        try:
            logger.info("Connecting to Redis Cache...")
            # Instantiate async client with decoding response strings
            self.client = aioredis.from_url(
                self.redis_url, decode_responses=True, socket_connect_timeout=3.0
            )
            # Send ping to verify authentication and connection
            await self.client.ping()
            self.is_connected = True
            logger.info("Successfully connected to Redis Cache.")
            return True
        except Exception as e:
            self.is_connected = False
            self.client = None
            logger.warning(
                f"Redis Connection Failed: {e}. "
                f"Gateway will run in Graceful Degradation mode (no caching)."
            )
            return False

    async def disconnect(self):
        """Close connection pool sockets gracefully at shutdown."""
        if self.client:
            try:
                await self.client.close()
                logger.info("Closed Redis connection pool.")
            except Exception as e:
                logger.error(f"Error during Redis close: {e}")
            finally:
                self.client = None
                self.is_connected = False

    def make_cache_key(self, prefix: str, payload: dict) -> str:
        """
        Generate a deterministic, collision-resistant SHA-256 key from a dictionary payload.

        Sorts dictionary keys before serialization to guarantee identical strings.
        """
        try:
            # Deterministic serialization: sort keys, strip whitespace, handle UTF-8
            serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
            return f"{prefix}:{payload_hash}"
        except Exception as e:
            logger.error(f"Failed to generate cache key: {e}")
            # Fallback to a random hash if serialization fails (defense-in-depth)
            dummy = str(payload)
            dummy_hash = hashlib.sha256(dummy.encode("utf-8")).hexdigest()
            return f"{prefix}:fallback:{dummy_hash}"

    async def get(self, key: str) -> Optional[dict]:
        """
        Retrieve and deserialize cached data.

        Returns:
            Decoded dictionary on HIT, None on MISS or Connection Failure.
        """
        if not self.is_connected or not self.client:
            return None

        try:
            val = await self.client.get(key)
            if val:
                logger.info(f"Cache HIT: {key}")
                return json.loads(val)
            return None
        except Exception as e:
            logger.error(f"Redis GET failed: {e}. Falling back to live execution.")
            # Graceful degrade: flag disconnected
            self.is_connected = False
            return None

    async def set(self, key: str, value: dict, ttl_seconds: Optional[int] = None) -> bool:
        """
        Serialize and cache data with a TTL.

        Returns:
            True on successful save, False on connection failure.
        """
        if not self.is_connected or not self.client:
            return False

        try:
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            serialized = json.dumps(value)
            await self.client.set(key, serialized, ex=ttl)
            logger.info(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Redis SET failed: {e}. Skipping cache save.")
            # Graceful degrade: flag disconnected
            self.is_connected = False
            return False

    async def ping(self) -> bool:
        """Check connection health. Returns True if healthy, False if down."""
        if not self.client:
            return False
        try:
            await self.client.ping()
            self.is_connected = True
            return True
        except Exception:
            self.is_connected = False
            return False
