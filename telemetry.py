from prometheus_client import Counter, Histogram
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

# 1. Prometheus Metrics Definitions
REQUEST_COUNT = Counter(
    "higala_request_total", 
    "Total requests processed by Higala Express services",
    ["method", "endpoint"]
)

REQUEST_LATENCY = Histogram(
    "higala_request_duration_seconds", 
    "Request latency in seconds",
    ["endpoint"]
)

# 2. OpenTelemetry Tracer Setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer("higala.express.tracer")

# For local visibility, we add a console span exporter (can be swapped for OTLP exporter later)
span_processor = SimpleSpanProcessor(ConsoleSpanExporter())
trace.get_tracer_provider().add_span_processor(span_processor)