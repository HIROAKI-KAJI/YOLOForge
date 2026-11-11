from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, 
    QLabel, QDialog, QWidget
)
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QBrush, QMouseEvent, QWheelEvent
from PySide6.QtCore import Qt, Signal, QPoint, QRectF
import random

_CLASS_PALETTE = [
    QColor(255, 50, 50), QColor(50, 255, 50), QColor(50, 50, 255),
    QColor(255, 200, 50), QColor(255, 50, 255), QColor(50, 255, 255),
    QColor(255, 128, 0), QColor(128, 0, 255), QColor(0, 128, 128),
]

def _color_for_class(cid: int) -> QColor:
    if 0 <= cid < len(_CLASS_PALETTE):
        return _CLASS_PALETTE[cid]
    random.seed(cid)
    return QColor(random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))

class InteractiveCanvas(QWidget):
    labels_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._pixmap = QPixmap()
        self._bboxes = []
        self._class_names = []
        
        self.current_class_id = 0
        
        # ズームとパン（移動）の管理
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._is_panning = False
        self._pan_start_pos = QPoint()
        self._pan_start_offset = (0.0, 0.0)

        # 新規描画用
        self._is_drawing = False
        self._start_pos = QPoint()
        self._current_pos = QPoint()
        
        # 既存枠の調整用
        self._is_adjusting = False
        self._adjust_idx = -1
        self._adjust_action = None
        self._adjust_start_pos = (0, 0)
        self._orig_box = None
        
        # 描画レイアウトキャッシュ
        self._x_off = 0.0
        self._y_off = 0.0
        self._scaled_w = 0.0
        self._scaled_h = 0.0

    def set_data(self, pixmap, norm_bboxes, class_names):
        self._pixmap = pixmap
        self._bboxes = list(norm_bboxes)
        self._class_names = class_names
        
        # 画像が変わったらズームとパンをリセット
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        
        self._update_layout_cache()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout_cache()

    def _update_layout_cache(self):
        """現在のズームとパンを考慮して、画像とBBoxを描画する座標を計算する"""
        if self._pixmap.isNull() or self.width() == 0 or self.height() == 0:
            return
            
        pw, ph = self._pixmap.width(), self._pixmap.height()
        # 画面に収まる基本スケール
        base_scale = min(self.width() / pw, self.height() / ph)
        
        self._scaled_w = pw * base_scale * self._zoom
        self._scaled_h = ph * base_scale * self._zoom
        
        self._x_off = (self.width() - self._scaled_w) / 2 + self._pan_x
        self._y_off = (self.height() - self._scaled_h) / 2 + self._pan_y

    def wheelEvent(self, event: QWheelEvent):
        """Ctrl+スクロールでズームイン・アウト（マウスカーソル位置基準）"""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if self._pixmap.isNull(): return
            
            delta = event.angleDelta().y()
            if delta == 0: return
            
            # ズーム倍率の計算 (1.1倍ずつ変化)
            zoom_step = 1.1 if delta > 0 else 1.0 / 1.1
            new_zoom = max(0.1, min(20.0, self._zoom * zoom_step))
            
            if new_zoom == self._zoom: return
            
            # pos() ではなく position() を使用する
            mx = event.position().x()
            my = event.position().y()
            
            
            # 現在のマウスカーソル下にある画像の相対座標(0.0~1.0)
            nx = (mx - self._x_off) / self._scaled_w if self._scaled_w > 0 else 0.5
            ny = (my - self._y_off) / self._scaled_h if self._scaled_h > 0 else 0.5
            
            self._zoom = new_zoom
            
            # ズーム後のサイズを仮計算
            pw, ph = self._pixmap.width(), self._pixmap.height()
            base_scale = min(self.width() / pw, self.height() / ph)
            new_scaled_w = pw * base_scale * self._zoom
            new_scaled_h = ph * base_scale * self._zoom
            
            base_x_off = (self.width() - new_scaled_w) / 2
            base_y_off = (self.height() - new_scaled_h) / 2
            
            # カーソル位置の画像相対座標(nx, ny)がズレないようにパンを逆算
            self._pan_x = mx - base_x_off - nx * new_scaled_w
            self._pan_y = my - base_y_off - ny * new_scaled_h
            
            self._update_layout_cache()
            self.update()
        else:
            super().wheelEvent(event)

    def _hit_test(self, mx, my):
        if self._scaled_w == 0: return -1, None
        
        nx = (mx - self._x_off) / self._scaled_w
        ny = (my - self._y_off) / self._scaled_h
        
        nx_margin = 8 / self._scaled_w
        ny_margin = 8 / self._scaled_h
        
        for i in reversed(range(len(self._bboxes))):
            cid, xc, yc, w, h = self._bboxes[i]
            x1, y1 = xc - w/2, yc - h/2
            x2, y2 = xc + w/2, yc + h/2
            
            if abs(nx - x1) <= nx_margin and abs(ny - y1) <= ny_margin: return i, 'TL'
            if abs(nx - x2) <= nx_margin and abs(ny - y1) <= ny_margin: return i, 'TR'
            if abs(nx - x1) <= nx_margin and abs(ny - y2) <= ny_margin: return i, 'BL'
            if abs(nx - x2) <= nx_margin and abs(ny - y2) <= ny_margin: return i, 'BR'
            
        for i in reversed(range(len(self._bboxes))):
            cid, xc, yc, w, h = self._bboxes[i]
            x1, y1 = xc - w/2, yc - h/2
            x2, y2 = xc + w/2, yc + h/2
            if x1 <= nx <= x2 and y1 <= ny <= y2:
                return i, 'MOVE'
                
        return -1, None

    def mousePressEvent(self, event: QMouseEvent):
        if self._pixmap.isNull() or self._scaled_w == 0:
            return

        mx, my = event.pos().x(), event.pos().y()

        # 中クリック または Shift+左クリックでパン（画面移動）開始
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.ShiftModifier):
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self._pan_start_offset = (self._pan_x, self._pan_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.RightButton:
            idx, action = self._hit_test(mx, my)
            if idx != -1:
                self._bboxes.pop(idx)
                self.labels_changed.emit(self._bboxes)
                self.update()
                    
        elif event.button() == Qt.MouseButton.LeftButton:
            idx, action = self._hit_test(mx, my)
            if action:
                self._is_adjusting = True
                self._adjust_idx = idx
                self._adjust_action = action
                self._adjust_start_pos = (mx, my)
                self._orig_box = self._bboxes[idx]
            else:
                self._is_drawing = True
                self._start_pos = event.pos()
                self._current_pos = event.pos()
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and not event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            mx, my = event.pos().x(), event.pos().y()
            idx, action = self._hit_test(mx, my)
            if idx != -1:
                cid, xc, yc, w, h = self._bboxes[idx]
                self._bboxes[idx] = (self.current_class_id, xc, yc, w, h)
                self.labels_changed.emit(self._bboxes)
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        mx, my = event.pos().x(), event.pos().y()
        
        if self._is_panning:
            dx = mx - self._pan_start_pos.x()
            dy = my - self._pan_start_pos.y()
            self._pan_x = self._pan_start_offset[0] + dx
            self._pan_y = self._pan_start_offset[1] + dy
            self._update_layout_cache()
            self.update()
            return

        if self._is_drawing:
            self._current_pos = event.pos()
            self.update()
            
        elif self._is_adjusting:
            dx = (mx - self._adjust_start_pos[0]) / self._scaled_w
            dy = (my - self._adjust_start_pos[1]) / self._scaled_h
            
            cid, xc, yc, w, h = self._orig_box
            x1, y1 = xc - w/2, yc - h/2
            x2, y2 = xc + w/2, yc + h/2
            
            if self._adjust_action == 'MOVE':
                bw, bh = x2 - x1, y2 - y1
                new_x1, new_y1 = x1 + dx, y1 + dy
                new_x2, new_y2 = x2 + dx, y2 + dy
                if new_x1 < 0: new_x1 = 0; new_x2 = bw
                if new_y1 < 0: new_y1 = 0; new_y2 = bh
                if new_x2 > 1: new_x2 = 1; new_x1 = 1 - bw
                if new_y2 > 1: new_y2 = 1; new_y1 = 1 - bh
                x1, y1, x2, y2 = new_x1, new_y1, new_x2, new_y2
            elif self._adjust_action == 'TL':
                x1 += dx; y1 += dy
            elif self._adjust_action == 'TR':
                x2 += dx; y1 += dy
            elif self._adjust_action == 'BL':
                x1 += dx; y2 += dy
            elif self._adjust_action == 'BR':
                x2 += dx; y2 += dy
                
            if x1 > x2: x1, x2 = x2, x1
            if y1 > y2: y1, y2 = y2, y1
            
            x1 = max(0.0, min(1.0, x1))
            x2 = max(0.0, min(1.0, x2))
            y1 = max(0.0, min(1.0, y1))
            y2 = max(0.0, min(1.0, y2))
            
            n_xc, n_yc = (x1 + x2) / 2, (y1 + y2) / 2
            n_w, n_h = x2 - x1, y2 - y1
            
            self._bboxes[self._adjust_idx] = (cid, n_xc, n_yc, n_w, n_h)
            self.labels_changed.emit(self._bboxes)
            self.update()
            
        else:
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                return
                
            idx, action = self._hit_test(mx, my)
            if action in ('TL', 'BR'):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif action in ('TR', 'BL'):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif action == 'MOVE':
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_drawing:
                self._is_drawing = False
                self._current_pos = event.pos()
                rect = QRectF(self._start_pos, self._current_pos).normalized()
                
                ix_min = max(self._x_off, min(rect.left(), self._x_off + self._scaled_w))
                iy_min = max(self._y_off, min(rect.top(), self._y_off + self._scaled_h))
                ix_max = max(self._x_off, min(rect.right(), self._x_off + self._scaled_w))
                iy_max = max(self._y_off, min(rect.bottom(), self._y_off + self._scaled_h))
                
                px_w, px_h = ix_max - ix_min, iy_max - iy_min
                if px_w > 5 and px_h > 5:
                    n_xc = ((ix_min + ix_max) / 2 - self._x_off) / self._scaled_w
                    n_yc = ((iy_min + iy_max) / 2 - self._y_off) / self._scaled_h
                    n_w = px_w / self._scaled_w
                    n_h = px_h / self._scaled_h
                    self._bboxes.append((self.current_class_id, n_xc, n_yc, n_w, n_h))
                    self.labels_changed.emit(self._bboxes)
            
            elif self._is_adjusting:
                self._is_adjusting = False
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if self._pixmap.isNull():
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "画像がありません")
            painter.end()
            return

        # QPainterの描画範囲指定を使って高速かつ綺麗にスケーリング描画
        target_rect = QRectF(self._x_off, self._y_off, self._scaled_w, self._scaled_h)
        source_rect = QRectF(0, 0, self._pixmap.width(), self._pixmap.height())
        painter.drawPixmap(target_rect, self._pixmap, source_rect)

        # BBox 描画
        for cid, xc, yc, w, h in self._bboxes:
            color = _color_for_class(cid)
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            rx = self._x_off + (xc - w/2) * self._scaled_w
            ry = self._y_off + (yc - h/2) * self._scaled_h
            rw = w * self._scaled_w
            rh = h * self._scaled_h
            painter.drawRect(rx, ry, rw, rh)
            
            label = self._class_names[cid] if cid < len(self._class_names) else str(cid)
            painter.fillRect(rx, ry - 18, 100, 18, QBrush(color))
            painter.setPen(Qt.GlobalColor.black if color.lightness() > 180 else Qt.GlobalColor.white)
            painter.drawText(int(rx + 4), int(ry - 4), label)

        # 新規ドラッグ中の枠
        if self._is_drawing:
            color = _color_for_class(self.current_class_id)
            painter.setPen(QPen(color, 2, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 50)))
            
            rect = QRectF(self._start_pos, self._current_pos).normalized()
            ix_min = max(self._x_off, min(rect.left(), self._x_off + self._scaled_w))
            iy_min = max(self._y_off, min(rect.top(), self._y_off + self._scaled_h))
            ix_max = max(self._x_off, min(rect.right(), self._x_off + self._scaled_w))
            iy_max = max(self._y_off, min(rect.bottom(), self._y_off + self._scaled_h))
            
            painter.drawRect(ix_min, iy_min, ix_max - ix_min, iy_max - iy_min)

        painter.end()


