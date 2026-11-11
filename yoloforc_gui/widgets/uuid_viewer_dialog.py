"""UUID 単位の画像・ラベル確認・簡易編集ダイアログ。
Blender 風レイアウト（左:ビューア+リスト / 右:サイドバー編集）。
viewer-confirm-reporter.py [1] のテキスト編集機能を踏襲。
プラグインAPI（ViewerAPI）をサポート。
"""
import random
import importlib
import pkgutil
import sys
from pathlib import Path
from typing import List, Tuple, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QTextEdit,
    QPushButton, QMessageBox, QWidget, QFormLayout,
    QGroupBox, QSizePolicy, QMenuBar, QMenu
)
from PySide6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QBrush, QFont,
    QKeyEvent, QAction
)
from PySide6.QtCore import Qt, Signal


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
        self._visible_classes: Optional[List[int]] = None  # プラグイン用フィルタ

    def set_data(self, pixmap: QPixmap, bboxes: List[Tuple[int, float, float, float, float]], class_names: List[str]):
        self._pixmap = pixmap
        self._bboxes = bboxes
        self._class_names = class_names
        self.update()

    def clear(self):
        self._pixmap = QPixmap()
        self._bboxes = []
        self.update()

    def set_visible_classes(self, class_ids: Optional[List[int]]):
        """特定のクラスのみを描画するフィルタを設定する（Noneで全表示）"""
        self._visible_classes = class_ids
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
            # フィルタリング適用
            if self._visible_classes is not None and cid not in self._visible_classes:
                continue

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


