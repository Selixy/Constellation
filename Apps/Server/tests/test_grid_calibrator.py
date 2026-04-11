"""Tests for GridCalibrator."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from riverflow_server.calibration.grid import GridCalibrator

# ---------------------------------------------------------------------------
# Four point pairs that form a square in both pixel and world space.
# API: add_point(pixel_x, pixel_y, grid_col, grid_row)
# World coords derived by implementation: col * cell_width, row * cell_height
# With default cell_width=cell_height=1.0: world = (col, row)
# ---------------------------------------------------------------------------
_FOUR_POINTS = [
    # (pixel_x, pixel_y, grid_col, grid_row)
    (0.0,   0.0,   0, 0),
    (100.0, 0.0,   1, 0),
    (100.0, 100.0, 1, 1),
    (0.0,   100.0, 0, 1),
]


@pytest.fixture
def calibrator() -> GridCalibrator:
    return GridCalibrator()


@pytest.fixture
def calibrator_with_four_points() -> GridCalibrator:
    c = GridCalibrator()
    c.set_grid_size(cols=2, rows=2, cell_width=1.0, cell_height=1.0)
    for px, py, col, row in _FOUR_POINTS:
        c.add_point(px, py, col, row)
    return c


# ---------------------------------------------------------------------------
# add_point / remove_point
# ---------------------------------------------------------------------------

class TestAddRemovePoint:
    def test_add_single_point(self, calibrator: GridCalibrator) -> None:
        calibrator.add_point(10.0, 20.0, 0, 0)
        assert calibrator.points_count == 1

    def test_add_multiple_points(self, calibrator: GridCalibrator) -> None:
        calibrator.add_point(0.0, 0.0, 0, 0)
        calibrator.add_point(100.0, 0.0, 1, 0)
        calibrator.add_point(100.0, 100.0, 1, 1)
        assert calibrator.points_count == 3

    def test_remove_existing_point(self, calibrator: GridCalibrator) -> None:
        calibrator.add_point(5.0, 5.0, 0, 0)
        calibrator.remove_point(0, 0)
        assert calibrator.points_count == 0

    def test_remove_nonexistent_point_is_noop(self, calibrator: GridCalibrator) -> None:
        calibrator.add_point(0.0, 0.0, 0, 0)
        calibrator.remove_point(99, 99)  # should not raise
        assert calibrator.points_count == 1

    def test_pixel_and_world_stay_in_sync(self, calibrator: GridCalibrator) -> None:
        calibrator.set_grid_size(cols=2, rows=2, cell_width=1.0, cell_height=1.0)
        for px, py, col, row in _FOUR_POINTS:
            calibrator.add_point(px, py, col, row)
        assert len(calibrator.get_pixel_points()) == len(calibrator.get_world_points())
        calibrator.remove_point(0, 0)
        assert len(calibrator.get_pixel_points()) == len(calibrator.get_world_points())

    def test_duplicate_col_row_replaces_existing(self, calibrator: GridCalibrator) -> None:
        calibrator.add_point(10.0, 10.0, 0, 0)
        calibrator.add_point(20.0, 20.0, 0, 0)  # same (col, row) → replaces
        assert calibrator.points_count == 1
        assert calibrator.get_pixel_points()[0] == (20.0, 20.0)


# ---------------------------------------------------------------------------
# is_ready property
# ---------------------------------------------------------------------------

class TestIsReady:
    def test_false_with_zero_points(self, calibrator: GridCalibrator) -> None:
        assert calibrator.is_ready is False

    def test_false_with_three_points(self, calibrator: GridCalibrator) -> None:
        for px, py, col, row in _FOUR_POINTS[:3]:
            calibrator.add_point(px, py, col, row)
        assert calibrator.is_ready is False

    def test_true_with_four_points(self, calibrator_with_four_points: GridCalibrator) -> None:
        assert calibrator_with_four_points.is_ready is True

    def test_true_with_more_than_four_points(self, calibrator: GridCalibrator) -> None:
        calibrator.set_grid_size(cols=3, rows=2, cell_width=1.0, cell_height=1.0)
        for px, py, col, row in _FOUR_POINTS:
            calibrator.add_point(px, py, col, row)
        calibrator.add_point(50.0, 50.0, 2, 0)
        assert calibrator.is_ready is True


# ---------------------------------------------------------------------------
# compute_homography()
# ---------------------------------------------------------------------------

class TestComputeHomography:
    def test_returns_none_with_zero_points(self, calibrator: GridCalibrator) -> None:
        assert calibrator.compute_homography() is None

    def test_returns_none_with_less_than_four_points(self, calibrator: GridCalibrator) -> None:
        for px, py, col, row in _FOUR_POINTS[:3]:
            calibrator.add_point(px, py, col, row)
        assert calibrator.compute_homography() is None

    def test_returns_3x3_matrix_with_four_points(
        self, calibrator_with_four_points: GridCalibrator
    ) -> None:
        H = calibrator_with_four_points.compute_homography()
        assert H is not None
        assert isinstance(H, np.ndarray)
        assert H.shape == (3, 3)

    def test_returns_float64_matrix(
        self, calibrator_with_four_points: GridCalibrator
    ) -> None:
        H = calibrator_with_four_points.compute_homography()
        assert H is not None
        assert H.dtype == np.float64

    def test_homography_maps_known_points_correctly(
        self, calibrator_with_four_points: GridCalibrator
    ) -> None:
        import cv2
        H = calibrator_with_four_points.compute_homography()
        assert H is not None
        px, py, col, row = _FOUR_POINTS[0]  # (0,0) → world (0,0)
        pts = np.array([[[px, py]]], dtype=np.float64)
        result = cv2.perspectiveTransform(pts, H)
        wx, wy = result[0, 0, 0], result[0, 0, 1]
        assert pytest.approx(wx, abs=1e-3) == float(col)
        assert pytest.approx(wy, abs=1e-3) == float(row)


# ---------------------------------------------------------------------------
# save / load JSON round-trip
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_round_trip_points(
        self, calibrator_with_four_points: GridCalibrator, tmp_path: Path
    ) -> None:
        path = tmp_path / "grid.json"
        calibrator_with_four_points.save(path)
        c2 = GridCalibrator()
        c2.load(path)
        assert c2.points_count == calibrator_with_four_points.points_count

    def test_round_trip_homography_recomputable_after_load(
        self, calibrator_with_four_points: GridCalibrator, tmp_path: Path
    ) -> None:
        path = tmp_path / "grid.json"
        calibrator_with_four_points.save(path)
        c2 = GridCalibrator()
        c2.load(path)
        H2 = c2.compute_homography()
        assert H2 is not None
        assert H2.shape == (3, 3)

    def test_save_creates_valid_json(
        self, calibrator_with_four_points: GridCalibrator, tmp_path: Path
    ) -> None:
        path = tmp_path / "grid.json"
        calibrator_with_four_points.save(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "points" in data

    def test_load_empty_points_gives_zero_count(
        self, calibrator: GridCalibrator, tmp_path: Path
    ) -> None:
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"grid": {}, "points": []}), encoding="utf-8")
        calibrator.load(path)
        assert calibrator.points_count == 0
