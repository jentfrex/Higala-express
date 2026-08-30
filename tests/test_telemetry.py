import pytest
from telemetry import REQUEST_COUNT, REQUEST_LATENCY, tracer

def test_prometheus_metrics_increment():
    initial_count = REQUEST_COUNT.labels(method="GET", endpoint="/health")._value.get()
    
    # Increment counter
    REQUEST_COUNT.labels(method="GET", endpoint="/health").inc()
    
    new_count = REQUEST_COUNT.labels(method="GET", endpoint="/health")._value.get()
    assert new_count == initial_count + 1

def test_opentelemetry_tracer_span():
    # Verify that a span can be created successfully using the configured tracer
    with tracer.start_as_current_span("test-delivery-span") as span:
        span.set_attribute("delivery.id", "DELV-9988")
        assert span.is_recording()