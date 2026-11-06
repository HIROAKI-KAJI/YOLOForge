# yoloforc_gui/widgets/new_dataset_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QTextEdit, QDialogButtonBox, QMessageBox
)
from .drop_zone import DropZone

class NewDatasetDialog(QDialog):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle("新規データセットの作成")
        self.setMinimumWidth(500)
        
        self.source_path = None  # ← ドロップされたパスを保持する変数を追加

        layout = QVBoxLayout(self)
        
        # ドラッグ＆ドロップで自動入力
        self.drop = DropZone(self)
        self.drop.label.setText("既存データセットをドロップして設定を自動入力 (推奨)")
        self.drop.folderDropped.connect(self._on_folder_dropped)
        layout.addWidget(self.drop)
        
        form = QFormLayout()
        self.edit_name = QLineEdit()
        self.edit_classes = QLineEdit()
        self.edit_classes.setPlaceholderText("cb, b1, b2... (カンマ区切り)")
        self.edit_notes = QTextEdit()
        self.edit_notes.setMaximumHeight(80)
        
        form.addRow("Dataset Name*:", self.edit_name)
        form.addRow("Classes (Tags)*:", self.edit_classes)
        form.addRow("Notes:", self.edit_notes)
        layout.addLayout(form)
        
        self.btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.btns.accepted.connect(self.accept)
        self.btns.rejected.connect(self.reject)
        layout.addWidget(self.btns)

    def _on_folder_dropped(self, path: str):
        self.source_path = path
        
        meta = self.bridge.extract_metadata_from_source(path)
        if not meta:
            QMessageBox.warning(
                self, 
                "パース失敗", 
                "対応しているデータセット形式（KYOLO / LabelMe等）が見つからないか、クラス情報を読み込めません。"
            )
            return
            
        # 検知したフォーマットを取得
        fmt = meta.get("format", "Unknown")
            
        if meta.get("dataset_name"):
            safe_name = "".join(c for c in meta["dataset_name"] if c.isalnum() or c in "_-")
            self.edit_name.setText(safe_name)
        if meta.get("classes"):
            self.edit_classes.setText(", ".join(meta["classes"]))
        if meta.get("notes"):
            self.edit_notes.setPlainText(meta["notes"])
        
        QMessageBox.information(
            self, 
            "自動入力", 
            f"【{fmt}】形式のデータセットを検出し、タグ情報を自動入力しました。"
        )



    def get_values(self):
        return {
            "name": self.edit_name.text().strip(),
            "classes": [c.strip() for c in self.edit_classes.text().split(",") if c.strip()],
            "notes": self.edit_notes.toPlainText().strip(),
            "source_path": self.source_path  # データセット本体のコピーのため、パスも一緒に親へ返す
        }

    