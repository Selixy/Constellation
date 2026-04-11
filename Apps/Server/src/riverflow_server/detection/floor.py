"""Floor plane detection via homography."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


class FloorDetector:
    """
    Stores the homography matrix from camera pixel space to floor world space.

    The homography is typically supplied by GridCalibrator after calibration.
    Provides helpers to map pixel coordinates to world coordinates via
    cv2.perspectiveTransform.
    """

    def __init__(self) -> None:
        self._H: np.ndarray | None = None  # 3×3 float64 homography matrix

    # ------------------------------------------------------------------
    # Homography management
    # ------------------------------------------------------------------

    def set_homography(self, H: np.ndarray) -> None:
        """Store a new 3×3 homography matrix (pixel → world).

        Parameters
        ----------
        H:
            3×3 numpy array of dtype float64 (or convertible).
        """
        H = np.asarray(H, dtype=np.float64)
        if H.shape != (3, 3):
            raise ValueError(f"Homography must be 3×3, got {H.shape}")
        self._H = H

    @property
    def is_calibrated(self) -> bool:
        """True if a valid homography matrix is stored."""
        return self._H is not None

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def pixel_to_world(self, px: float, py: float) -> tuple[float, float]:
        """Convert a single pixel coordinate to world space.

        Parameters
        ----------
        px, py:
            Pixel position (column, row).

        Returns
        -------
        (world_x, world_y) tuple.  Raises RuntimeError if not calibrated.
        """
        if self._H is None:
            raise RuntimeError("FloorDetector is not calibrated — call set_homography first.")
        pts = np.array([[[px, py]]], dtype=np.float64)  # shape (1, 1, 2)
        result = cv2.perspectiveTransform(pts, self._H)  # shape (1, 1, 2)
        wx, wy = float(result[0, 0, 0]), float(result[0, 0, 1])
        return wx, wy

    def pixels_to_world(self, points: np.ndarray) -> np.ndarray:
        """Convert an array of pixel coordinates to world space.

        Parameters
        ----------
        points:
            Array of shape (N, 2) with columns [px, py].

        Returns
        -------
        Array of shape (N, 2) with columns [world_x, world_y].
        Raises RuntimeError if not calibrated.
        """
        if self._H is None:
            raise RuntimeError("FloorDetector is not calibrated — call set_homography first.")
        points = np.asarray(points, dtype=np.float64)
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError(f"points must have shape (N, 2), got {points.shape}")
        # cv2.perspectiveTransform expects (1, N, 2)
        pts = points[np.newaxis, :, :]  # (1, N, 2)
        result = cv2.perspectiveTransform(pts, self._H)  # (1, N, 2)
        return result[0]  # (N, 2)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Serialize the homography matrix to a JSON file.

        Parameters
        ----------
        path:
            Destination file path.  Parent directory must exist.
        """
        path = Path(path)
        data: dict = {"homography": None}
        if self._H is not None:
            data["homography"] = self._H.tolist()
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        """Deserialize the homography matrix from a JSON file.

        Parameters
        ----------
        path:
            Source file path.
        """
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        h = data.get("homography")
        if h is not None:
            self._H = np.array(h, dtype=np.float64)
        else:
            self._H = None
