import numpy as np
import cv2
from pathlib import Path
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, 
    QLabel, QDialog, QGroupBox, QMessageBox, QProgressDialog
)
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QKeyEvent
from PySide6.QtCore import Qt

def imread_japanese(filename: str, flags=cv2.IMREAD_COLOR):
    """日本語パスを含む画像読み込みの回避策"""
    try:
        n = np.fromfile(filename, np.uint8)
        img = cv2.imdecode(n, flags)
        return img
    except Exception:
        return None

class OutlierDetectorWindow(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Outlier Detector - 外れ値（ミス）候補の検知")
        self.resize(750, 650)
        
        self.target_class_id = -1
        # matches = [{'img_idx': int, 'bbox_idx': int, 'line': str, 'score': float, 'reason': str}, ...]
        self.matches = [] 
        self.current_match_idx = 0
        
        self._build_ui()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # --- 上部: タグ選択とスキャン ---
        top_lay = QHBoxLayout()
        top_lay.addWidget(QLabel("検査するタグ:"))
        
        self.combo_tags = QComboBox()
        self.combo_tags.addItems(self.api.get_class_names())
        top_lay.addWidget(self.combo_tags)
        
        self.btn_scan = QPushButton("外れ値を計算 (Scan)")
        self.btn_scan.clicked.connect(self._scan_and_calculate)
        top_lay.addWidget(self.btn_scan)
        layout.addLayout(top_lay)
        
        # --- スコア・理由表示 ---
        self.lbl_status = QLabel("待機中...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.lbl_status.setFont(font)
        layout.addWidget(self.lbl_status)

        self.lbl_reason = QLabel("-")
        self.lbl_reason.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_reason.setStyleSheet("color: #ff6666;")
        layout.addWidget(self.lbl_reason)

        # --- 中央: 画像プレビュー ---
        self.lbl_image = QLabel("画像領域")
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setMinimumSize(400, 300)
        self.lbl_image.setStyleSheet("background-color: #1e1e1e; border: 2px solid #444; border-radius: 4px;")
        layout.addWidget(self.lbl_image, stretch=1)
        
        # --- 下部: ナビゲーション（スコア順） ---
        nav_group = QGroupBox("検知された外れ値候補をスコア順に確認")
        nav_lay = QHBoxLayout()
        self.btn_prev = QPushButton("◀ より正常なデータへ")
        self.btn_next = QPushButton("より異常なデータへ ▶")
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        nav_lay.addWidget(self.btn_prev)
        nav_lay.addWidget(self.btn_next)
        nav_group.setLayout(nav_lay)
        layout.addWidget(nav_group)
        
        if self.api.get_class_names():
            self.target_class_id = self.combo_tags.currentIndex()

    def _scan_and_calculate(self):
        self.target_class_id = self.combo_tags.currentIndex()
        if self.target_class_id < 0: return

        total = self.api.get_total_count()
        raw_candidates = []

        # UIフリーズ防止用プログレスダイアログ
        progress = QProgressDialog("特徴量を抽出中...", "キャンセル", 0, total, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        # 1. データ収集と特徴量抽出
        for i in range(total):
            if progress.wasCanceled():
                return
            progress.setValue(i)

            img_path, txt_path = self.api.get_data_at(i)
            if not txt_path or not txt_path.exists() or not img_path:
                continue
            
            try:
                lines = txt_path.read_text(encoding="utf-8").strip().splitlines()
                img = None # 遅延読み込み用
                
                for b_idx, line in enumerate(lines):
                    parts = line.split()
                    if len(parts) == 5 and int(parts[0]) == self.target_class_id:
                        xc, yc, w, h = map(float, parts[1:])
                        
                        # 幾何的特徴量
                        aspect = w / (h + 1e-6)
                        area = w * h
                        
                        # 視覚的特徴量 (HSVヒストグラム)
                        if img is None:
                            img = imread_japanese(str(img_path))
                        
                        hist = None
                        if img is not None:
                            ih, iw = img.shape[:2]
                            px_xc, px_yc, px_w, px_h = int(xc*iw), int(yc*ih), int(w*iw), int(h*ih)
                            cx1, cy1 = max(0, int(px_xc - px_w/2)), max(0, int(px_yc - px_h/2))
                            cx2, cy2 = min(iw, int(px_xc + px_w/2)), min(ih, int(px_yc + px_h/2))
                            
                            crop = img[cy1:cy2, cx1:cx2]
                            if crop.size > 0:
                                hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                                # HueとSaturationの2次元ヒストグラム
                                hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
                                cv2.normalize(hist, hist)
                                hist = hist.flatten()
                        
                        raw_candidates.append({
                            'img_idx': i, 'bbox_idx': b_idx, 'line': line,
                            'aspect': aspect, 'area': area, 'hist': hist
                        })
            except Exception as e:
                pass

        progress.setValue(total)

        if not raw_candidates:
            QMessageBox.information(self, "結果", "該当するタグのデータがありません。")
            return

        # 2. 中央値（ロバストな基準）の計算
        aspects = [c['aspect'] for c in raw_candidates]
        areas = [c['area'] for c in raw_candidates]
        med_aspect = np.median(aspects)
        med_area = np.median(areas)
        
        # 基準となるヒストグラム（平均を代用）
        valid_hists = [c['hist'] for c in raw_candidates if c['hist'] is not None]
        base_hist = np.mean(valid_hists, axis=0) if valid_hists else None

        # 3. 外れ値スコアの計算
        for c in raw_candidates:
            # Zスコア的な偏差（中央値からのズレの割合）
            diff_aspect = abs(c['aspect'] - med_aspect) / med_aspect
            diff_area = abs(c['area'] - med_area) / med_area
            
            diff_hist = 0
            if c['hist'] is not None and base_hist is not None:
                # Bhattacharyya距離 (0:完全一致, 1:全く違う)
                diff_hist = cv2.compareHist(c['hist'], base_hist, cv2.HISTCMP_BHATTACHARYYA)
            
            # 各指標を重み付けして合算
            score = (diff_aspect * 1.5) + (diff_area * 1.0) + (diff_hist * 3.0)
            c['score'] = score
            
            # 理由のテキスト生成
            reasons = []
            if diff_aspect > 0.5: reasons.append("縦横比が異常")
            if diff_area > 0.5: reasons.append("サイズが異常")
            if diff_hist > 0.6: reasons.append("色が大きく異なる")
            c['reason'] = " / ".join(reasons) if reasons else "正常の範囲内"

        # 4. スコアが高い（異常度が高い）順にソート
        raw_candidates.sort(key=lambda x: x['score'], reverse=True)
        self.matches = raw_candidates
        self.current_match_idx = 0
        
        self._update_view()

    def _update_view(self):
        self.btn_prev.setEnabled(self.current_match_idx < len(self.matches) - 1)
        self.btn_next.setEnabled(self.current_match_idx > 0)

        if not self.matches:
            return
            
        c = self.matches[self.current_match_idx]
        img_idx, line, score, reason = c['img_idx'], c['line'], c['score'], c['reason']
        img_path, txt_path = self.api.get_data_at(img_idx)
        tag_name = self.api.get_class_names()[self.target_class_id]
        
        # ランク付け（1位が最も異常）
        rank = self.current_match_idx + 1
        self.lbl_status.setText(f"異常度ランク: {rank}位 / {len(self.matches)}件  ({img_path.name})")
        self.lbl_reason.setText(f"スコア: {score:.2f} | 理由: {reason}")
        
        if self.api.get_current_index() != img_idx:
            self.api.navigate_to(img_idx)
            
        pix = QPixmap(str(img_path))
        if pix.isNull(): return
        
        parts = line.split()
        xc, yc, w, h = map(float, parts[1:])
        iw, ih = pix.width(), pix.height()
        
        px_xc, px_yc, px_w, px_h = int(xc * iw), int(yc * ih), int(w * iw), int(h * ih)
        pad = max(50, int(px_w * 1.0))
        crop_x, crop_y = max(0, px_xc - px_w//2 - pad), max(0, px_yc - px_h//2 - pad)
        crop_w, crop_h = min(iw - crop_x, px_w + pad*2), min(ih - crop_y, px_h + pad*2)
        
        if crop_w <= 0 or crop_h <= 0: return
        cropped = pix.copy(crop_x, crop_y, crop_w, crop_h)
        
        painter = QPainter(cropped)
        if painter.isActive():
            painter.setPen(QPen(QColor(255, 0, 255), max(2, int(crop_w/100))))
            painter.drawRect(px_xc - px_w//2 - crop_x, px_yc - px_h//2 - crop_y, px_w, px_h)
            painter.end()
        
        scaled = cropped.scaled(self.lbl_image.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.lbl_image.setPixmap(scaled)

    def _prev(self):
        # より正常なデータ（リストの後ろ）へ
        if self.current_match_idx < len(self.matches) - 1:
            self.current_match_idx += 1
            self._update_view()

    def _next(self):
        # より異常なデータ（リストの前）へ
        if self.current_match_idx > 0:
            self.current_match_idx -= 1
            self._update_view()

    
    def keyPressEvent(self, event: QKeyEvent):
        # 左キー または Aキー で「より正常なデータへ (◀)」
        if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_A:
            self._prev()
        # 右キー または Dキー で「より異常なデータへ (▶)」
        elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_D:
            self._next()
        else:
            super().keyPressEvent(event)

class OutlierDetectorEntry:
    def __init__(self, api):
        self.api = api
        self.window = None
        
    def setup_ui(self):
        self.btn = QPushButton("外れ値（ミス候補）検知")
        self.btn.clicked.connect(self._open_window)
        self.api.add_sidebar_widget(self.btn, "Anomaly Detector")
        
    def _open_window(self):
        if not self.window:
            self.window = OutlierDetectorWindow(self.api, parent=self.api._dialog)
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

def register_plugin(api):
    return OutlierDetectorEntry(api)