"""Tests for ImpactDetector (optical flow + ImpactEvent)."""

from __future__ import annotations

import numpy as np
import pytest

from riverflow_server.detection.impact import ImpactDetector, ImpactEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def detector() -> ImpactDetector:
    # Low threshold so motion in test frames triggers events.
    return ImpactDetector(velocity_threshold=0.5)


@pytest.fixture
def blank_frame() -> np.ndarray:
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def base_frame() -> np.ndarray:
    """Frame with a bright blob at one position."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:150, 190:270, :] = 200
    return frame


@pytest.fixture
def moved_frame() -> np.ndarray:
    """Same blob displaced by 10 px — simulates motion."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:150, 200:280, :] = 200
    return frame


# ---------------------------------------------------------------------------
# ImpactEvent dataclass fields
# ---------------------------------------------------------------------------

class TestImpactEvent:
    def test_has_required_fields(self) -> None:
        ev = ImpactEvent(
            camera_id="cam0",
            zone_x=2,
            zone_y=3,
            world_x=0.5,
            world_y=0.3,
            velocity=1.2,
        )
        assert ev.camera_id == "cam0"
        assert ev.zone_x == 2
        assert ev.zone_y == 3
        assert ev.world_x == pytest.approx(0.5)
        assert ev.world_y == pytest.approx(0.3)
        assert ev.velocity == pytest.approx(1.2)

    def test_has_timestamp(self) -> None:
        ev = ImpactEvent(
            camera_id="cam0", zone_x=0, zone_y=0,
            world_x=0.0, world_y=0.0, velocity=1.0,
        )
        assert isinstance(ev.timestamp, float)
        assert ev.timestamp > 0


# ---------------------------------------------------------------------------
# process() — no impact on identical frames
# ---------------------------------------------------------------------------

class TestProcessIdenticalFrames:
    def test_first_frame_returns_empty(
        self, detector: ImpactDetector, blank_frame: np.ndarray
    ) -> None:
        """First call has no previous frame → always empty."""
        events = detector.process(blank_frame, "cam0")
        assert list(events) == []

    def test_identical_frames_return_no_events(
        self, detector: ImpactDetector, blank_frame: np.ndarray
    ) -> None:
        detector.process(blank_frame, "cam0")  # seed previous frame
        events = detector.process(blank_frame, "cam0")
        assert list(events) == []


# ---------------------------------------------------------------------------
# process() — impact detected on motion
# ---------------------------------------------------------------------------

class TestProcessWithMotion:
    def test_returns_at_least_one_event(
        self,
        detector: ImpactDetector,
        base_frame: np.ndarray,
        moved_frame: np.ndarray,
    ) -> None:
        detector.process(base_frame, "cam0")   # seed
        events = list(detector.process(moved_frame, "cam0"))
        assert len(events) >= 1

    def test_events_are_impact_event_instances(
        self,
        detector: ImpactDetector,
        base_frame: np.ndarray,
        moved_frame: np.ndarray,
    ) -> None:
        detector.process(base_frame, "cam0")
        events = list(detector.process(moved_frame, "cam0"))
        assert len(events) >= 1
        assert all(isinstance(e, ImpactEvent) for e in events)

    def test_event_velocity_is_positive(
        self,
        detector: ImpactDetector,
        base_frame: np.ndarray,
        moved_frame: np.ndarray,
    ) -> None:
        detector.process(base_frame, "cam0")
        events = list(detector.process(moved_frame, "cam0"))
        assert len(events) >= 1
        assert all(e.velocity > 0.0 for e in events)

    def test_event_camera_id_matches(
        self,
        detector: ImpactDetector,
        base_frame: np.ndarray,
        moved_frame: np.ndarray,
    ) -> None:
        detector.process(base_frame, "camX")
        events = list(detector.process(moved_frame, "camX"))
        assert all(e.camera_id == "camX" for e in events)


# ---------------------------------------------------------------------------
# get_velocity_map()
# ---------------------------------------------------------------------------

class TestGetVelocityMap:
    def test_returns_zeros_before_any_process(
        self, detector: ImpactDetector, blank_frame: np.ndarray
    ) -> None:
        vmap = detector.get_velocity_map(blank_frame)
        assert isinstance(vmap, np.ndarray)
        assert vmap.ndim == 3
        assert vmap.shape[2] == 3  # BGR

    def test_returns_bgr_array_after_process(
        self,
        detector: ImpactDetector,
        base_frame: np.ndarray,
        moved_frame: np.ndarray,
    ) -> None:
        detector.process(base_frame, "cam0")
        vmap = detector.get_velocity_map(moved_frame)
        assert isinstance(vmap, np.ndarray)
        assert vmap.ndim == 3
        assert vmap.shape[2] == 3
        assert vmap.dtype == np.uint8

    def test_same_spatial_shape_as_input(
        self,
        detector: ImpactDetector,
        base_frame: np.ndarray,
        moved_frame: np.ndarray,
    ) -> None:
        detector.process(base_frame, "cam0")
        vmap = detector.get_velocity_map(moved_frame)
        assert vmap.shape[:2] == base_frame.shape[:2]


# ---------------------------------------------------------------------------
# Homography integration
# ---------------------------------------------------------------------------

class TestWithHomography:
    def test_process_without_homography_returns_normalised_coords(
        self,
        base_frame: np.ndarray,
        moved_frame: np.ndarray,
    ) -> None:
        detector = ImpactDetector(velocity_threshold=0.5)
        detector.process(base_frame, "cam0")
        events = list(detector.process(moved_frame, "cam0"))
        assert isinstance(events, list)
        # Without homography, coords should be in [0, 1]
        for e in events:
            assert 0.0 <= e.world_x <= 1.0
            assert 0.0 <= e.world_y <= 1.0

    def test_update_homography_does_not_crash(
        self,
        detector: ImpactDetector,
        base_frame: np.ndarray,
        moved_frame: np.ndarray,
    ) -> None:
        H = np.eye(3, dtype=np.float64)
        detector.update_homography(H)
        detector.process(base_frame, "cam0")
        events = list(detector.process(moved_frame, "cam0"))
        assert isinstance(events, list)

    def test_clear_homography_does_not_crash(
        self,
        detector: ImpactDetector,
        base_frame: np.ndarray,
        moved_frame: np.ndarray,
    ) -> None:
        H = np.eye(3, dtype=np.float64)
        detector.update_homography(H)
        detector.update_homography(None)
        detector.process(base_frame, "cam0")
        events = list(detector.process(moved_frame, "cam0"))
        assert isinstance(events, list)
