"""インポート専用ウィザード。
タグ付けの修正・アノテーション編集は別機能セットとして扱う。
"""
from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QLabel, QMessageBox, QTextEdit,
)

from ..core.bridge import YFCBridge
from .drop_zone import DropZone


class ImportWizard(QDialog):
    def __init__(
        self,
        bridge: YFCBridge,
        dataset_name: str,
        default_classes: List[str],
        parent=None,
    ):
        super().__init__(parent)
        self.bridge = bridge
        self.dataset_name = dataset_name
        self.source_path: Optional[str] = None

        self.setWindowTitle(f"インポート — {dataset_name}")
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)

        # --- ドロップゾーン ---
        self.drop = DropZone(self)
        self.drop.folderDropped.connect(self._on_drop)
        layout.addWidget(self.drop)

        # --- プレビュー ---
        info = QFormLayout()
        self.lbl_source = QLabel("未選択")
        self.lbl_pattern = QLabel("-")
        self.lbl_counts = QLabel("-")
        info.addRow("Source:", self.lbl_source)
        info.addRow("Pattern:", self.lbl_pattern)
        info.addRow("Counts:", self.lbl_counts)
        layout.addLayout(info)

        # --- メタ入力 ---
        form = QFormLayout()

        self.edit_classes = QLineEdit(
            ", ".join(default_classes) if default_classes else ""
        )
        self.edit_note = QTextEdit()
        self.edit_note.setMaximumHeight(80)
        self.edit_note.setPlaceholderText("このバッチのメモ（任意）")
        self.edit_annotator = QLineEdit()
        self.edit_tags = QLineEdit()
        self.edit_tags.setPlaceholderText("batch_01, night （カンマ区切り）")

        form.addRow("Classes*:", self.edit_classes)
        form.addRow("Note:", self.edit_note)
        form.addRow("Annotator:", self.edit_annotator)
        form.addRow("Batch Tags:", self.edit_tags)
        layout.addLayout(form)

        self._note_label = QLabel(
            "<i>タグ付け修正・アノテーション編集は別機能として提供します。</i>"
        )
        self._note_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self._note_label)

        # --- ボタン ---
        self.btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.btns.button(QDialogButtonBox.StandardButton.Ok).setText("インポート実行")
        self.btns.accepted.connect(self._execute)
        self.btns.rejected.connect(self.reject)
        self.btns.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.btns)

    def _on_drop(self, path: str):
        self.source_path = path
        self.lbl_source.setText(path)

        preview = self.bridge.analyze_source_structure(path)
        if preview:
            self.lbl_pattern.setText(preview["pattern"])
            self.lbl_counts.setText(
                f"Images: {preview['image_count']}, "
                f"Labels: {preview['label_count']}"
            )
            self.btns.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        else:
            self.lbl_pattern.setText("ERROR")
            self.lbl_counts.setText("-")
            self.btns.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _execute(self):
        if not self.source_path:
            return

        raw = self.edit_classes.text().strip()
        classes: Optional[List[str]] = None
        if raw:
            classes = [c.strip() for c in raw.split(",") if c.strip()]

        note = self.edit_note.toPlainText().strip()
        annotator = self.edit_annotator.text().strip()
        tags = [t.strip() for t in self.edit_tags.text().split(",") if t.strip()]

        result = self.bridge.import_folder(
            dataset_name=self.dataset_name,
            source=self.source_path,
            classes=classes,
            note=note,
            annotator=annotator,
            tags=tags,
        )
        if result is not None:
            QMessageBox.information(
                self,
                "インポート完了",
                f"UUID: {result.uuid}\n"
                f"Images: {result.image_count}\n"
                f"Labels: {result.label_count}\n\n"
                f"※アノテーション修正が必要な場合は別機能を利用してください。",
            )
            self.accept()