"""Main Qt window — RiverFlow Vision Server."""

from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from riverflow_server.calibration.grid import GridCalibrator
from riverflow_server.camera.manager import CameraManager, CameraSource
from riverflow_server.detection.impact import ImpactDetector
from riverflow_server.osc.sender import OscSender
from riverflow_server.ui.calibration_widget import CalibrationWidget
from riverflow_server.ui.camera_view import CameraView

logger = logging.getLogger(__name__)

# Default OSC target.
_DEFAULT_OSC_HOST = "127.0.0.1"
_DEFAULT_OSC_PORT = 9000


class _OscSettingsDialog(QDialog):
    """Simple dialog for editing the OSC host and port."""

    def __init__(self, host: str, port: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paramètres OSC")
        self.setFixedSize(320, 140)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._host_edit = QLineEdit(host)
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(port)

        form.addRow("Hôte UDP :", self._host_edit)
        form.addRow("Port UDP :", self._port_spin)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def host(self) -> str:
        """Return the entered host string."""
        return self._host_edit.text().strip()

    @property
    def port(self) -> int:
        """Return the entered port number."""
        return self._port_spin.value()


class MainWindow(QMainWindow):
    """
    Main application window for RiverFlow Vision Server.

    Layout
    ------
    - Menu bar  : Fichier / Caméras / Calibration / OSC
    - Toolbar   : shortcut actions
    - Central   : grid of :class:`CameraView` (up to 4)
    - Status bar: connection and FPS status

    Lifecycle
    ---------
    :meth:`showEvent` starts the :class:`CameraManager`.
    :meth:`closeEvent` stops it gracefully.
    """

    # Emitted (camera_id, frame) from the OpenCV callback → must be queued to the GUI thread.
    _frame_signal: Signal = Signal(str, np.ndarray)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RiverFlow Vision Server")
        self.resize(1280, 720)

        # OSC settings (mutable).
        self._osc_host = _DEFAULT_OSC_HOST
        self._osc_port = _DEFAULT_OSC_PORT

        # Core components.
        self._camera_manager = CameraManager()
        self._impact_detector: ImpactDetector | None = self._try_build_detector()
        self._osc_sender: OscSender | None = self._try_build_osc_sender()

        # camera_id → CameraView
        self._camera_views: dict[str, CameraView] = {}
        # camera_id → GridCalibrator
        self._calibrators: dict[str, GridCalibrator] = {}

        self._build_ui()

        # Connect the cross-thread frame signal (queued → runs on GUI thread).
        self._frame_signal.connect(self._on_frame_received, Qt.QueuedConnection)

        # Register the on_frame callback with the manager.
        self._camera_manager.on_frame = self._camera_frame_callback

        # Seed with a default demo camera (index 0); user can change via menu.
        self._add_camera("cam0", 0)

    # ------------------------------------------------------------------ UI construction

    def _build_ui(self) -> None:
        """Construct menu, toolbar, central widget, and status bar."""
        # ---- Central widget ----
        central = QWidget()
        self._central_layout = QGridLayout(central)
        self._central_layout.setContentsMargins(4, 4, 4, 4)
        self._central_layout.setSpacing(4)
        self.setCentralWidget(central)

        # ---- Status bar ----
        self._status_label = QLabel("Démarrage…")
        status_bar = QStatusBar()
        status_bar.addWidget(self._status_label)
        self.setStatusBar(status_bar)

        # ---- Menu bar ----
        menubar = self.menuBar()

        # Fichier
        file_menu = menubar.addMenu("Fichier")
        quit_action = QAction("Quitter", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Caméras
        cam_menu = menubar.addMenu("Caméras")

        add_cam_action = QAction("Ajouter une caméra…", self)
        add_cam_action.triggered.connect(self._on_add_camera)
        cam_menu.addAction(add_cam_action)

        remove_cam_action = QAction("Supprimer une caméra…", self)
        remove_cam_action.triggered.connect(self._on_remove_camera)
        cam_menu.addAction(remove_cam_action)

        # Calibration
        calib_menu = menubar.addMenu("Calibration")
        calib_action = QAction("Calibrer une caméra…", self)
        calib_action.triggered.connect(self._on_calibrate_from_menu)
        calib_menu.addAction(calib_action)

        # Paramètres OSC
        osc_menu = menubar.addMenu("OSC")
        osc_settings_action = QAction("Paramètres OSC…", self)
        osc_settings_action.triggered.connect(self._on_osc_settings)
        osc_menu.addAction(osc_settings_action)

        # ---- Toolbar ----
        toolbar = QToolBar("Outils", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        toolbar.addAction(add_cam_action)
        toolbar.addAction(remove_cam_action)
        toolbar.addSeparator()
        toolbar.addAction(calib_action)
        toolbar.addSeparator()
        toolbar.addAction(osc_settings_action)
        toolbar.addSeparator()
        toolbar.addAction(quit_action)

    # ------------------------------------------------------------------ camera management

    def _add_camera(self, camera_id: str, source: int | str) -> None:
        """Register a new camera, create its CameraView, and update the grid."""
        if camera_id in self._camera_views:
            logger.warning("Camera '%s' already present", camera_id)
            return

        view = CameraView(camera_id)
        view.calibration_requested.connect(self._on_calibration_requested)
        self._camera_views[camera_id] = view
        self._calibrators[camera_id] = GridCalibrator()

        src = CameraSource(camera_id=camera_id, source=source)
        self._camera_manager.add_source(src)

        self._rebuild_camera_grid()
        self._update_status()
        logger.info("Added camera '%s' (source=%s)", camera_id, source)

    def _remove_camera(self, camera_id: str) -> None:
        """Stop and remove a camera and its view."""
        if camera_id not in self._camera_views:
            return
        self._camera_manager.remove_source(camera_id)
        view = self._camera_views.pop(camera_id)
        self._calibrators.pop(camera_id, None)
        view.setParent(None)  # type: ignore[call-overload]
        view.deleteLater()
        self._rebuild_camera_grid()
        self._update_status()
        logger.info("Removed camera '%s'", camera_id)

    def _rebuild_camera_grid(self) -> None:
        """Re-layout all CameraView widgets in a responsive grid (1-4 cameras)."""
        # Remove all widgets from the grid without deleting them.
        while self._central_layout.count():
            item = self._central_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)  # type: ignore[call-overload]

        views = list(self._camera_views.values())
        n = len(views)
        if n == 0:
            placeholder = QLabel("Aucune caméra active.\nUtilisez le menu Caméras → Ajouter.")
            placeholder.setAlignment(Qt.AlignCenter)
            self._central_layout.addWidget(placeholder, 0, 0)
            return

        # Choose column count: 1 cam → 1 col, 2 → 2, 3-4 → 2 cols.
        cols = 1 if n == 1 else 2
        for idx, view in enumerate(views):
            r, c = divmod(idx, cols)
            self._central_layout.addWidget(view, r, c)

    # ------------------------------------------------------------------ frame pipeline

    def _camera_frame_callback(self, camera_id: str, frame: np.ndarray) -> None:
        """Called from a camera thread; marshals the frame to the GUI thread."""
        self._frame_signal.emit(camera_id, frame)

    @Slot(str, np.ndarray)
    def _on_frame_received(self, camera_id: str, frame: np.ndarray) -> None:
        """
        GUI-thread handler: update the relevant CameraView and run detection.
        """
        view = self._camera_views.get(camera_id)
        if view is None:
            return
        view.update_frame(frame)

        # Run impact detection if the detector is available.
        if self._impact_detector is None:
            return
        try:
            events = self._impact_detector.process(frame, camera_id)
        except Exception:
            logger.exception("ImpactDetector.process raised for camera '%s'", camera_id)
            return

        for event in events:
            view.add_impact(event.world_x, event.world_y, event.velocity)
            if self._osc_sender is not None:
                try:
                    self._osc_sender.send_impact(camera_id, event.world_x,
                                                  event.world_y, event.velocity)
                except Exception:
                    logger.exception("OscSender.send_impact raised for camera '%s'", camera_id)

    # ------------------------------------------------------------------ slots (menu actions)

    @Slot()
    def _on_add_camera(self) -> None:
        """Dialog: enter a camera ID and source, then add it."""
        camera_id, ok = QInputDialog.getText(
            self, "Ajouter une caméra", "Identifiant de la caméra :"
        )
        if not ok or not camera_id.strip():
            return
        camera_id = camera_id.strip()

        source_str, ok = QInputDialog.getText(
            self,
            "Source",
            "Source (index entier ou URL/RTSP) :",
            text="0",
        )
        if not ok:
            return
        source_str = source_str.strip()
        try:
            source: int | str = int(source_str)
        except ValueError:
            source = source_str

        self._add_camera(camera_id, source)

    @Slot()
    def _on_remove_camera(self) -> None:
        """Dialog: choose a camera to remove."""
        ids = list(self._camera_views.keys())
        if not ids:
            QMessageBox.information(self, "Supprimer", "Aucune caméra active.")
            return
        camera_id, ok = QInputDialog.getItem(
            self,
            "Supprimer une caméra",
            "Caméra à supprimer :",
            ids,
            editable=False,
        )
        if ok and camera_id:
            self._remove_camera(camera_id)

    @Slot()
    def _on_calibrate_from_menu(self) -> None:
        """Dialog: choose a camera then open CalibrationWidget."""
        ids = list(self._camera_views.keys())
        if not ids:
            QMessageBox.information(self, "Calibration", "Aucune caméra active.")
            return
        camera_id, ok = QInputDialog.getItem(
            self,
            "Calibrer une caméra",
            "Sélectionnez la caméra à calibrer :",
            ids,
            editable=False,
        )
        if ok and camera_id:
            self._open_calibration(camera_id)

    @Slot(str)
    def _on_calibration_requested(self, camera_id: str) -> None:
        """Triggered by double-click on a CameraView."""
        self._open_calibration(camera_id)

    def _open_calibration(self, camera_id: str) -> None:
        """Fetch the latest frame for *camera_id* and open CalibrationWidget."""
        frame = self._camera_manager.get_frame(camera_id)
        if frame is None:
            QMessageBox.warning(
                self,
                "Calibration",
                f"Pas de frame disponible pour la caméra « {camera_id} ».\n"
                "Vérifiez que la caméra est active.",
            )
            return

        calibrator = self._calibrators.setdefault(camera_id, GridCalibrator())
        dlg = CalibrationWidget(camera_id, frame, calibrator, parent=self)
        dlg.calibration_done.connect(
            lambda H, cid=camera_id: self._on_calibration_done(cid, H)
        )
        dlg.exec()

    @Slot()
    def _on_osc_settings(self) -> None:
        """Open the OSC settings dialog and rebuild the sender if confirmed."""
        dlg = _OscSettingsDialog(self._osc_host, self._osc_port, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._osc_host = dlg.host
            self._osc_port = dlg.port
            self._osc_sender = self._try_build_osc_sender()
            self._update_status()

    def _on_calibration_done(self, camera_id: str, H: np.ndarray) -> None:
        """Store the computed homography (future use by backend)."""
        logger.info(
            "Calibration done for camera '%s': homography shape=%s", camera_id, H.shape
        )
        self._status_label.setText(
            f"Calibration caméra « {camera_id} » enregistrée."
        )

    # ------------------------------------------------------------------ lifecycle

    def showEvent(self, event) -> None:  # noqa: N802
        """Start the camera manager when the window is first shown."""
        super().showEvent(event)
        if not self._camera_manager._running:
            self._camera_manager.start()
            self._update_status()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Stop the camera manager gracefully before closing."""
        logger.info("MainWindow closing — stopping CameraManager")
        self._camera_manager.stop()
        super().closeEvent(event)

    # ------------------------------------------------------------------ helpers

    def _try_build_detector(self) -> ImpactDetector | None:
        """Instantiate ImpactDetector if its implementation is available."""
        try:
            return ImpactDetector()
        except Exception:
            logger.warning("ImpactDetector not yet implemented; impacts disabled")
            return None

    def _try_build_osc_sender(self) -> OscSender | None:
        """Instantiate OscSender with current host/port settings."""
        try:
            return OscSender(self._osc_host, self._osc_port)  # type: ignore[call-arg]
        except Exception:
            logger.warning(
                "OscSender could not be created (%s:%s); OSC disabled",
                self._osc_host,
                self._osc_port,
            )
            return None

    def _update_status(self) -> None:
        """Refresh the status bar text."""
        n_cams = len(self._camera_views)
        osc_info = f"{self._osc_host}:{self._osc_port}" if self._osc_sender else "OSC désactivé"
        self._status_label.setText(
            f"{n_cams} caméra(s) active(s) — {osc_info}"
        )
