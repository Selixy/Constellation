"""Impact detection via optical-flow velocity analysis."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class ImpactEvent:
    """A single detected impact event."""

    camera_id: str
    zone_x: int        # grid column index of the impacted zone
    zone_y: int        # grid row index of the impacted zone
    world_x: float     # world-space X (or normalised 0-1 if no homography)
    world_y: float     # world-space Y (or normalised 0-1 if no homography)
    velocity: float    # average optical-flow magnitude in that zone (px/frame)
    timestamp: float = field(default_factory=time.time)


class ImpactDetector:
    """
    Detects floor impacts by computing dense optical flow between consecutive
    frames, computing per-zone velocity magnitude, and firing events when a
    velocity threshold is crossed.

    Output events carry world-space (x, y) positions (via homography if
    available, otherwise normalised 0-1) plus a velocity scalar, ready to be
    forwarded to the OSC sender.

    Parameters
    ----------
    grid_cols, grid_rows:
        Number of horizontal / vertical zones into which each frame is divided.
    velocity_threshold:
        Minimum mean velocity (pixels/frame) within a zone to trigger an event.
    min_area_ratio:
        Minimum fraction of a zone that must have non-zero flow to count it
        (filters sensor noise in nearly-static regions).  Range 0-1.
    farneback_params:
        Optional keyword overrides for cv2.calcOpticalFlowFarneback.
    """

    # Default Farneback parameters — tuned for real-time indoor use
    _DEFAULT_FB: dict = {
        "pyr_scale": 0.5,
        "levels": 3,
        "winsize": 15,
        "iterations": 3,
        "poly_n": 5,
        "poly_sigma": 1.2,
        "flags": 0,
    }

    def __init__(
        self,
        grid_cols: int = 8,
        grid_rows: int = 6,
        velocity_threshold: float = 2.0,
        min_area_ratio: float = 0.1,
        farneback_params: dict | None = None,
    ) -> None:
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.velocity_threshold = velocity_threshold
        self.min_area_ratio = min_area_ratio
        self._fb_params: dict = {**self._DEFAULT_FB, **(farneback_params or {})}

        self._prev_gray: np.ndarray | None = None  # previous greyscale frame
        self._H: np.ndarray | None = None          # optional homography (pixel→world)

    # ------------------------------------------------------------------
    # Homography
    # ------------------------------------------------------------------

    def update_homography(self, H: np.ndarray | None) -> None:
        """Set or clear the pixel→world homography matrix.

        Parameters
        ----------
        H:
            3×3 float64 array supplied by FloorDetector, or None to disable
            world-space conversion (events will carry normalised coords).
        """
        self._H = H if H is None else np.asarray(H, dtype=np.float64)

    # ------------------------------------------------------------------
    # Main processing
    # ------------------------------------------------------------------

    def process(self, frame: np.ndarray, camera_id: str) -> list[ImpactEvent]:
        """Analyse a new frame and return any detected impact events.

        Parameters
        ----------
        frame:
            BGR (or greyscale) frame from the camera, shape (H, W[, C]).
        camera_id:
            Identifier of the source camera, embedded in emitted events.

        Returns
        -------
        List of ImpactEvent (may be empty).
        """
        gray = self._to_gray(frame)

        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            # First frame or resolution change — nothing to compare yet
            self._prev_gray = gray
            return []

        # Dense optical flow
        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray,
            gray,
            None,
            **self._fb_params,
        )  # shape (H, W, 2)

        self._prev_gray = gray

        # Per-pixel velocity magnitude
        mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)  # (H, W)

        return self._detect_zone_impacts(mag, frame.shape, camera_id)

    # ------------------------------------------------------------------
    # Debug / overlay
    # ------------------------------------------------------------------

    def get_velocity_map(self, frame: np.ndarray) -> np.ndarray:
        """Return a BGR heatmap of optical-flow velocities.

        The current frame is used *only* to compute flow against the stored
        previous frame; the stored previous frame is NOT advanced so that
        ``process`` can still be called normally afterwards.

        If no previous frame is stored yet, a black image of the same size
        is returned.

        Parameters
        ----------
        frame:
            Current BGR (or greyscale) frame.

        Returns
        -------
        BGR heatmap of the same spatial resolution as *frame*.
        """
        gray = self._to_gray(frame)
        h, w = gray.shape[:2]

        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            return np.zeros((h, w, 3), dtype=np.uint8)

        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray,
            gray,
            None,
            **self._fb_params,
        )
        mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)

        # Normalise to 0-255 using a soft cap at 2× threshold for contrast
        cap = max(self.velocity_threshold * 2.0, 1.0)
        mag_clipped = np.clip(mag / cap, 0.0, 1.0)
        gray_heat = (mag_clipped * 255).astype(np.uint8)
        heatmap_bgr = cv2.applyColorMap(gray_heat, cv2.COLORMAP_JET)
        return heatmap_bgr

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_gray(frame: np.ndarray) -> np.ndarray:
        """Convert any frame (BGR, BGRA, grey) to single-channel uint8."""
        if frame.ndim == 2:
            return frame.astype(np.uint8) if frame.dtype != np.uint8 else frame
        if frame.shape[2] == 1:
            return frame[:, :, 0]
        if frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def _detect_zone_impacts(
        self,
        mag: np.ndarray,
        frame_shape: tuple,
        camera_id: str,
    ) -> list[ImpactEvent]:
        """Split *mag* into a grid and emit events for zones above threshold.

        Parameters
        ----------
        mag:
            Per-pixel velocity magnitude array, shape (H, W).
        frame_shape:
            Original frame shape (used for normalised coords fallback).
        camera_id:
            Camera identifier for emitted events.
        """
        h, w = mag.shape
        events: list[ImpactEvent] = []
        now = time.time()

        zone_h = h / self.grid_rows
        zone_w = w / self.grid_cols

        for gy in range(self.grid_rows):
            y0 = int(gy * zone_h)
            y1 = int((gy + 1) * zone_h)
            for gx in range(self.grid_cols):
                x0 = int(gx * zone_w)
                x1 = int((gx + 1) * zone_w)

                zone_mag = mag[y0:y1, x0:x1]
                if zone_mag.size == 0:
                    continue

                # Area filter: skip if too few pixels have meaningful flow
                active_fraction = float(np.count_nonzero(zone_mag > 0.5)) / zone_mag.size
                if active_fraction < self.min_area_ratio:
                    continue

                mean_vel = float(zone_mag.mean())
                if mean_vel < self.velocity_threshold:
                    continue

                # Zone centre in pixel space
                cx_px = (x0 + x1) * 0.5
                cy_px = (y0 + y1) * 0.5

                world_x, world_y = self._pixel_to_world(cx_px, cy_px, w, h)

                events.append(
                    ImpactEvent(
                        camera_id=camera_id,
                        zone_x=gx,
                        zone_y=gy,
                        world_x=world_x,
                        world_y=world_y,
                        velocity=mean_vel,
                        timestamp=now,
                    )
                )

        return events

    def _pixel_to_world(
        self,
        px: float,
        py: float,
        frame_w: int,
        frame_h: int,
    ) -> tuple[float, float]:
        """Convert a pixel position to world coordinates.

        If a homography is available it is applied; otherwise the position is
        normalised to [0, 1] in both axes.

        Parameters
        ----------
        px, py:
            Pixel position (column, row).
        frame_w, frame_h:
            Frame dimensions used for normalisation fallback.
        """
        if self._H is not None:
            pts = np.array([[[px, py]]], dtype=np.float64)
            result = cv2.perspectiveTransform(pts, self._H)
            return float(result[0, 0, 0]), float(result[0, 0, 1])
        # Normalised fallback
        return px / frame_w, py / frame_h
