import sys
import cv2
import time
import numpy as np
import mediapipe as mp
from pythonosc.udp_client import SimpleUDPClient
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QCheckBox, QGroupBox, QSpinBox, QFormLayout,
    QSlider, QRadioButton, QButtonGroup, QScrollArea, QTabWidget, QDialog
)
from PyQt6.QtCore import QTimer, Qt, QPoint
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygon

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

class OSCManager:
    def __init__(self, ip="127.0.0.1", port=9000):
        self.ip = ip
        self.port = port
        self.client = SimpleUDPClient(self.ip, self.port)

    def send_pose(self, cam_idx, landmarks):
        if not landmarks: return
        args = []
        for lm in landmarks.landmark:
            args.extend([lm.x, lm.y, lm.z, lm.visibility])
        self.client.send_message(f"/mocap/pose/{cam_idx}", args)

    def send_feet(self, cam_idx, spatial_feet):
        args = []
        for (sx, sy) in spatial_feet:
            args.extend([float(sx), float(sy), 0.0, 1.0]) 
        if args:
            self.client.send_message(f"/mocap/feet/{cam_idx}", args)

    def send_impact(self, cam_idx, sx, sy):
        self.client.send_message(f"/mocap/impact/{cam_idx}", [float(sx), float(sy), 1.0])

class FootTracker:
    def __init__(self):
        self.tracks = {}
        self.next_id = 0
        self.active_impacts = []

    def update(self, points, current_time):
        new_tracks = {}
        unmatched = points[:]
        new_impacts = []

        for tid, hist in self.tracks.items():
            if not unmatched:
                if len(hist) >= 2:
                    dy = hist[-1][1] - hist[-2][1]
                    if dy > 0.5: 
                        new_impacts.append(hist[-1][:2])
                continue

            last_pos = hist[-1][:2]
            dists = [np.hypot(p[0]-last_pos[0], p[1]-last_pos[1]) for p in unmatched]
            min_idx = int(np.argmin(dists)) if dists else -1
            
            if len(dists) > 0 and dists[min_idx] < 50:
                p = unmatched.pop(min_idx)
                hist.append((p[0], p[1], current_time))
                if len(hist) > 10: hist = hist[-10:]
                new_tracks[tid] = hist
                
                if len(hist) >= 3:
                    y0 = hist[-3][1]
                    y1 = hist[-2][1]
                    y2 = hist[-1][1]
                    dy_prev = y1 - y0
                    dy_curr = y2 - y1
                    
                    if dy_prev > 1.5 and abs(dy_curr) <= 0.5:
                        new_impacts.append((p[0], p[1]))
            else:
                if len(hist) >= 2:
                    dy = hist[-1][1] - hist[-2][1]
                    if dy > 0.5: new_impacts.append(last_pos)

        for p in unmatched:
            new_tracks[self.next_id] = [(p[0], p[1], current_time)]
            self.next_id += 1

        self.tracks = new_tracks

        for imp in new_impacts:
            self.active_impacts.append({'pos': imp, 'time': current_time})

        self.active_impacts = [imp for imp in self.active_impacts if current_time - imp['time'] < 0.5]
        return new_impacts


class CalibrationModal(QDialog):
    """Fenetre modale pour ajuster manuellement les 4 coins du sol pour une caméra"""
    def __init__(self, cam_idx, frame, current_pts, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Calibration Sol - Caméra {cam_idx}")
        self.setFixedSize(640, 480)
        self.setModal(True)
        
        self.frame = cv2.resize(frame, (640, 480))
        # Les points d'entrée sont en 320x240, on les scale x2
        self.pts = [[p[0]*2, p[1]*2] for p in current_pts] 
        self.dragging_idx = -1
        
        layout = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setFixedSize(640, 480)
        layout.addWidget(self.label)
        
        self.label.mousePressEvent = self.mousePressEvent
        self.label.mouseMoveEvent = self.mouseMoveEvent
        self.label.mouseReleaseEvent = self.mouseReleaseEvent
        
        btn_ok = QPushButton("Sauvegarder")
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)
        
        self.update_image()

    def update_image(self):
        img_copy = self.frame.copy()
        
        poly = np.array(self.pts, np.int32)
        cv2.fillPoly(img_copy, [poly], (0, 255, 0))
        img_copy = cv2.addWeighted(img_copy, 0.4, self.frame, 0.6, 0)
        cv2.polylines(img_copy, [poly], True, (0, 255, 0), 2)
        
        for p in self.pts:
            cv2.circle(img_copy, (int(p[0]), int(p[1])), 8, (0, 0, 255), -1)
            
        img_copy = cv2.cvtColor(img_copy, cv2.COLOR_BGR2RGB)
        qimg = QImage(img_copy.data, 640, 480, 640*3, QImage.Format.Format_RGB888)
        self.label.setPixmap(QPixmap.fromImage(qimg))

    def mousePressEvent(self, event):
        x, y = event.pos().x(), event.pos().y()
        for i, p in enumerate(self.pts):
            if np.hypot(p[0]-x, p[1]-y) < 20:
                self.dragging_idx = i
                break

    def mouseMoveEvent(self, event):
        if self.dragging_idx >= 0:
            x = max(0, min(640, event.pos().x()))
            y = max(0, min(480, event.pos().y()))
            self.pts[self.dragging_idx] = [x, y]
            self.update_image()

    def mouseReleaseEvent(self, event):
        self.dragging_idx = -1

    def get_result(self):
        # On remet à l'échelle pour l'appli (divise par 2)
        return [[int(p[0]/2), int(p[1]/2)] for p in self.pts]


class AppUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Constelation - Optical Flow + Mode Calibration")
        self.resize(1300, 700)
        
        self.osc = OSCManager()
        self.pose_tracker = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5, model_complexity=0)
        
        self.active_cams = {}
        # Format des poly par default pour chaque cam 320x240 (tl, tr, br, bl)
        self.calibrations = {} 
        self.foot_trackers = {} 
        
        self._init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33) 
        
        self.refresh_cameras()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        panel_scroll = QScrollArea()
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        panel_scroll.setWidget(control_panel)
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFixedWidth(320)
        
        # 1. Caméras
        cams_group = QGroupBox("1. Caméras du Couloir")
        self.cam_list_layout = QVBoxLayout()
        btn_refresh = QPushButton("Rafraîchir Caméras")
        btn_refresh.clicked.connect(self.refresh_cameras)
        cams_group.setLayout(self.cam_list_layout)
        
        # 2. Mode
        mode_group = QGroupBox("2. Mode de Capture")
        mode_layout = QVBoxLayout(mode_group)
        self.radio_pose = QRadioButton("Mocap Complet (Lourd)")
        self.radio_feet = QRadioButton("Impacts Sol (Optical Flow)")
        self.radio_feet.setChecked(True)
        self.mode_btn_group = QButtonGroup()
        self.mode_btn_group.addButton(self.radio_pose)
        self.mode_btn_group.addButton(self.radio_feet)
        mode_layout.addWidget(self.radio_pose)
        mode_layout.addWidget(self.radio_feet)
        
        self.slider_sens = QSlider(Qt.Orientation.Horizontal)
        self.slider_sens.setRange(50, 2000) 
        self.slider_sens.setValue(300)
        mode_layout.addWidget(QLabel("Taille min (mvt):"))
        mode_layout.addWidget(self.slider_sens)

        # 3. CALIBRATION
        spat_group = QGroupBox("3. Calibration Sol")
        spat_layout = QVBoxLayout(spat_group)
        btn_auto_calib = QPushButton("Détection Auto des Sols (IA)")
        btn_auto_calib.clicked.connect(self.auto_detect_floors)
        spat_layout.addWidget(btn_auto_calib)
        
        self.calib_buttons_layout = QVBoxLayout()
        spat_layout.addLayout(self.calib_buttons_layout)
        
        # 4. OSC
        osc_group = QGroupBox("4. Destination OSC")
        osc_layout = QFormLayout(osc_group)
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(9000)
        self.spin_port.valueChanged.connect(self.update_osc_port)
        osc_layout.addRow("Port (Local):", self.spin_port)
        
        control_layout.addWidget(btn_refresh)
        control_layout.addWidget(cams_group)
        control_layout.addWidget(mode_group)
        control_layout.addWidget(spat_group)
        control_layout.addWidget(osc_group)
        control_layout.addStretch()
        
        # Video Area
        self.video_scroll = QScrollArea()
        self.video_scroll.setWidgetResizable(True)
        self.video_label = QLabel("Cochez pour aligner le couloir")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        self.video_scroll.setWidget(self.video_label)
        
        layout.addWidget(panel_scroll)
        layout.addWidget(self.video_scroll, 1)

    def refresh_cameras(self):
        for cam_data in self.active_cams.values():
            cam_data['cap'].release()
        self.active_cams.clear()
        self.foot_trackers.clear()
        
        for i in reversed(range(self.cam_list_layout.count())): 
            widget = self.cam_list_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
            
        self.video_label.setText("Scan des ports USB...")
        QApplication.processEvents()
            
        found = False
        for i in range(5):
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2 if sys.platform.startswith('linux') else cv2.CAP_ANY)
            if cap.isOpened():
                cap.release()
                found = True
                cb = QCheckBox(f"Caméra {i}")
                cb.stateChanged.connect(lambda state, idx=i: self.toggle_camera(idx, state))
                self.cam_list_layout.addWidget(cb)
                
        if not found: self.video_label.setText("Aucune caméra.")
        else: self.video_label.setText("Cochez les caméras à activer")

    def toggle_camera(self, cam_idx, state):
        if state == Qt.CheckState.Checked.value:
            cap = cv2.VideoCapture(cam_idx)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            self.active_cams[cam_idx] = {'cap': cap, 'prev_gray': None} 
            self.foot_trackers[cam_idx] = FootTracker()
            # Grille par défaut
            self.calibrations[cam_idx] = [[100, 100], [220, 100], [320, 240], [0, 240]]
        else:
            if cam_idx in self.active_cams:
                self.active_cams[cam_idx]['cap'].release()
                del self.active_cams[cam_idx]
                if cam_idx in self.calibrations: del self.calibrations[cam_idx]
                if cam_idx in self.foot_trackers: del self.foot_trackers[cam_idx]
        
        self.refresh_calibration_ui()

    def refresh_calibration_ui(self):
        for i in reversed(range(self.calib_buttons_layout.count())): 
            w = self.calib_buttons_layout.itemAt(i).widget()
            if w: w.setParent(None)
            
        for cid in sorted(self.active_cams.keys()):
            btn = QPushButton(f"Ajuster Grille Cam {cid}")
            btn.clicked.connect(lambda checked, idx=cid: self.open_calibration_modal(idx))
            self.calib_buttons_layout.addWidget(btn)

    def open_calibration_modal(self, cam_idx):
        if cam_idx not in self.active_cams: return
        ret, frame = self.active_cams[cam_idx]['cap'].read()
        if not ret: return
        
        modal = CalibrationModal(cam_idx, frame, self.calibrations[cam_idx], self)
        if modal.exec() == QDialog.DialogCode.Accepted:
            self.calibrations[cam_idx] = modal.get_result()

    def auto_detect_floors(self):
        """ Détection de sol naïve via detection de lignes (Hough) """
        for cam_idx, cam_data in self.active_cams.items():
            ret, frame = cam_data['cap'].read()
            if not ret: continue
            
            frame_s = cv2.resize(frame, (320, 240))
            gray = cv2.cvtColor(frame_s, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
            
            # Heuristique super basique: on remonte de 20px au dessus de la ligne horizontale la plus basse
            h_y = 120 
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    if abs(y1 - y2) < 20: # Ligne pseudo-horizontale
                        h_y = max(h_y, y1 - 20)
            
            self.calibrations[cam_idx] = [[100, h_y], [220, h_y], [320, 240], [0, 240]]

    def update_osc_port(self):
        self.osc.port = self.spin_port.value()
        self.osc.client = SimpleUDPClient(self.osc.ip, self.osc.port)

    def update_frame(self):
        if not self.active_cams: return
            
        mode = "pose" if self.radio_pose.isChecked() else "feet"
        frames_to_show = []
        current_time = time.time()
        
        for cam_idx, cam_data in sorted(self.active_cams.items()):
            cap = cam_data['cap']
            ret, frame = cap.read()
            if not ret: continue                            
            frame_small = cv2.resize(frame, (320, 240))
            
            # --- MASQUE DU SOL COURANT ---
            pts = self.calibrations[cam_idx]
            floor_poly = np.array(pts, np.int32)
            
            # Matrice d'homographie de CETTE caméra
            src_pts = np.float32(pts)
            dst_pts = np.float32([[0, 1], [1, 1], [1, 0], [0, 0]]) # (tl, tr, br, bl) -> 0,1 est fond a gauche
            homography_matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
            
            if mode == "feet":
                gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
                
                if cam_data['prev_gray'] is None:
                    cam_data['prev_gray'] = gray
                else:                        
                    flow = cv2.calcOpticalFlowFarneback(cam_data['prev_gray'], gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                    cam_data['prev_gray'] = gray
                    mag = cv2.magnitude(flow[..., 0], flow[..., 1])
                    _, moving_mask = cv2.threshold(mag, 2.0, 255, cv2.THRESH_BINARY)
                    moving_mask = moving_mask.astype(np.uint8)
                    
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                    moving_mask = cv2.morphologyEx(moving_mask, cv2.MORPH_OPEN, kernel)
                    moving_mask = cv2.morphologyEx(moving_mask, cv2.MORPH_CLOSE, kernel)
                    
                    contours, _ = cv2.findContours(moving_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    min_area = self.slider_sens.value()
                    feet_img_positions = []
                    feet_spatial_positions = []
                    
                    for c in contours:
                        if cv2.contourArea(c) > min_area:
                            x, y, w, h = cv2.boundingRect(c)
                            vy_roi = flow[y:y+h, x:x+w, 1] 
                            
                            if np.mean(vy_roi) > 0.5: 
                                bottom_point = tuple(c[c[:, :, 1].argmax()][0])
                                cx, cy = int(bottom_point[0]), int(bottom_point[1])
                                
                                # Doit être DANS la zone dessinée
                                if cv2.pointPolygonTest(floor_poly, (float(cx), float(cy)), False) >= 0:
                                    feet_img_positions.append((cx, cy))
                                    
                                    pt32 = np.float32([[[cx, cy]]])
                                    sp_pt = cv2.perspectiveTransform(pt32, homography_matrix)[0][0]
                                    feet_spatial_positions.append((sp_pt[0], sp_pt[1]))
                                    
                                    cv2.rectangle(frame_small, (x, y), (x + w, y + h), (255, 255, 0), 1)
                                    cv2.circle(frame_small, (cx, cy), 6, (255, 0, 255), -1)
                    
                    tracker = self.foot_trackers[cam_idx]
                    new_impacts_img = tracker.update(feet_img_positions, current_time)
                    
                    if feet_spatial_positions:
                        self.osc.send_feet(cam_idx, feet_spatial_positions)
                    
                    for imp_img in new_impacts_img:
                        pt32 = np.float32([[[imp_img[0], imp_img[1]]]])
                        sp_pt = cv2.perspectiveTransform(pt32, homography_matrix)[0][0]
                        self.osc.send_impact(cam_idx, sp_pt[0], sp_pt[1])

                    # DEBUG IMP
                    for active_imp in tracker.active_impacts:
                        ix, iy = int(active_imp['pos'][0]), int(active_imp['pos'][1])
                        cv2.line(frame_small, (ix - 25, iy - 25), (ix + 25, iy + 25), (0, 0, 255), 5)
                        cv2.line(frame_small, (ix + 25, iy - 25), (ix - 25, iy + 25), (0, 0, 255), 5)
                        age = current_time - active_imp['time']
                        cv2.circle(frame_small, (ix, iy), int(age * 100), (0, 165, 255), 2)
                        
            else:
                rgb_frame = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
                results = self.pose_tracker.process(rgb_frame)
                if results.pose_landmarks:
                    mp_drawing.draw_landmarks(frame_small, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
                    self.osc.send_pose(cam_idx, results.pose_landmarks)

            # DESSIN GRILLE DE SOL CALIBRE 
            overlay = frame_small.copy()
            cv2.fillPoly(overlay, [floor_poly], (0, 255, 0))
            frame_small = cv2.addWeighted(overlay, 0.15, frame_small, 0.85, 0)
            cv2.polylines(frame_small, [floor_poly], True, (0, 255, 0), 2)

            cv2.putText(frame_small, f"Cam {cam_idx}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            frames_to_show.append(frame_small)

        if not frames_to_show: return
            
        final_frame = cv2.hconcat(frames_to_show)
        final_frame = cv2.cvtColor(final_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = final_frame.shape
        q_img = QImage(final_frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        
        pixmap = QPixmap.fromImage(q_img).scaledToHeight(self.video_scroll.height() - 20, Qt.TransformationMode.SmoothTransformation)
        self.video_label.setPixmap(pixmap)

    def closeEvent(self, event):
        for cam_data in self.active_cams.values(): cam_data['cap'].release()
        self.pose_tracker.close()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = AppUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
