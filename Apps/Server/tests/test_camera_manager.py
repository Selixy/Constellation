"""Tests for CameraManager / _CameraThread."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

from riverflow_server.camera.manager import CameraManager, CameraSource, _CameraThread


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source(cam_id: str = "cam0", source: int = 0) -> CameraSource:
    return CameraSource(camera_id=cam_id, source=source, width=640, height=480, fps=30)


def _fake_frame() -> np.ndarray:
    return np.zeros((480, 640, 3), dtype=np.uint8)


def _mock_capture_ok(frames: list[np.ndarray] | None = None, stop_after: int = 3) -> MagicMock:
    """Return a mock VideoCapture that yields *stop_after* frames then stops."""
    cap = MagicMock()
    cap.isOpened.return_value = True

    frame = _fake_frame() if frames is None else frames[0]
    # Produce *stop_after* good reads, then a failing read
    side_effects = [(True, frame)] * stop_after + [(False, None)]
    cap.read.side_effect = side_effects
    return cap


# ---------------------------------------------------------------------------
# _CameraThread unit tests
# ---------------------------------------------------------------------------

class TestCameraThread:
    def test_get_frame_returns_none_before_start(self) -> None:
        """get_frame() must return None when the thread has not run yet."""
        src = _make_source()
        thread = _CameraThread(src, on_frame=None)
        assert thread.get_frame() is None

    def test_on_frame_callback_called(self) -> None:
        """on_frame callback should be called with (camera_id, frame) for each captured frame."""
        received: list[tuple[str, np.ndarray]] = []

        def cb(cam_id: str, frame: np.ndarray) -> None:
            received.append((cam_id, frame))

        src = _make_source("test_cam")
        thread = _CameraThread(src, on_frame=cb)

        mock_cap = _mock_capture_ok(stop_after=2)

        with patch("riverflow_server.camera.manager.cv2.VideoCapture", return_value=mock_cap):
            thread.start()
            # Give the thread time to process at least one frame
            deadline = time.monotonic() + 2.0
            while len(received) == 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            thread.stop()
            thread.join(timeout=3.0)

        assert len(received) >= 1
        cam_id, frame = received[0]
        assert cam_id == "test_cam"
        assert isinstance(frame, np.ndarray)

    def test_stop_terminates_thread(self) -> None:
        """stop() must signal the thread to exit and join() should succeed."""
        src = _make_source()
        frame = _fake_frame()

        # Endless successful reads until stop is called
        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.read.return_value = (True, frame)

        thread = _CameraThread(src, on_frame=None)

        with patch("riverflow_server.camera.manager.cv2.VideoCapture", return_value=cap):
            thread.start()
            time.sleep(0.05)  # let it loop a bit
            thread.stop()
            thread.join(timeout=3.0)

        assert not thread.is_alive()

    def test_reconnect_on_read_failure(self) -> None:
        """When cap.read() fails the thread should try to reconnect (open a new capture)."""
        src = _make_source()
        frame = _fake_frame()

        # First capture: immediately fails → triggers reconnect
        cap_fail = MagicMock()
        cap_fail.isOpened.return_value = True
        cap_fail.read.return_value = (False, None)  # always fails

        # Second capture: succeeds twice then we stop
        cap_ok = MagicMock()
        cap_ok.isOpened.return_value = True
        cap_ok.read.side_effect = [(True, frame), (True, frame), (False, None)]

        open_count = {"n": 0}
        def fake_open(source: int) -> MagicMock:
            open_count["n"] += 1
            return cap_fail if open_count["n"] == 1 else cap_ok

        thread = _CameraThread(src, on_frame=None)

        with patch("riverflow_server.camera.manager.cv2.VideoCapture", side_effect=fake_open):
            with patch("riverflow_server.camera.manager._RECONNECT_DELAY_S", 0.01):
                thread.start()
                deadline = time.monotonic() + 3.0
                while open_count["n"] < 2 and time.monotonic() < deadline:
                    time.sleep(0.01)
                thread.stop()
                thread.join(timeout=3.0)

        assert open_count["n"] >= 2, "Thread should have attempted a reconnect"

    def test_get_frame_returns_copy(self) -> None:
        """get_frame() must return a copy so that mutating it does not affect internal state."""
        src = _make_source()
        frame = _fake_frame()

        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.read.side_effect = [(True, frame), (False, None)]

        thread = _CameraThread(src, on_frame=None)

        with patch("riverflow_server.camera.manager.cv2.VideoCapture", return_value=cap):
            thread.start()
            deadline = time.monotonic() + 2.0
            result = None
            while result is None and time.monotonic() < deadline:
                result = thread.get_frame()
                time.sleep(0.01)
            thread.stop()
            thread.join(timeout=3.0)

        assert result is not None
        # Mutate the copy — internal frame should not change
        result[:] = 255
        second = thread.get_frame()
        # If second is not None, it should not have been affected
        if second is not None:
            assert not np.all(second == 255)


# ---------------------------------------------------------------------------
# CameraManager integration tests
# ---------------------------------------------------------------------------

class TestCameraManager:
    def test_get_frame_returns_none_before_start(self) -> None:
        """get_frame() must return None when the manager has not been started."""
        src = _make_source()
        manager = CameraManager(sources=[src])
        assert manager.get_frame("cam0") is None

    def test_get_frame_unknown_camera(self) -> None:
        """get_frame() with an unknown camera_id must return None."""
        manager = CameraManager(sources=[])
        manager.start()
        try:
            assert manager.get_frame("nonexistent") is None
        finally:
            manager.stop()

    def test_start_creates_threads(self) -> None:
        """start() should register one thread per source."""
        sources = [_make_source("c0"), _make_source("c1", source=1)]

        cap = MagicMock()
        cap.isOpened.return_value = False  # won't produce frames, just checks thread creation

        with patch("riverflow_server.camera.manager.cv2.VideoCapture", return_value=cap):
            with patch("riverflow_server.camera.manager._RECONNECT_DELAY_S", 0.01):
                manager = CameraManager(sources=sources)
                manager.start()
                assert sorted(manager.list_cameras()) == ["c0", "c1"]
                manager.stop()

    def test_stop_clears_threads(self) -> None:
        """After stop(), list_cameras() should be empty."""
        src = _make_source()
        cap = MagicMock()
        cap.isOpened.return_value = False

        with patch("riverflow_server.camera.manager.cv2.VideoCapture", return_value=cap):
            with patch("riverflow_server.camera.manager._RECONNECT_DELAY_S", 0.01):
                manager = CameraManager(sources=[src])
                manager.start()
                manager.stop()

        assert manager.list_cameras() == []
        assert not manager._running

    def test_on_frame_callback_forwarded(self) -> None:
        """The manager's on_frame callback should be forwarded to _CameraThread."""
        received: list[str] = []

        def cb(cam_id: str, frame: np.ndarray) -> None:
            received.append(cam_id)

        src = _make_source("fwd_cam")
        frame = _fake_frame()

        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.read.side_effect = [(True, frame)] * 5 + [(False, None)]

        with patch("riverflow_server.camera.manager.cv2.VideoCapture", return_value=cap):
            with patch("riverflow_server.camera.manager._RECONNECT_DELAY_S", 0.01):
                manager = CameraManager(sources=[src], on_frame=cb)
                manager.start()
                deadline = time.monotonic() + 2.0
                while len(received) == 0 and time.monotonic() < deadline:
                    time.sleep(0.01)
                manager.stop()

        assert "fwd_cam" in received

    def test_add_source_while_running(self) -> None:
        """add_source() while running should start the new thread immediately."""
        cap = MagicMock()
        cap.isOpened.return_value = False

        with patch("riverflow_server.camera.manager.cv2.VideoCapture", return_value=cap):
            with patch("riverflow_server.camera.manager._RECONNECT_DELAY_S", 0.01):
                manager = CameraManager(sources=[])
                manager.start()
                manager.add_source(_make_source("new_cam"))
                assert "new_cam" in manager.list_cameras()
                manager.stop()

    def test_double_start_is_ignored(self) -> None:
        """Calling start() twice should not create duplicate threads."""
        cap = MagicMock()
        cap.isOpened.return_value = False

        with patch("riverflow_server.camera.manager.cv2.VideoCapture", return_value=cap):
            with patch("riverflow_server.camera.manager._RECONNECT_DELAY_S", 0.01):
                manager = CameraManager(sources=[_make_source()])
                manager.start()
                manager.start()  # second call — should be a no-op
                assert len(manager.list_cameras()) == 1
                manager.stop()
