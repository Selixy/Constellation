"""Manual grid rectification — camera-to-world homography via clicked points."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np


class _GridPoint(NamedTuple):
    pixel_x: float
    pixel_y: float
    grid_col: int
    grid_row: int


class GridCalibrator:
    """
    Stores manually-clicked pixel coordinates for grid corners and
    computes the camera-to-world homography via cv2.findHomography.

    Persists calibration data to JSON so it survives restarts.

    Usage
    -----
    1. Call ``set_grid_size`` to define the physical grid dimensions.
    2. For each known grid intersection, call ``add_point`` with the pixel
       position that was clicked and the corresponding grid column/row.
    3. Once ``is_ready`` is True (≥4 points), call ``compute_homography``
       to obtain the 3×3 matrix.
    """

    def __init__(self) -> None:
        self._cols: int = 0
        self._rows: int = 0
        self._cell_width: float = 1.0   # world units per column
        self._cell_height: float = 1.0  # world units per row
        # Keyed by (col, row) for O(1) deduplication
        self._points: dict[tuple[int, int], _GridPoint] = {}

    # ------------------------------------------------------------------
    # Grid configuration
    # ------------------------------------------------------------------

    def set_grid_size(
        self,
        cols: int,
        rows: int,
        cell_width: float,
        cell_height: float,
    ) -> None:
        """Define the physical dimensions of the calibration grid.

        Parameters
        ----------
        cols, rows:
            Number of grid columns and rows (intersections, not cells).
        cell_width, cell_height:
            World-space distance between adjacent grid lines.
        """
        if cols < 2 or rows < 2:
            raise ValueError("Grid must have at least 2 columns and 2 rows.")
        self._cols = cols
        self._rows = rows
        self._cell_width = float(cell_width)
        self._cell_height = float(cell_height)

    # ------------------------------------------------------------------
    # Point management
    # ------------------------------------------------------------------

    def add_point(
        self,
        pixel_x: float,
        pixel_y: float,
        grid_col: int,
        grid_row: int,
    ) -> None:
        """Register a clicked pixel position for a known grid intersection.

        If a point for the same (col, row) already exists it is replaced.

        Parameters
        ----------
        pixel_x, pixel_y:
            Position in camera image (pixels).
        grid_col, grid_row:
            Zero-based indices of the grid intersection.
        """
        self._points[(grid_col, grid_row)] = _GridPoint(
            pixel_x=float(pixel_x),
            pixel_y=float(pixel_y),
            grid_col=grid_col,
            grid_row=grid_row,
        )

    def remove_point(self, grid_col: int, grid_row: int) -> None:
        """Remove the registered point for (col, row) if it exists."""
        self._points.pop((grid_col, grid_row), None)

    @property
    def points_count(self) -> int:
        """Number of registered calibration points."""
        return len(self._points)

    @property
    def is_ready(self) -> bool:
        """True when ≥4 points are available to compute a homography."""
        return len(self._points) >= 4

    # ------------------------------------------------------------------
    # Coordinate accessors
    # ------------------------------------------------------------------

    def get_pixel_points(self) -> list[tuple[float, float]]:
        """Return pixel (x, y) for all registered points, sorted by (col, row)."""
        return [
            (p.pixel_x, p.pixel_y)
            for p in sorted(self._points.values(), key=lambda p: (p.grid_row, p.grid_col))
        ]

    def get_world_points(self) -> list[tuple[float, float]]:
        """Return world (x, y) for all registered points, sorted by (col, row).

        World coordinates are derived from (grid_col * cell_width, grid_row * cell_height).
        """
        return [
            (p.grid_col * self._cell_width, p.grid_row * self._cell_height)
            for p in sorted(self._points.values(), key=lambda p: (p.grid_row, p.grid_col))
        ]

    # ------------------------------------------------------------------
    # Homography computation
    # ------------------------------------------------------------------

    def compute_homography(self) -> np.ndarray | None:
        """Compute and return the pixel→world 3×3 homography matrix.

        Uses RANSAC to be robust against mis-clicks.

        Returns
        -------
        3×3 float64 numpy array, or None if fewer than 4 points are available.
        """
        if not self.is_ready:
            return None

        src = np.array(self.get_pixel_points(), dtype=np.float64)   # pixel coords
        dst = np.array(self.get_world_points(), dtype=np.float64)   # world coords

        H, _mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        # findHomography returns None if computation failed
        return H  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Serialize calibration state to JSON.

        Parameters
        ----------
        path:
            Destination file path.
        """
        path = Path(path)
        data = {
            "grid": {
                "cols": self._cols,
                "rows": self._rows,
                "cell_width": self._cell_width,
                "cell_height": self._cell_height,
            },
            "points": [
                {
                    "pixel_x": p.pixel_x,
                    "pixel_y": p.pixel_y,
                    "grid_col": p.grid_col,
                    "grid_row": p.grid_row,
                }
                for p in self._points.values()
            ],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        """Deserialize calibration state from JSON.

        Parameters
        ----------
        path:
            Source file path.
        """
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))

        grid = data.get("grid", {})
        self._cols = int(grid.get("cols", 0))
        self._rows = int(grid.get("rows", 0))
        self._cell_width = float(grid.get("cell_width", 1.0))
        self._cell_height = float(grid.get("cell_height", 1.0))

        self._points = {}
        for entry in data.get("points", []):
            col = int(entry["grid_col"])
            row = int(entry["grid_row"])
            self._points[(col, row)] = _GridPoint(
                pixel_x=float(entry["pixel_x"]),
                pixel_y=float(entry["pixel_y"]),
                grid_col=col,
                grid_row=row,
            )
