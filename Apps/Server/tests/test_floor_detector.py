"""Tests for FloorDetector (homography pixel→world)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from riverflow_server.detection.floor import FloorDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def detector() -> FloorDetector:
    return FloorDetector()


@pytest.fixture
def identity_detector() -> FloorDetector:
    """FloorDetector with the 3×3 identity homography set."""
    d = FloorDetector()
    d.set_homography(np.eye(3, dtype=np.float64))
    return d


# ---------------------------------------------------------------------------
# is_calibrated
# ---------------------------------------------------------------------------

class TestIsCalibrated:
    def test_false_on_init(self, detector: FloorDetector) -> None:
        assert detector.is_calibrated is False

    def test_true_after_set_homography(self, detector: FloorDetector) -> None:
        detector.set_homography(np.eye(3))
        assert detector.is_calibrated is True

    def test_false_after_load_null_homography(self, detector: FloorDetector, tmp_path: Path) -> None:
        """Loading a JSON file with null homography should clear calibration."""
        p = tmp_path / "floor.json"
        p.write_text(json.dumps({"homography": None}), encoding="utf-8")
        detector.set_homography(np.eye(3))  # pre-set so we can verify it clears
        detector.load(p)
        assert detector.is_calibrated is False


# ---------------------------------------------------------------------------
# set_homography validation
# ---------------------------------------------------------------------------

class TestSetHomography:
    def test_accepts_3x3_array(self, detector: FloorDetector) -> None:
        H = np.eye(3, dtype=np.float64)
        detector.set_homography(H)
        assert detector.is_calibrated

    def test_rejects_wrong_shape(self, detector: FloorDetector) -> None:
        with pytest.raises(ValueError, match="3×3"):
            detector.set_homography(np.eye(4))

    def test_converts_to_float64(self, detector: FloorDetector) -> None:
        H = np.eye(3, dtype=np.float32)
        detector.set_homography(H)
        # Internally stored as float64 — no exception means conversion worked
        assert detector.is_calibrated


# ---------------------------------------------------------------------------
# pixel_to_world with identity homography
# ---------------------------------------------------------------------------

class TestPixelToWorldIdentity:
    def test_origin_maps_to_origin(self, identity_detector: FloorDetector) -> None:
        wx, wy = identity_detector.pixel_to_world(0.0, 0.0)
        assert pytest.approx(wx, abs=1e-9) == 0.0
        assert pytest.approx(wy, abs=1e-9) == 0.0

    def test_arbitrary_point_preserved(self, identity_detector: FloorDetector) -> None:
        wx, wy = identity_detector.pixel_to_world(320.0, 240.0)
        assert pytest.approx(wx, abs=1e-6) == 320.0
        assert pytest.approx(wy, abs=1e-6) == 240.0

    def test_raises_when_not_calibrated(self, detector: FloorDetector) -> None:
        with pytest.raises(RuntimeError, match="not calibrated"):
            detector.pixel_to_world(0.0, 0.0)


# ---------------------------------------------------------------------------
# pixels_to_world (batch)
# ---------------------------------------------------------------------------

class TestPixelsToWorld:
    def test_batch_identity(self, identity_detector: FloorDetector) -> None:
        pts = np.array([[0.0, 0.0], [100.0, 200.0], [320.0, 240.0]])
        result = identity_detector.pixels_to_world(pts)
        assert result.shape == (3, 2)
        np.testing.assert_allclose(result, pts, atol=1e-6)

    def test_raises_wrong_shape(self, identity_detector: FloorDetector) -> None:
        bad = np.array([1.0, 2.0, 3.0])  # 1-D, not (N, 2)
        with pytest.raises(ValueError):
            identity_detector.pixels_to_world(bad)

    def test_raises_when_not_calibrated(self, detector: FloorDetector) -> None:
        pts = np.array([[0.0, 0.0]])
        with pytest.raises(RuntimeError, match="not calibrated"):
            detector.pixels_to_world(pts)


# ---------------------------------------------------------------------------
# Persistence (save / load round-trip)
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_round_trip(self, tmp_path: Path) -> None:
        """save then load must reconstruct the exact homography."""
        H = np.array(
            [[1.1, 0.2, 10.0],
             [0.0, 1.3, 20.0],
             [0.0, 0.0,  1.0]],
            dtype=np.float64,
        )
        d = FloorDetector()
        d.set_homography(H)
        path = tmp_path / "homography.json"
        d.save(path)

        d2 = FloorDetector()
        d2.load(path)
        assert d2.is_calibrated
        np.testing.assert_array_almost_equal(d2._H, H)

    def test_save_uncalibrated_creates_null_json(self, tmp_path: Path) -> None:
        d = FloorDetector()
        path = tmp_path / "empty.json"
        d.save(path)
        data = json.loads(path.read_text())
        assert data["homography"] is None

    def test_load_from_valid_file(self, tmp_path: Path) -> None:
        H_list = np.eye(3).tolist()
        path = tmp_path / "h.json"
        path.write_text(json.dumps({"homography": H_list}), encoding="utf-8")

        d = FloorDetector()
        d.load(path)
        assert d.is_calibrated
        np.testing.assert_array_almost_equal(d._H, np.eye(3))

    def test_load_overwrites_existing_homography(self, tmp_path: Path) -> None:
        d = FloorDetector()
        d.set_homography(np.eye(3) * 99)

        H_new = (np.eye(3) * 2).tolist()
        path = tmp_path / "new.json"
        path.write_text(json.dumps({"homography": H_new}), encoding="utf-8")
        d.load(path)
        np.testing.assert_array_almost_equal(d._H, np.eye(3) * 2)

    def test_pixel_to_world_consistent_after_load(self, tmp_path: Path) -> None:
        """pixel_to_world results must be identical before and after a save/load cycle."""
        H = np.array(
            [[2.0, 0.0, 5.0],
             [0.0, 2.0, 3.0],
             [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        d1 = FloorDetector()
        d1.set_homography(H)
        expected = d1.pixel_to_world(10.0, 20.0)

        path = tmp_path / "h2.json"
        d1.save(path)

        d2 = FloorDetector()
        d2.load(path)
        result = d2.pixel_to_world(10.0, 20.0)
        assert pytest.approx(result[0], abs=1e-6) == expected[0]
        assert pytest.approx(result[1], abs=1e-6) == expected[1]
