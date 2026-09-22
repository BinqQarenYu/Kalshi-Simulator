"""Unit & Invariant Tests for SystemResourceGovernor (Memory, CPU & GC Management)."""

import gc
import pytest
from app_3_autonomous_chef.system_governor import SystemResourceGovernor, get_system_governor, SystemResourceMetrics


def test_system_governor_initialization():
    governor = SystemResourceGovernor(
        rss_warning_mb=200.0,
        rss_critical_mb=500.0,
        metrics_cache_ttl_s=0.2,
    )
    metrics = governor.get_resource_metrics(force_refresh=True)
    assert isinstance(metrics, SystemResourceMetrics)
    assert metrics.cpu_cores_count > 0
    assert metrics.process_rss_mb >= 0.0
    assert metrics.system_ram_total_mb >= 0.0
    assert metrics.memory_status in ("OPTIMAL", "ELEVATED", "CRITICAL")
    assert isinstance(metrics.to_dict(), dict)


def test_gc_tuning_for_low_latency():
    governor = SystemResourceGovernor()
    orig_thresholds = gc.get_threshold()
    
    governor.tune_gc_for_low_latency()
    new_thresholds = gc.get_threshold()
    
    # Verify Gen 0 threshold was expanded
    assert new_thresholds[0] >= orig_thresholds[0]


def test_controlled_gc_sweep():
    governor = SystemResourceGovernor()
    res = governor.trigger_controlled_gc_sweep(generation=1)
    assert "reclaimed_objects" in res
    assert res["generation"] == 1


def test_metrics_caching_and_ttl():
    governor = SystemResourceGovernor(metrics_cache_ttl_s=1.0)
    m1 = governor.get_resource_metrics(force_refresh=True)
    m2 = governor.get_resource_metrics(force_refresh=False)
    
    # Should return cached object within TTL
    assert m1.timestamp == m2.timestamp

    # Force refresh should update timestamp
    m3 = governor.get_resource_metrics(force_refresh=True)
    assert m3 is not None


def test_memory_pressure_critical_detection():
    # Set critical threshold to 0.01 MB to test threshold trip logic
    governor = SystemResourceGovernor(rss_critical_mb=0.01)
    metrics = governor.get_resource_metrics(force_refresh=True)
    assert metrics.memory_status == "CRITICAL"
    assert metrics.is_pressure_critical is True
    assert governor._pressure_shed_count >= 1


def test_singleton_accessor():
    g1 = get_system_governor()
    g2 = get_system_governor()
    assert g1 is g2
