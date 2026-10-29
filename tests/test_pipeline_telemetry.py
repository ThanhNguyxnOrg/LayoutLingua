import unittest
from layoutlingua.processing.telemetry import ExponentialMovingAverage, PipelineProgressTracker


def test_ema_rate_smoothing():
    ema = ExponentialMovingAverage(smoothing=0.25, initial_rate=10.0)
    assert abs(ema.value - 10.0) < 0.1

    # Extreme instant spike from an empty page (e.g. 500 pages/s)
    val = ema.update(500.0)
    # EMA must dampen the spike, not jump directly to 500
    assert val < 150.0
    assert val > 10.0


def test_pipeline_tracker_stage3_realistic_eta():
    tracker = PipelineProgressTracker(total_pages=96, total_segments=300)
    tracker.set_stage(3)

    # Simulate fast completion of first 7 pages (like in user screenshot)
    snap = {}
    for p in range(1, 8):
        snap = tracker.update_typesetting(done_pages=p)

    # Must NOT report ~1s remaining when 89 pages are left!
    eta = snap["eta_seconds"]
    assert eta > 5, f"Expected realistic ETA > 5s, got {eta}s"
    assert snap["current_page"] == 7
    assert snap["total_pages"] == 96
    assert snap["subtitle"] == "page 7 of 96"
    assert 55 <= snap["overall_pct"] <= 65


def test_pipeline_tracker_stage2_segments():
    tracker = PipelineProgressTracker(total_pages=96, total_segments=200)
    tracker.set_stage(2)

    snap = tracker.update_translation(done_segments=50)
    assert snap["subtitle"] == "segment 50 of 200"
    assert snap["segments_done"] == 50
    assert snap["segments_total"] == 200
    assert 5 <= snap["overall_pct"] <= 55
    # In stage 2, ETA includes translation remaining + future typesetting + write
    assert snap["eta_seconds"] > 10


def test_overall_pct_monotonic():
    tracker = PipelineProgressTracker(total_pages=20, total_segments=50)
    pcts = []

    tracker.set_stage(1)
    pcts.append(tracker.calculate_overall_pct())

    tracker.set_stage(2)
    for seg in (10, 25, 50):
        tracker.update_translation(seg)
        pcts.append(tracker.calculate_overall_pct())

    tracker.set_stage(3)
    for p in (5, 10, 20):
        tracker.update_typesetting(p)
        pcts.append(tracker.calculate_overall_pct())

    tracker.set_stage(4)
    pcts.append(tracker.calculate_overall_pct())

    # Strictly non-decreasing
    for i in range(len(pcts) - 1):
        assert pcts[i] <= pcts[i + 1]


class TestPipelineTelemetry(unittest.TestCase):
    def test_all(self) -> None:
        test_ema_rate_smoothing()
        test_pipeline_tracker_stage3_realistic_eta()
        test_pipeline_tracker_stage2_segments()
        test_overall_pct_monotonic()

