"""UUID 単位の画像・ラベル確認・簡易編集ダイアログ。
viewer-confirm-exporter.py のテキストエディタ編集・保存機能を踏襲 [1]。
"""
import os
from pathlib import Path
from typing import List, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QTextEdit,
    QPushButton, QMessageBox, QWidget, QFormLayout,
)
from PySide6.QtGui import QPixmap, QKeyEvent
from PySide6.QtCore import Qt


class UUIDViewerDialog(QDialog):
    def __init__(self, uuid: str, image_dir: str, labels_dir: str, parent=None):
        super().__init__(parent)
        self.uuid = uuid
        self.image_dir = Path(image_dir)
        self.labels_dir = Path(labels_dir)

        self.setWindowTitle(f"確認ビューア — {uuid}")
        self.resize(1200, 700)

        self.pairs: List[Tuple[Path, Path]] = []   # (img, txt)
        self.current_idx: int = 0

        self._build_ui()
        self._load_pairs()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 上部情報
        info = QFormLayout()
        self.lbl_info = QLabel(f"UUID: {self.uuid}")
        self.lbl_count = QLabel("- / -")
        info.addRow(self.lbl_info, self.lbl_count)
        layout.addLayout(info)

        # メインスプリッタ
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左：ペア一覧
        self.list_widget = QListWidget()
        self.list_widget.setMaximumWidth(280)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        splitter.addWidget(self.list_widget)

        # 中央：画像プレビュー
        self.img_label = QLabel("画像を選択")
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setStyleSheet("background-color: #1a1a1a; color: #888;")
        splitter.addWidget(self.img_label)

        # 右：テキスト編集
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.txt_edit = QTextEdit()
        self.txt_edit.setPlaceholderText("ラベルファイルが存在しません")
        self.btn_save_txt = QPushButton("💾 保存")
        self.btn_save_txt.clicked.connect(self._save_current_label)
        right_layout.addWidget(QLabel("YOLO Label (.txt)"))
        right_layout.addWidget(self.txt_edit)
        right_layout.addWidget(self.btn_save_txt)
        splitter.addWidget(right)

        layout.addWidget(splitter)

        # 下部ナビ
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("◀ 前")
        self.btn_next = QPushButton("次 ▶")
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        nav.addWidget(self.btn_prev)
        nav.addStretch()
        nav.addWidget(self.btn_next)
        layout.addLayout(nav)

    def _load_pairs(self):
        """image/ と labels/ のペアをスキャン [1]"""
        if not self.image_dir.exists():
            QMessageBox.critical(self, "エラー", f"image dir not found:\n{self.image_dir}")
            return

        img_exts = [".png", ".jpg", ".jpeg", ".webp"]
        image_files = sorted(
            [p for p in self.image_dir.iterdir() if p.suffix.lower() in img_exts]
        )

        for img_path in image_files:
            base = img_path.stem
            txt_path = self.labels_dir / f"{base}.txt"
            self.pairs.append((img_path, txt_path))

        for img_path, txt_path in self.pairs:
            item = QListWidgetItem(f"{img_path.name}")
            if not txt_path.exists():
                item.setForeground(Qt.GlobalColor.gray)
            self.list_widget.addItem(item)

        if self.pairs:
            self.list_widget.setCurrentRow(0)
            self._show_pair(0)

        self.lbl_count.setText(f"{len(self.pairs)} ペア")

    def _on_row_changed(self, row: int):
        if 0 <= row < len(self.pairs):
            self.current_idx = row
            self._show_pair(row)

    def _show_pair(self, idx: int):
        img_path, txt_path = self.pairs[idx]
        self.lbl_count.setText(f"{idx + 1} / {len(self.pairs)}")

        # 画像表示
        pixmap = QPixmap(str(img_path))
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.img_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.img_label.setPixmap(scaled)
        else:
            self.img_label.setText("画像読み込み失敗")

        # テキスト読み込み [1]
        if txt_path.exists():
            try:
                raw = txt_path.read_text(encoding="utf-8")
                self.txt_edit.setPlainText(raw)
                self.txt_edit.setEnabled(True)
                self.btn_save_txt.setEnabled(True)
            except Exception as e:
                self.txt_edit.setPlainText(f"読み込みエラー:\n{e}")
                self.txt_edit.setEnabled(False)
                self.btn_save_txt.setEnabled(False)
        else:
            self.txt_edit.setPlainText("")
            self.txt_edit.setPlaceholderText("ラベルファイルが存在しません")
            self.txt_edit.setEnabled(False)
            self.btn_save_txt.setEnabled(False)

    def _save_current_label(self):
        """テキストエディタの内容を .txt へ上書き保存 [1]"""
        if not self.pairs:
            return
        img_path, txt_path = self.pairs[self.current_idx]
        try:
            txt_path.write_text(self.txt_edit.toPlainText(), encoding="utf-8")
            QMessageBox.information(self, "保存完了", f"{txt_path.name} を保存しました。")
            item = self.list_widget.item(self.current_idx)
            if item:
                item.setForeground(Qt.GlobalColor.black)
        except Exception as e:
            QMessageBox.critical(self, "保存失敗", str(e))

    def _prev(self):
        if self.current_idx > 0:
            self.list_widget.setCurrentRow(self.current_idx - 1)

    def _next(self):
        if self.current_idx < len(self.pairs) - 1:
            self.list_widget.setCurrentRow(self.current_idx + 1)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Left:
            self._prev()
        elif event.key() == Qt.Key.Key_Right:
            self._next()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent