"""
gateway/router.py — Circuit Breaker and Routing orchestration for LLM calls.

Protects gateway availability by monitoring OpenRouter API failures. If the API
fails consecutively, it trips the circuit breaker to immediately return fallback
advisories instead of hanging the incoming request threads.
"""

import time
import logging

logger = logging.getLogger("harvestgate.router")


class LLMCircuitBreaker:
    """
    Implements a three-state Circuit Breaker pattern to protect the LLM gateway.
    States:
      - CLOSED: Healthy. Requests flow directly to the LLM API.
      - OPEN: Tripped. Requests are instantly blocked and returned using fallback.
      - HALF-OPEN: Recovery check. A single trial request is allowed through.
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.failure_count = 0
        self.last_state_change = time.time()

    def can_execute(self) -> bool:
        """Determines if the LLM API call can be executed under the current state."""
        now = time.time()
        
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # If the recovery timeout has expired, move to HALF-OPEN to test connection
            if now - self.last_state_change >= self.recovery_timeout:
                logger.info("Circuit breaker entering HALF-OPEN state. Permitting recovery trial.")
                self.state = "HALF-OPEN"
                self.last_state_change = now
                return True
            return False

        # In HALF-OPEN state, allow execution to verify if it works
        return True

    def record_success(self):
        """Records a successful API response, closing the circuit if it was open/half-open."""
        if self.state != "CLOSED":
            logger.info("Circuit breaker returned to CLOSED state. LLM API fully operational.")
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_state_change = time.time()

    def record_failure(self):
        """Records an API failure, tripping the circuit to OPEN if threshold is crossed."""
        self.failure_count += 1
        now = time.time()
        logger.warning(
            f"LLM API failure recorded ({self.failure_count}/{self.failure_threshold}). State: {self.state}"
        )

        if self.state == "HALF-OPEN" or self.failure_count >= self.failure_threshold:
            if self.state != "OPEN":
                logger.error(
                    f"Circuit breaker tripped to OPEN! Blocking LLM calls for {self.recovery_timeout} seconds."
                )
            self.state = "OPEN"
            self.last_state_change = now


# Global Circuit Breaker instance
circuit_breaker = LLMCircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