class CurrentAdjusterWindow(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("BBox Adjuster - マウス操作 (ズーム・パン対応)")
        self.resize(1000, 700)
        
        self._build_ui()
        self.refresh_data()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        top_lay = QHBoxLayout()
        top_lay.addWidget(QLabel("🎨 新規・変更用タグ:"))
        self.combo_class = QComboBox()
        self.combo_class.addItems(self.api.get_class_names())
        self.combo_class.currentIndexChanged.connect(self._on_class_changed)
        top_lay.addWidget(self.combo_class)
        
        # 操作説明
        lbl_hint = QLabel(
            "💡 <b>Ctrl+スクロール</b>: ズーム / <b>Shift+ドラッグ</b> (または中クリック): 移動<br>"
            "<b>左ドラッグ</b>: 枠の移動・伸縮・新規 / <b>右クリック</b>: 削除 / <b>Wクリック</b>: タグ変更"
        )
        lbl_hint.setStyleSheet("color: #bbbbbb; font-size: 11px;")
        top_lay.addStretch()
        top_lay.addWidget(lbl_hint)
        layout.addLayout(top_lay)
        
        self.canvas = InteractiveCanvas(self)
        self.canvas.labels_changed.connect(self._on_labels_modified_on_canvas)
        layout.addWidget(self.canvas, stretch=1)
        
        self.btn_save = QPushButton("💾 本体に反映してファイル保存")
        self.btn_save.setMinimumHeight(40)
        self.btn_save.setStyleSheet("font-weight: bold; font-size: 14px; background-color: #2d5a2d;")
        self.btn_save.clicked.connect(self._save_file)
        layout.addWidget(self.btn_save)

    def _on_class_changed(self, idx):
        self.canvas.current_class_id = idx

    def refresh_data(self):
        img_path = self.api.get_current_image_path()
        if not img_path or not img_path.exists():
            self.canvas.set_data(QPixmap(), [], [])
            return
            
        pixmap = QPixmap(str(img_path))
        iw, ih = pixmap.width(), pixmap.height()
        class_names = self.api.get_class_names()
        
        raw_bboxes = self.api.get_current_labels()
        norm_bboxes = []
        if iw > 0 and ih > 0:
            for cid, px_xmin, px_ymin, px_w, px_h in raw_bboxes:
                n_w = px_w / iw
                n_h = px_h / ih
                n_xc = (px_xmin + px_w / 2) / iw
                n_yc = (px_ymin + px_h / 2) / ih
                norm_bboxes.append((cid, n_xc, n_yc, n_w, n_h))
        
        self.canvas.set_data(pixmap, norm_bboxes, class_names)
        
        if class_names and self.combo_class.count() > 0:
            self.canvas.current_class_id = self.combo_class.currentIndex()

    def _on_labels_modified_on_canvas(self, new_norm_bboxes):
        self.api.update_current_labels(new_norm_bboxes)
        
        img_path = self.api.get_current_image_path()
        if not img_path: return
        pix = QPixmap(str(img_path))
        iw, ih = pix.width(), pix.height()
        
        px_bboxes = []
        if iw > 0 and ih > 0:
            for cid, xc, yc, w, h in new_norm_bboxes:
                px_w = w * iw
                px_h = h * ih
                px_xmin = (xc - w/2) * iw
                px_ymin = (yc - h/2) * ih
                px_bboxes.append((cid, px_xmin, px_ymin, px_w, px_h))
                
        self.api._dialog.canvas._bboxes = px_bboxes
        self.api._dialog.canvas.update()

    def _save_file(self):
        self.api.save_current_labels()

class CurrentAdjusterEntry:
    def __init__(self, api):
        self.api = api
        self.window = None
        
    def setup_ui(self):
        self.btn = QPushButton("🛠️ 現在の画像をマウスで微調整")
        self.btn.clicked.connect(self._open_window)
        self.api.add_sidebar_widget(self.btn, "Mouse BBox Adjuster")
        
    def _open_window(self):
        if not self.window:
            self.window = CurrentAdjusterWindow(self.api, parent=self.api._dialog)
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        self.window.refresh_data()
        
    def on_image_changed(self, idx, img_path, txt_path):
        if self.window and self.window.isVisible():
            self.window.refresh_data()

def register_plugin(api):
    return CurrentAdjusterEntry(api)