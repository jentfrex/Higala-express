import pybreaker
import logging

logger = logging.getLogger("higala.resilience")

# Configure a circuit breaker:
# - fail_max: Number of failures before opening the circuit
# - reset_timeout: Seconds to wait before attempting to test the service again (half-open state)
external_service_breaker = pybreaker.CircuitBreaker(
    fail_max=3, 
    reset_timeout=30
)

@external_service_breaker
def call_external_service(api_func, *args, **kwargs):
    """
    Wrapper function that executes an external call protected by the circuit breaker.
    """
    return api_func(*args, **kwargs)