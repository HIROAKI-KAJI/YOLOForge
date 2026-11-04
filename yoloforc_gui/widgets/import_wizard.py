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
from ..core.workers import ImportWorker
from .progress_dialog import ProgressDialog

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
            
            # --- タグの不一致検証と自動入力の追加 ---
            meta = self.bridge.extract_metadata_from_source(path)
            if meta and "classes" in meta:
                extracted_classes = meta["classes"]
                
                # 今のデータセット定義 (self.edit_classes の初期値に渡されたもの) と比較
                current_classes_text = self.edit_classes.text().strip()
                current_classes = [c.strip() for c in current_classes_text.split(",") if c.strip()]
                
                if current_classes and extracted_classes != current_classes:
                    msg = (
                        f"タグの不一致を検出しました！\n\n"
                        f"現在のデータセット:\n{', '.join(current_classes)}\n\n"
                        f"インポート元:\n{', '.join(extracted_classes)}\n\n"
                        f"タイポや意図しない変更がないか確認してください。"
                    )
                    QMessageBox.warning(self, "タグの不一致ワーニング", msg)
                
                # 自動補完 (タイポ修正・上書き用としてセット)
                self.edit_classes.setText(", ".join(extracted_classes))
            
            self.btns.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        else:
            self.lbl_pattern.setText("ERROR")
            self.lbl_counts.setText("-")
            self.btns.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _execute(self):
        if not self.source_path:
            return

        raw = self.edit_classes.text().strip()
        classes = [c.strip() for c in raw.split(",") if c.strip()] if raw else None
        note = self.edit_note.toPlainText().strip()
        annotator = self.edit_annotator.text().strip()
        tags = [t.strip() for t in self.edit_tags.text().split(",") if t.strip()]

        # 1. プログレスダイアログの準備
        self.progress_dlg = ProgressDialog(self, title=f"インポート — {self.dataset_name}")
        
        # 2. ワーカーの準備
        self.worker = ImportWorker(
            bridge=self.bridge,
            dataset_name=self.dataset_name,
            source=self.source_path,
            classes=classes,
            note=note,
            annotator=annotator,
            tags=tags
        )
        
        # シグナルの接続
        self.worker.progressChanged.connect(self.progress_dlg.update_progress)
        self.worker.formatDetected.connect(self.progress_dlg.set_format)
        self.worker.finishedSuccessfully.connect(self._on_import_success)
        self.worker.errorOccurred.connect(self._on_import_error)

        # 3. 処理開始とダイアログのモーダル表示
        self.worker.start()
        self.progress_dlg.exec()

    def _on_import_success(self, result):
        self.progress_dlg.accept()
        QMessageBox.information(
            self,
            "インポート完了",
            f"UUID: {result.uuid}\n"
            f"Images: {result.image_count}\n"
            f"Labels: {result.label_count}\n\n"
            f"※アノテーション修正が必要な場合は別機能を利用してください。",
        )
        self.accept() # Wizardを閉じる

    def _on_import_error(self, err_msg):
        self.progress_dlg.reject()
        QMessageBox.critical(self, "エラー", f"インポート中にエラーが発生しました:\n{err_msg}")