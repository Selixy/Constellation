"""Camera feed widget with impact overlay."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

# Velocity above this threshold → red circle; below → green.
_HIGH_VELOCITY_THRESHOLD = 2.0
# How long (ms) an impact circle lives before fully fading out.
_IMPACT_LIFETIME_MS = 1500
# Radius of the impact circle (pixels in widget space).
_IMPACT_RADIUS_PX = 14
# Number of frames used for FPS sliding-window average.
_FPS_WINDOW = 30


@dataclass
class _ImpactOverlay:
    """Transient impact marker drawn on top of the video frame."""

    world_x: float
    world_y: float
    velocity: float
    born_at_ms: float = field(default_factory=lambda: time.monotonic() * 1000)

    def alpha(self) -> int:
        """Return current opacity 0-255, decreasing linearly over the lifetime."""
        elapsed = time.monotonic() * 1000 - self.born_at_ms
        ratio = max(0.0, 1.0 - elapsed / _IMPACT_LIFETIME_MS)
        return int(ratio * 220)

    def is_expired(self) -> bool:
        """Return True once the fade duration has elapsed."""
        return (time.monotonic() * 1000 - self.born_at_ms) >= _IMPACT_LIFETIME_MS


class CameraView(QWidget):
    """
    Displays a single camera stream (QPixmap from OpenCV BGR frame).

    Overlays detected impact positions as coloured circles that fade over
    ~1.5 s.  The widget is updated from a background thread via Qt signals
    so no mutex is required in application code.

    Signals
    -------
    calibration_requested(str)
        Emitted on double-click; carries the *camera_id*.
    """

    # ------------------------------------------------------------------ signals
    calibration_requested = Signal(str)
    _frame_ready = Signal(np.ndarray)   # internal, cross-thread

    def __init__(self, camera_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._camera_id = camera_id
        self._pixmap: QPixmap | None = None
        self._impacts: list[_ImpactOverlay] = []
        # Timestamps (monotonic seconds) of the last _FPS_WINDOW frames.
        self._frame_times: deque[float] = deque(maxlen=_FPS_WINDOW)
        self._fps: float = 0.0

        self.setMinimumSize(160, 120)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

        # Redraw timer to animate fading impacts even when no new frame arrives.
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(33)  # ~30 Hz
        self._repaint_timer.timeout.connect(self._on_repaint_tick)
        self._repaint_timer.start()

        # Cross-thread frame delivery.
        self._frame_ready.connect(self._apply_frame, Qt.QueuedConnection)

    # ------------------------------------------------------------------ public

    @property
    def camera_id(self) -> str:
        """Human-readable identifier for the camera this widget displays."""
        return self._camera_id

    @Slot(np.ndarray)
    def update_frame(self, frame: np.ndarray) -> None:
        """
        Accept a new BGR frame from any thread.

        The signal/slot mechanism guarantees the actual pixmap update happens
        on the GUI thread.
        """
        self._frame_ready.emit(frame)

    def add_impact(self, world_x: float, world_y: float, velocity: float) -> None:
        """
        Add a transient impact circle overlay.

        Parameters
        ----------
        world_x, world_y:
            World-space coordinates (used only for label; position is centred
            in this simple implementation — full homography mapping is done by
            MainWindow when it has the calibration matrix).
        velocity:
            Impact velocity scalar; controls circle colour.
        """
        self._impacts.append(_ImpactOverlay(world_x, world_y, velocity))

    # ------------------------------------------------------------------ slots

    @Slot(np.ndarray)
    def _apply_frame(self, frame: np.ndarray) -> None:
        """Convert BGR ndarray → QPixmap and update FPS counter (GUI thread)."""
        now = time.monotonic()
        self._frame_times.append(now)
        if len(self._frame_times) >= 2:
            span = self._frame_times[-1] - self._frame_times[0]
            if span > 0:
                self._fps = (len(self._frame_times) - 1) / span

        h, w = frame.shape[:2]
        rgb = frame[..., ::-1].copy()  # BGR → RGB, ensure contiguous
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self.update()

    @Slot()
    def _on_repaint_tick(self) -> None:
        """Expire old impacts and schedule a repaint if any are still active."""
        before = len(self._impacts)
        self._impacts = [imp for imp in self._impacts if not imp.is_expired()]
        if self._impacts or before != len(self._impacts):
            self.update()

    # ------------------------------------------------------------------ Qt overrides

    def paintEvent(self, event) -> None:  # noqa: N802
        """Render the frame, impact circles, and FPS counter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        if self._pixmap is None:
            painter.fillRect(0, 0, w, h, Qt.black)
            painter.setPen(Qt.white)
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                f"[{self._camera_id}]\nEn attente du flux…",
            )
            return

        # Scale pixmap while keeping aspect ratio.
        scaled = self._pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x_off = (w - scaled.width()) // 2
        y_off = (h - scaled.height()) // 2
        painter.fillRect(0, 0, w, h, Qt.black)
        painter.drawPixmap(x_off, y_off, scaled)

        # Scale factors from pixmap space to widget space.
        sx = scaled.width() / self._pixmap.width()
        sy = scaled.height() / self._pixmap.height()

        # Draw impact circles. world coords are mapped to the centre of the
        # visible image area (a real mapping needs the homography inverse).
        for imp in self._impacts:
            alpha = imp.alpha()
            if alpha <= 0:
                continue
            if imp.velocity >= _HIGH_VELOCITY_THRESHOLD:
                color = QColor(220, 40, 40, alpha)
            else:
                color = QColor(40, 200, 80, alpha)

            # Normalise world coords to [0,1] assuming ±5 m range.
            nx = (imp.world_x + 5.0) / 10.0
            ny = (imp.world_y + 5.0) / 10.0
            cx = int(x_off + nx * scaled.width())
            cy = int(y_off + ny * scaled.height())

            pen = QPen(color)
            pen.setWidth(3)
            painter.setPen(pen)
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), alpha // 3))
            painter.drawEllipse(cx - _IMPACT_RADIUS_PX, cy - _IMPACT_RADIUS_PX,
                                _IMPACT_RADIUS_PX * 2, _IMPACT_RADIUS_PX * 2)

        # FPS counter top-right.
        if self._fps > 0:
            painter.setPen(QColor(255, 230, 0, 220))
            fps_text = f"{self._fps:.1f} fps"
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(fps_text)
            painter.drawText(w - text_w - 8, fm.ascent() + 4, fps_text)

        painter.end()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Emit *calibration_requested* on double-click."""
        self.calibration_requested.emit(self._camera_id)
        super().mouseDoubleClickEvent(event)
