import pytest
import pybreaker

def test_circuit_breaker_trips():
    breaker = pybreaker.CircuitBreaker(fail_max=2, reset_timeout=30)

    def failing_api():
        raise ConnectionError("Service down")

    # 1st failure (count = 1)
    with pytest.raises(ConnectionError):
        breaker.call(failing_api)

    # 2nd failure hits fail_max=2, so the breaker opens immediately and raises CircuitBreakerError
    with pytest.raises(pybreaker.CircuitBreakerError):
        breaker.call(failing_api)