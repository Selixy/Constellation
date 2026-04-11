"""Interactive floor-grid calibration widget."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from riverflow_server.calibration.grid import GridCalibrator


@dataclass
class _CalibPoint:
    """A single user-clicked calibration point."""

    px: float          # pixel x in original image
    py: float          # pixel y in original image
    col: int           # grid column index (0-based)
    row: int           # grid row index (0-based)


class _ImageClickLabel(QLabel):
    """
    A QLabel subclass that emits pixel coordinates when clicked.

    The label shows a scaled version of the source pixmap; this class
    converts click positions back to the original image space.
    """

    clicked_px = Signal(float, float)   # (px_x, px_y) in original image space

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 240)
        self._source_pixmap: QPixmap | None = None
        self._points: list[_CalibPoint] = []

    def set_pixmap(self, pixmap: QPixmap) -> None:
        """Store *pixmap* as source and display scaled version."""
        self._source_pixmap = pixmap
        self._refresh_display()

    def set_points(self, points: list[_CalibPoint]) -> None:
        """Update the displayed calibration points and repaint."""
        self._points = points
        self._refresh_display()

    # ------------------------------------------------------------------ internal

    def _refresh_display(self) -> None:
        if self._source_pixmap is None:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        scaled = self._source_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Draw cross markers and point numbers on top.
        if self._points:
            painter = QPainter(scaled)
            painter.setRenderHint(QPainter.Antialiasing)
            sx = scaled.width() / self._source_pixmap.width()
            sy = scaled.height() / self._source_pixmap.height()

            for i, pt in enumerate(self._points):
                cx = int(pt.px * sx)
                cy = int(pt.py * sy)
                color = QColor(255, 80, 0)
                pen = QPen(color, 2)
                painter.setPen(pen)
                arm = 8
                painter.drawLine(cx - arm, cy, cx + arm, cy)
                painter.drawLine(cx, cy - arm, cx, cy + arm)
                painter.drawEllipse(cx - 4, cy - 4, 8, 8)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(cx + 6, cy - 4, f"#{i + 1} ({pt.col},{pt.row})")
            painter.end()

        self.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._refresh_display()
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._source_pixmap is not None:
            w, h = self.width(), self.height()
            scaled_w = self._source_pixmap.width()
            scaled_h = self._source_pixmap.height()
            # Recompute scaled dimensions as Qt would render them.
            ratio = min(w / scaled_w, h / scaled_h)
            disp_w = int(scaled_w * ratio)
            disp_h = int(scaled_h * ratio)
            x_off = (w - disp_w) // 2
            y_off = (h - disp_h) // 2

            click_x = event.position().x() - x_off
            click_y = event.position().y() - y_off

            if 0 <= click_x <= disp_w and 0 <= click_y <= disp_h:
                orig_x = click_x / ratio
                orig_y = click_y / ratio
                self.clicked_px.emit(orig_x, orig_y)
        super().mousePressEvent(event)


class CalibrationWidget(QDialog):
    """
    Full-screen calibration dialog.

    Displays the last captured frame of a camera.  The user clicks image
    points corresponding to known grid intersections.  When ≥ 4 points are
    set, the homography can be computed via :class:`GridCalibrator`.

    Signals
    -------
    calibration_done(np.ndarray)
        Emitted with the 3×3 homography matrix after a successful computation.
    """

    calibration_done = Signal(np.ndarray)

    def __init__(
        self,
        camera_id: str,
        frame: np.ndarray,
        calibrator: GridCalibrator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera_id = camera_id
        self._calibrator = calibrator
        self._points: list[_CalibPoint] = []
        self._next_col = 0
        self._next_row = 0
        self._homography: np.ndarray | None = None

        self.setWindowTitle(f"Calibration — caméra « {camera_id} »")
        self.resize(1100, 700)

        self._build_ui()
        self.set_frame(frame)

    # ------------------------------------------------------------------ public

    def set_frame(self, frame: np.ndarray) -> None:
        """Display *frame* (BGR ndarray) in the image panel."""
        h, w = frame.shape[:2]
        rgb = frame[..., ::-1].copy()
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self._image_label.set_pixmap(pixmap)

    # ------------------------------------------------------------------ UI construction

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        # ---- Left: image area ----
        self._image_label = _ImageClickLabel()
        self._image_label.clicked_px.connect(self._on_image_click)
        root.addWidget(self._image_label, stretch=3)

        # ---- Right: control panel ----
        panel = QVBoxLayout()
        panel.setSpacing(8)
        root.addLayout(panel, stretch=1)

        # Grid dimensions group.
        grid_group = QGroupBox("Paramètres de grille")
        grid_layout = QVBoxLayout(grid_group)

        def _labeled_spin(label: str, lo: int, hi: int, default: int) -> QSpinBox:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            sb = QSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(default)
            row.addWidget(sb)
            grid_layout.addLayout(row)
            return sb

        def _labeled_dspin(label: str, lo: float, hi: float, default: float) -> QDoubleSpinBox:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(default)
            sb.setSuffix(" m")
            sb.setDecimals(3)
            row.addWidget(sb)
            grid_layout.addLayout(row)
            return sb

        self._cols_spin = _labeled_spin("Colonnes :", 2, 20, 4)
        self._rows_spin = _labeled_spin("Lignes :", 2, 20, 4)
        self._cell_w_spin = _labeled_dspin("Largeur cellule :", 0.01, 10.0, 0.5)
        self._cell_h_spin = _labeled_dspin("Hauteur cellule :", 0.01, 10.0, 0.5)

        # Next-point position label.
        self._next_label = QLabel()
        grid_layout.addWidget(self._next_label)
        self._update_next_label()

        panel.addWidget(grid_group)

        # Points list.
        pts_group = QGroupBox("Points placés")
        pts_layout = QVBoxLayout(pts_group)
        self._points_list = QListWidget()
        self._points_list.setMaximumHeight(200)
        pts_layout.addWidget(self._points_list)

        del_btn = QPushButton("Supprimer le point sélectionné")
        del_btn.clicked.connect(self._on_delete_point)
        pts_layout.addWidget(del_btn)

        clear_btn = QPushButton("Tout effacer")
        clear_btn.clicked.connect(self._on_clear_points)
        pts_layout.addWidget(clear_btn)

        panel.addWidget(pts_group)

        # Action buttons.
        self._compute_btn = QPushButton("Calculer l'homographie")
        self._compute_btn.setEnabled(False)
        self._compute_btn.clicked.connect(self._on_compute)
        panel.addWidget(self._compute_btn)

        self._save_btn = QPushButton("Sauvegarder")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        panel.addWidget(self._save_btn)

        panel.addStretch()

        # Standard close button.
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        panel.addWidget(buttons)

    # ------------------------------------------------------------------ slots

    @Slot(float, float)
    def _on_image_click(self, px: float, py: float) -> None:
        """Record a new calibration point at the clicked pixel position."""
        col = self._next_col
        row = self._next_row
        pt = _CalibPoint(px=px, py=py, col=col, row=row)
        self._points.append(pt)

        # Advance to the next grid position (row-major).
        n_cols = self._cols_spin.value()
        n_rows = self._rows_spin.value()
        self._next_col += 1
        if self._next_col >= n_cols:
            self._next_col = 0
            self._next_row += 1
        if self._next_row >= n_rows:
            self._next_col = 0
            self._next_row = 0

        self._refresh_points_list()
        self._image_label.set_points(self._points)
        self._update_next_label()
        self._compute_btn.setEnabled(len(self._points) >= 4)

    @Slot()
    def _on_delete_point(self) -> None:
        """Remove the currently selected point from the list."""
        row = self._points_list.currentRow()
        if row < 0 or row >= len(self._points):
            return
        self._points.pop(row)
        self._refresh_points_list()
        self._image_label.set_points(self._points)
        self._compute_btn.setEnabled(len(self._points) >= 4)
        self._update_next_label()

    @Slot()
    def _on_clear_points(self) -> None:
        """Remove all calibration points."""
        self._points.clear()
        self._next_col = 0
        self._next_row = 0
        self._refresh_points_list()
        self._image_label.set_points(self._points)
        self._compute_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._update_next_label()

    @Slot()
    def _on_compute(self) -> None:
        """Feed all points to GridCalibrator and compute the homography."""
        cell_w = self._cell_w_spin.value()
        cell_h = self._cell_h_spin.value()

        # GridCalibrator stub interface: add_point(px, py, col, row) then compute_homography().
        # We call add_point on each stored point.
        try:
            for pt in self._points:
                self._calibrator.add_point(pt.px, pt.py, pt.col, pt.row)
            H = self._calibrator.compute_homography()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Erreur de calibration",
                f"Impossible de calculer l'homographie :\n{exc}",
            )
            return

        if H is None:
            QMessageBox.warning(
                self,
                "Homographie invalide",
                "La matrice homographie n'a pas pu être calculée. "
                "Vérifiez que les points ne sont pas colinéaires.",
            )
            return

        self._homography = H
        self._save_btn.setEnabled(True)
        QMessageBox.information(
            self,
            "Succès",
            "Homographie calculée avec succès.\n"
            "Cliquez sur « Sauvegarder » pour l'appliquer.",
        )

    @Slot()
    def _on_save(self) -> None:
        """Emit calibration_done with the computed homography matrix."""
        if self._homography is not None:
            self.calibration_done.emit(self._homography)
            self.accept()

    # ------------------------------------------------------------------ helpers

    def _refresh_points_list(self) -> None:
        self._points_list.clear()
        for i, pt in enumerate(self._points):
            self._points_list.addItem(
                f"#{i + 1}  grille({pt.col},{pt.row})  "
                f"pixel({pt.px:.0f}, {pt.py:.0f})"
            )

    def _update_next_label(self) -> None:
        self._next_label.setText(
            f"Prochain clic → colonne {self._next_col}, ligne {self._next_row}"
        )