class ViewerAPI:
    """プラグインに渡される、本体操作用のインターフェース"""
    def __init__(self, dialog: 'UUIDViewerDialog'):
        self._dialog = dialog
        
        # シグナルの公開
        self.index_changed = dialog.index_changed
        self.labels_modified = dialog.labels_modified
        self.labels_saved = dialog.labels_saved

    # --- 1. 状態取得 API ---
    def get_current_index(self) -> int:
        return self._dialog.current_idx

    def get_total_count(self) -> int:
        return len(self._dialog.pairs)

    def get_class_names(self) -> List[str]:
        return self._dialog._class_names.copy()

    def get_current_image_path(self) -> Optional[Path]:
        if not self._dialog.pairs: return None
        return self._dialog.pairs[self._dialog.current_idx][0]

    def get_current_label_path(self) -> Optional[Path]:
        if not self._dialog.pairs: return None
        return self._dialog.pairs[self._dialog.current_idx][1]

    def get_current_labels(self) -> List[Tuple[int, float, float, float, float]]:
        return self._dialog.canvas._bboxes.copy()

    def get_data_at(self, index: int) -> Tuple[Optional[Path], Optional[Path]]:
        if 0 <= index < len(self._dialog.pairs):
            return self._dialog.pairs[index]
        return (None, None)

    def get_uuid(self) -> str:
        return self._dialog.uuid

    # --- 2. 操作・更新 API ---
    def navigate_to(self, index: int):
        if 0 <= index < len(self._dialog.pairs):
            self._dialog.list_widget.setCurrentRow(index)

    def navigate_next(self):
        self._dialog._next()

    def navigate_prev(self):
        self._dialog._prev()

    def update_current_labels(self, new_labels: List[Tuple[int, float, float, float, float]]):
        # Yoloフォーマット文字列に変換してテキストエディタにセット
        lines = []
        for cid, xc, yc, w, h in new_labels:
            lines.append(f"{cid} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
        text = "\n".join(lines)
        self._dialog.txt_edit.setPlainText(text)
        # キャンバスも更新
        self._dialog.canvas._bboxes = new_labels
        self._dialog.canvas.update()

    def save_current_labels(self):
        self._dialog._save_current_label()

    # --- 4. 描画・UI介入 API ---
    def set_canvas_filter(self, class_ids: Optional[List[int]]):
        self._dialog.canvas.set_visible_classes(class_ids)

    def add_sidebar_widget(self, widget: QWidget, title: str = ""):
        # グループボックスで包んで追加
        group_box = QGroupBox(title)
        layout = QVBoxLayout(group_box)
        layout.addWidget(widget)
        self._dialog.plugin_layout.addWidget(group_box)

    def add_menu_action(self, menu_name: str, action: QAction):
        # 既存のメニューを探すか新規作成
        target_menu = None
        for action_obj in self._dialog.menu_bar.actions():
            if action_obj.menu() and action_obj.menu().title() == menu_name:
                target_menu = action_obj.menu()
                break
        
        if not target_menu:
            target_menu = self._dialog.menu_bar.addMenu(menu_name)
        
        target_menu.addAction(action)


class UUIDViewerDialog(QDialog):
    # プラグイン向けシグナル
    index_changed = Signal(int, Path, Path)
    labels_modified = Signal(str)
    labels_saved = Signal(Path)

    def __init__(
        self,
        uuid: str,
        image_dir: str,
        labels_dir: str,
        class_names: List[str] = None,
        enabled_plugins: List[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.uuid = uuid
        self.image_dir = Path(image_dir)
        self.labels_dir = Path(labels_dir)
        self._class_names = list(class_names) if class_names else []
        self._enabled_plugins = enabled_plugins or []

        self.setWindowTitle(f"Viewer — {uuid}")
        self.resize(1600, 950)

        self.pairs: List[Tuple[Path, Path]] = []
        self.current_idx: int = 0
        self.loaded_plugins = []

        self._build_ui()
        self._load_pairs()

        # プラグインAPIの初期化と読み込み
        self.api = ViewerAPI(self)
        self._load_plugins()

    def _build_ui(self):
        # メインレイアウト
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 拡張ポイント1: メニューバー
        self.menu_bar = QMenuBar(self)
        main_layout.setMenuBar(self.menu_bar)

        # === Root : 水平スプリッター ===
        root_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Pane : 垂直スプリッター ---
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # Canvas
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

        # Text Editor
        edit_box = QGroupBox("Label Text (YOLO)")
        edit_layout = QVBoxLayout(edit_box)
        self.txt_edit = QTextEdit()
        self.txt_edit.setMinimumHeight(200)
        self.txt_edit.textChanged.connect(self._on_text_modified) # シグナル発火用
        edit_layout.addWidget(self.txt_edit)

        btn_bar = QHBoxLayout()
        self.btn_save = QPushButton("💾 Save .txt")
        self.btn_save.clicked.connect(self._save_current_label)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_save)
        edit_layout.addLayout(btn_bar)
        sb_layout.addWidget(edit_box)

        # Nav
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

        # 拡張ポイント2: プラグイン専用レイアウト
        self.plugin_layout = QVBoxLayout()
        sb_layout.addLayout(self.plugin_layout)

        sb_layout.addStretch()
        root_splitter.addWidget(sidebar)

        root_splitter.setStretchFactor(0, 4)
        root_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(root_splitter)

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

    def _load_plugins(self):
        # config.py からグローバルインスタンスをインポート
        from ..core.config import plugin_manager
        import importlib
        import pkgutil
        
        # マネージャーに有効なプラグインを聞く
        enabled_plugins = plugin_manager.get_enabled_plugins()
        
        # plugins.__path__ ではなく、plugin_manager が解決したディレクトリパスを使う
        for _, module_name, _ in pkgutil.iter_modules([str(plugin_manager.plugins_dir)]):
            if module_name in enabled_plugins:
                module = importlib.import_module(f"plugins.{module_name}")
                if hasattr(module, "register_plugin"):
                    plugin_instance = module.register_plugin(self.api)
                    self.loaded_plugins.append(plugin_instance)
                    
                    if hasattr(plugin_instance, "on_image_changed"):
                        self.index_changed.connect(plugin_instance.on_image_changed)
                        
                    if hasattr(plugin_instance, "on_labels_modified"):
                        self.labels_modified.connect(plugin_instance.on_labels_modified)
                        
                    if hasattr(plugin_instance, "on_labels_saved"):
                        self.labels_saved.connect(plugin_instance.on_labels_saved)
                    
                    if hasattr(plugin_instance, "setup_ui"):
                        plugin_instance.setup_ui()

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
            self.txt_edit.blockSignals(True)
            self.txt_edit.setPlainText("")
            self.txt_edit.blockSignals(False)
            return

        iw, ih = pix.width(), pix.height()
        self.lbl_img_size.setText(f"{iw} x {ih}")

        bboxes = self._parse_yolo_label(txt, iw, ih)
        self.canvas.set_data(pix, bboxes, self._class_names)

        self.txt_edit.blockSignals(True) # 無駄なシグナル発火を防ぐ
        if txt.exists():
            self.txt_edit.setPlainText(txt.read_text(encoding="utf-8"))
            self.txt_edit.setEnabled(True)
            self.btn_save.setEnabled(True)
        else:
            self.txt_edit.setPlainText("")
            self.txt_edit.setPlaceholderText("No label file")
            self.txt_edit.setEnabled(False)
            self.btn_save.setEnabled(False)
        self.txt_edit.blockSignals(False)

        # イベント通知
        self.index_changed.emit(idx, img, txt)

    def _on_text_modified(self):
        self.labels_modified.emit(self.txt_edit.toPlainText())

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
            
            # イベント通知
            self.labels_saved.emit(txt)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _prev(self):
        if self.current_idx > 0:
            self.list_widget.setCurrentRow(self.current_idx - 1)

    def _next(self):
        if self.current_idx < len(self.pairs) - 1:
            self.list_widget.setCurrentRow(self.current_idx + 1)

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