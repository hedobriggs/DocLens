"""Bounded-cardinality metrics: never label by document, question or user."""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from time import perf_counter
from prometheus_client import Counter, Gauge, Histogram, REGISTRY
from prometheus_client.core import GaugeMetricFamily

DURATION = Histogram('doclens_operation_duration_seconds', 'Operation wall time', ['operation'],
                     buckets=(.01, .05, .1, .5, 1, 5, 15, 30, 60, 120, 300, 600))
OPERATIONS = Counter('doclens_operations_total', 'Completed operations', ['operation', 'outcome'])
TOKENS = Counter('doclens_gemini_tokens_total', 'Provider-reported tokens', ['direction'])
COST = Counter('doclens_gemini_estimated_cost_usd_total', 'Estimated cost using configured per-million token prices', ['currency'])
COST_SKIPPED = Counter('doclens_gemini_cost_estimate_skipped_total', 'Cost estimate omitted without affecting answers', ['reason'])
DOCUMENTS = Gauge('doclens_documents', 'Distinct documents in the local collection', ['collection'])
CHUNKS = Gauge('doclens_chunks', 'Points in the local collection', ['collection'])

@contextmanager
def measure(operation):
    start = perf_counter()
    outcome = 'success'
    try:
        yield
    except Exception:
        outcome = 'error'
        raise
    finally:
        DURATION.labels(operation).observe(perf_counter() - start)
        OPERATIONS.labels(operation, outcome).inc()

def tracked(operation):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with measure(operation):
                return function(*args, **kwargs)
        return wrapped
    return decorate

class StorageBytes:
    def collect(self):
        path = Path('qdrant_data')
        if path.exists():
            try:
                size = sum(p.stat().st_size for p in path.rglob('*') if p.is_file())
            except OSError:
                return  # Missing/unknown must not be represented as zero.
            yield GaugeMetricFamily('doclens_qdrant_storage_bytes', 'Local Qdrant files, apparent bytes', value=size)

REGISTRY.register(StorageBytes())
