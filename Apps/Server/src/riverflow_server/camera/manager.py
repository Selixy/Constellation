"""Multi-camera manager — thread-safe, pure Python/OpenCV, no Qt dependency."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_S = 2.0


@dataclass
class CameraSource:
    """Describes a single camera source (index or URL/RTSP string)."""

    camera_id: str       # human-readable identifier
    source: int | str    # cv2.VideoCapture index or URL/path
    width: int = 1280
    height: int = 720
    fps: int = 30


class _CameraThread(threading.Thread):
    """Daemon thread that continuously captures frames from one camera source."""

    def __init__(self, source: CameraSource, on_frame: Callable[[str, np.ndarray], None] | None) -> None:
        super().__init__(name=f"cam-{source.camera_id}", daemon=True)
        self._source = source
        self._on_frame = on_frame

        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public helpers (called from the main thread)
    # ------------------------------------------------------------------

    def get_frame(self) -> np.ndarray | None:
        """Return the latest captured frame (copy), or *None* if not yet available."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self) -> None:
        """Signal the capture loop to exit and wait for the thread to finish."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _open_capture(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self._source.source)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._source.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._source.height)
        cap.set(cv2.CAP_PROP_FPS, self._source.fps)
        return cap

    def run(self) -> None:  # noqa: D102
        cam_id = self._source.camera_id
        logger.info("Camera '%s': starting capture thread", cam_id)

        while not self._stop_event.is_set():
            cap = self._open_capture()

            if not cap.isOpened():
                logger.warning("Camera '%s': failed to open '%s', retrying in %.1fs",
                               cam_id, self._source.source, _RECONNECT_DELAY_S)
                cap.release()
                self._stop_event.wait(_RECONNECT_DELAY_S)
                continue

            logger.info("Camera '%s': capture opened successfully", cam_id)

            while not self._stop_event.is_set():
                ok, frame = cap.read()

                if not ok or frame is None:
                    logger.warning("Camera '%s': read failed, attempting reconnect in %.1fs",
                                   cam_id, _RECONNECT_DELAY_S)
                    break  # outer loop will reconnect

                with self._lock:
                    self._frame = frame

                if self._on_frame is not None:
                    try:
                        self._on_frame(cam_id, frame)
                    except Exception:
                        logger.exception("Camera '%s': exception in on_frame callback", cam_id)

            cap.release()

            if not self._stop_event.is_set():
                self._stop_event.wait(_RECONNECT_DELAY_S)

        logger.info("Camera '%s': capture thread stopped", cam_id)


@dataclass
class CameraManager:
    """
    Manages N camera streams, each running in its own capture thread.

    Consumers call :meth:`get_frame` to obtain the latest frame (pull model)
    or subscribe via the *on_frame* callback for a push model.

    Example::

        manager = CameraManager(
            sources=[CameraSource("cam0", 0)],
            on_frame=lambda cid, frame: print(cid, frame.shape),
        )
        manager.start()
        ...
        manager.stop()
    """

    sources: list[CameraSource] = field(default_factory=list)
    on_frame: Callable[[str, np.ndarray], None] | None = field(default=None, repr=False)

    # Populated by start()
    _threads: dict[str, _CameraThread] = field(default_factory=dict, init=False, repr=False)
    _running: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start one capture thread per registered :class:`CameraSource`."""
        if self._running:
            logger.warning("CameraManager.start() called but already running")
            return

        self._threads = {}
        for src in self.sources:
            t = _CameraThread(src, self.on_frame)
            self._threads[src.camera_id] = t
            t.start()

        self._running = True
        logger.info("CameraManager started with %d camera(s)", len(self._threads))

    def stop(self) -> None:
        """Stop all capture threads gracefully and wait for them to finish."""
        if not self._running:
            return

        for t in self._threads.values():
            t.stop()

        for t in self._threads.values():
            t.join(timeout=5.0)
            if t.is_alive():
                logger.warning("Camera '%s': thread did not stop within timeout", t.name)

        self._threads.clear()
        self._running = False
        logger.info("CameraManager stopped")

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------

    def get_frame(self, camera_id: str) -> np.ndarray | None:
        """
        Return the latest frame for *camera_id* (thread-safe copy).

        Returns *None* if *camera_id* is unknown or no frame has been
        captured yet.
        """
        t = self._threads.get(camera_id)
        if t is None:
            logger.debug("get_frame: unknown camera_id '%s'", camera_id)
            return None
        return t.get_frame()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_cameras(self) -> list[str]:
        """Return the IDs of all currently active camera threads."""
        return list(self._threads.keys())

    def add_source(self, source: CameraSource) -> None:
        """
        Dynamically add and start a new camera source.

        If the manager is already running the thread is started immediately.
        If a source with the same *camera_id* is already present, a warning
        is logged and the call is ignored.
        """
        if source.camera_id in self._threads:
            logger.warning("add_source: camera_id '%s' already registered", source.camera_id)
            return
        self.sources.append(source)
        if self._running:
            t = _CameraThread(source, self.on_frame)
            self._threads[source.camera_id] = t
            t.start()

    def remove_source(self, camera_id: str) -> None:
        """Stop and remove the camera thread for *camera_id*."""
        t = self._threads.pop(camera_id, None)
        if t is None:
            logger.warning("remove_source: camera_id '%s' not found", camera_id)
            return
        t.stop()
        t.join(timeout=5.0)
        self.sources = [s for s in self.sources if s.camera_id != camera_id]
