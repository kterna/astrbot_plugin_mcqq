"""Unit tests for MetricsCollector."""

import pytest
from core.utils.metrics import MetricsCollector


def test_metrics_collector():
    collector = MetricsCollector()
    collector.increment("msg.received", 5)
    collector.record_latency("rcon.latency", 0.05)

    summary = collector.get_summary()
    assert summary["counters"]["msg.received"] >= 5
    assert "rcon.latency" in summary["latencies"]
    assert "mcqq_msg_received" in collector.export_prometheus()
