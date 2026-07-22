"""UUID 単位の画像・ラベル確認・簡易編集ダイアログ。
Blender 風レイアウト（左:ビューア+リスト / 右:サイドバー編集）。
viewer-confirm-exporter.py [1] のテキスト編集機能を踏襲。
"""
import random
from pathlib import Path
from typing import List, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QTextEdit,
    QPushButton, QMessageBox, QWidget, QFormLayout,
    QGroupBox, QSizePolicy,
)
from PySide6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QBrush, QFont,
    QKeyEvent,
)
from PySide6.QtCore import Qt


# --- クラス色は従来通り ---
_CLASS_PALETTE = [
    QColor(255, 50, 50), QColor(50, 255, 50), QColor(50, 50, 255),
    QColor(255, 200, 50), QColor(255, 50, 255), QColor(50, 255, 255),
    QColor(255, 128, 0), QColor(128, 0, 255), QColor(0, 128, 128),
    QColor(128, 64, 0), QColor(0, 64, 128), QColor(192, 192, 192),
]

def _color_for_class(cid: int) -> QColor:
    if 0 <= cid < len(_CLASS_PALETTE):
        return _CLASS_PALETTE[cid]
    random.seed(cid)
    return QColor(random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))


class ImageCanvas(QWidget):
    """画像と YOLO BBox を重ね描画するカスタムキャンバス。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap = QPixmap()
        self._bboxes: List[Tuple[int, float, float, float, float]] = []
        self._class_names: List[str] = []

    def set_data(self, pixmap: QPixmap, bboxes: List[Tuple[int, float, float, float, float]], class_names: List[str]):
        self._pixmap = pixmap
        self._bboxes = bboxes
        self._class_names = class_names
        self.update()

    def clear(self):
        self._pixmap = QPixmap()
        self._bboxes = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(20, 20, 20))

        if self._pixmap.isNull():
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "画像なし")
            painter.end()
            return

        scaled = self._pixmap.scaled(
            self.rect().size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x_off = (self.width() - scaled.width()) // 2
        y_off = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x_off, y_off, scaled)

        sx = scaled.width() / self._pixmap.width()
        sy = scaled.height() / self._pixmap.height()
        pen_w = max(2, int(2 * ((sx + sy) / 2)))

        font = QFont()
        font.setPointSize(max(9, int(11 * ((sx + sy) / 2))))
        painter.setFont(font)

        for cid, bx, by, bw, bh in self._bboxes:
            rx = x_off + bx * sx
            ry = y_off + by * sy
            rw = bw * sx
            rh = bh * sy

            color = _color_for_class(cid)
            painter.setPen(QPen(color, pen_w))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rx, ry, rw, rh)

            label = self._class_names[cid] if cid < len(self._class_names) else str(cid)
            th = max(16, int(18 * ((sx) / 2)))
            lbl_rect = painter.boundingRect(0, 0, 300, 60, Qt.AlignmentFlag.AlignLeft, label)
            tw = lbl_rect.width() + 8
            painter.fillRect(rx, ry - th, tw, th, QBrush(color))
            c = Qt.GlobalColor.black if color.lightness() > 180 else Qt.GlobalColor.white
            painter.setPen(c)
            painter.drawText(int(rx + 4), int(ry - 3), label)

        painter.end()


class UUIDViewerDialog(QDialog):
    def __init__(
        self,
        uuid: str,
        image_dir: str,
        labels_dir: str,
        class_names: List[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.uuid = uuid
        self.image_dir = Path(image_dir)
        self.labels_dir = Path(labels_dir)
        self._class_names = list(class_names) if class_names else []

        self.setWindowTitle(f"Viewer — {uuid}")
        self.resize(1600, 950)

        self.pairs: List[Tuple[Path, Path]] = []
        self.current_idx: int = 0

        self._build_ui()
        self._load_pairs()

    # ------------------------------------------------------------------
    # UI 構築 : メイン水平スプリッター
    #  Left  : 垂直スプリッター [上:ImageCanvas(大)] [下:FileList(小)]
    #  Right : サイドバー [Info] [TextEdit] [Nav/Save]
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # === Root : 水平スプリッター ===
        root_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Pane : 垂直スプリッター ---
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # Canvas（大きく）
        self.canvas = ImageCanvas(self)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.setMinimumHeight(400)
        left_splitter.addWidget(self.canvas)

        # 下部ファイルリスト
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(220)
        self.list_widget.setMinimumHeight(100)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        list_layout.addWidget(QLabel("Files"))
        list_layout.addWidget(self.list_widget)
        left_splitter.addWidget(list_container)

        # Stretch factor : Canvas を優先
        left_splitter.setStretchFactor(0, 5)
        left_splitter.setStretchFactor(1, 1)
        left_splitter.setSizes([700, 200])

        root_splitter.addWidget(left_splitter)

        # --- Right Pane : サイドバー ---
        sidebar = QWidget()
        sidebar.setMinimumWidth(320)
        sidebar.setMaximumWidth(480)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setSpacing(8)

        # Info
        info_box = QGroupBox("Info")
        info_form = QFormLayout(info_box)
        self.lbl_uuid = QLabel(self.uuid)
        self.lbl_file_name = QLabel("-")
        self.lbl_counter = QLabel("- / -")
        self.lbl_img_size = QLabel("- x -")
        info_form.addRow("UUID:", self.lbl_uuid)
        info_form.addRow("File:", self.lbl_file_name)
        info_form.addRow("Count:", self.lbl_counter)
        info_form.addRow("Size:", self.lbl_img_size)
        sb_layout.addWidget(info_box)

        # Text Editor [1]
        edit_box = QGroupBox("Label Text (YOLO)")
        edit_layout = QVBoxLayout(edit_box)
        self.txt_edit = QTextEdit()
        self.txt_edit.setMinimumHeight(200)
        edit_layout.addWidget(self.txt_edit)

        btn_bar = QHBoxLayout()
        self.btn_save = QPushButton("💾 Save .txt")
        self.btn_save.clicked.connect(self._save_current_label)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_save)
        edit_layout.addLayout(btn_bar)
        sb_layout.addWidget(edit_box)

        # Nav + Close
        nav_box = QWidget()
        nav_layout = QHBoxLayout(nav_box)
        self.btn_prev = QPushButton("◀ Prev")
        self.btn_next = QPushButton("Next ▶")
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addStretch()
        nav_layout.addWidget(self.btn_next)
        sb_layout.addWidget(nav_box)

        sb_layout.addStretch()
        root_splitter.addWidget(sidebar)

        # Root stretch factor
        root_splitter.setStretchFactor(0, 4)
        root_splitter.setStretchFactor(1, 1)

        layout.addWidget(root_splitter)

    # ------------------------------------------------------------------
    def _load_pairs(self):
        if not self.image_dir.exists():
            QMessageBox.critical(self, "Error", f"image dir not found:\n{self.image_dir}")
            return

        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        imgs = sorted([p for p in self.image_dir.iterdir() if p.suffix.lower() in exts])

        self.pairs = []
        for img in imgs:
            txt = self.labels_dir / f"{img.stem}.txt"
            self.pairs.append((img, txt))

        for img, txt in self.pairs:
            item = QListWidgetItem(img.name)
            if not txt.exists():
                item.setForeground(Qt.GlobalColor.gray)
            self.list_widget.addItem(item)

        if self.pairs:
            self.list_widget.setCurrentRow(0)
            self._show_pair(0)
        else:
            self.lbl_counter.setText("0 / 0")

    def _on_row_changed(self, row: int):
        if 0 <= row < len(self.pairs):
            self.current_idx = row
            self._show_pair(row)

    def _parse_yolo_label(self, txt: Path, iw: int, ih: int) -> List[Tuple[int, float, float, float, float]]:
        out = []
        if not txt.exists():
            return out
        try:
            raw = txt.read_text(encoding="utf-8")
        except Exception:
            return out
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                cid = int(parts[0])
                xc, yc, w, h = map(float, parts[1:])
            except ValueError:
                continue
            out.append((
                cid,
                (xc - w / 2) * iw,
                (yc - h / 2) * ih,
                w * iw,
                h * ih,
            ))
        return out

    def _show_pair(self, idx: int):
        img, txt = self.pairs[idx]

        self.lbl_counter.setText(f"{idx + 1} / {len(self.pairs)}")
        self.lbl_file_name.setText(img.name)

        pix = QPixmap(str(img))
        if pix.isNull():
            self.canvas.clear()
            self.lbl_img_size.setText("? x ?")
            self.txt_edit.setPlainText("")
            return

        iw, ih = pix.width(), pix.height()
        self.lbl_img_size.setText(f"{iw} x {ih}")

        bboxes = self._parse_yolo_label(txt, iw, ih)
        self.canvas.set_data(pix, bboxes, self._class_names)

        if txt.exists():
            self.txt_edit.setPlainText(txt.read_text(encoding="utf-8"))
            self.txt_edit.setEnabled(True)
            self.btn_save.setEnabled(True)
        else:
            self.txt_edit.setPlainText("")
            self.txt_edit.setPlaceholderText("No label file")
            self.txt_edit.setEnabled(False)
            self.btn_save.setEnabled(False)

    def _save_current_label(self):
        if not self.pairs:
            return
        _, txt = self.pairs[self.current_idx]
        try:
            txt.write_text(self.txt_edit.toPlainText(), encoding="utf-8")
            QMessageBox.information(self, "Saved", f"{txt.name} saved.")
            item = self.list_widget.item(self.current_idx)
            if item:
                item.setForeground(Qt.GlobalColor.black)
            self._show_pair(self.current_idx)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _prev(self):
        if self.current_idx > 0:
            self.list_widget.setCurrentRow(self.current_idx - 1)

    def _next(self):
        if self.current_idx < len(self.pairs) - 1:
            self.list_widget.setCurrentRow(self.current_idx + 1)

    # ------------------------------------------------------------------
    # キーボード: テキストエディタにフォーカスがある時はページめくりを無視 [1]
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent):
        if self.txt_edit.hasFocus():
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_A:
            self._prev()
        elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_D:
            self._next()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pairs:
            self._show_pair(self.current_idx)