"""dataset.yaml の内容（classes, notes, 基本情報）を編集するダイアログ。
classes の順序変更・削除は既存アノテーションと整合性が崩れるため、警告付きで実行する。
"""
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QListWidget, QPushButton, QLabel,
    QDialogButtonBox, QMessageBox, QTextEdit, QInputDialog,
)


class DatasetMetaEditDialog(QDialog):
    def __init__(self, meta: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.meta = meta
        self.result_classes: List[str] = []

        self.setWindowTitle(f"データセット設定の編集 — {meta.get('dataset_name', '')}")
        self.resize(520, 480)

        layout = QVBoxLayout(self)

        # --- 基本情報 ---
        form = QFormLayout()
        self.edit_name = QLineEdit(str(meta.get("dataset_name") or ""))
        self.edit_name.setReadOnly(True)  # 改名は安全のため禁止

        self.edit_date = QLineEdit(str(meta.get("date_captured") or ""))
        self.edit_location = QLineEdit(str(meta.get("location") or ""))
        self.edit_notes = QTextEdit(str(meta.get("notes") or ""))
        self.edit_notes.setMaximumHeight(80)

        form.addRow("Dataset Name:", self.edit_name)
        form.addRow("Date Captured:", self.edit_date)
        form.addRow("Location:", self.edit_location)
        form.addRow("Notes:", self.edit_notes)
        layout.addLayout(form)

        # --- Classes 編集 ---
        layout.addWidget(QLabel("Classes (順序変更・削除は既存ラベルに影響):"))
        self.list_classes = QListWidget()
        for c in meta.get("classes", []):
            self.list_classes.addItem(c)
        layout.addWidget(self.list_classes)

        cls_bar = QHBoxLayout()
        self.btn_add = QPushButton("+ 末尾に追加")
        self.btn_edit = QPushButton("✎ 名前変更")
        self.btn_remove = QPushButton("− 削除")
        cls_bar.addWidget(self.btn_add)
        cls_bar.addWidget(self.btn_edit)
        cls_bar.addWidget(self.btn_remove)
        layout.addLayout(cls_bar)

        self.btn_add.clicked.connect(self._add_class)
        self.btn_edit.clicked.connect(self._edit_name)
        self.btn_remove.clicked.connect(self._remove_class)

        # --- 警告文 ---
        warn = QLabel(
            "<span style='color:#ff6644;'>⚠ 警告:</span> "
            "<b>クラスを途中で削除したり順序を入れ替えると</b>、"
            "既存バッチの class_id と意味がずれ、学習データが破損します。<br>"
            "<b>名前変更</b>と<b>末尾への追加</b>のみ安全です。"
        )
        warn.setWordWrap(True)
        warn.setStyleSheet("font-size: 12px; background: #331800; padding: 6px; border-radius: 4px;")
        layout.addWidget(warn)

        # --- ボタン ---
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _add_class(self):
        name, ok = QInputDialog.getText(
            self, "クラス追加", "新しいクラス名（末尾に追加）:"
        )
        if ok and name.strip():
            self.list_classes.addItem(name.strip())

    def _edit_name(self):
        row = self.list_classes.currentRow()
        if row < 0:
            QMessageBox.warning(self, "選択", "変更するクラスを選択してください。")
            return
        old = self.list_classes.item(row).text()
        name, ok = QInputDialog.getText(
            self, "名前変更", "新しい名前:", text=old
        )
        if ok and name.strip():
            self.list_classes.item(row).setText(name.strip())

    def _remove_class(self):
        row = self.list_classes.currentRow()
        if row < 0:
            return
        item = self.list_classes.item(row)
        name = item.text()
        r = QMessageBox.question(
            self,
            "削除確認",
            f"クラス '{name}'（index={row}）を削除しますか？\n\n"
            f"この index に該当する既存アノテーションは、"
            f"学習時に別クラスと解釈される可能性があります。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r == QMessageBox.StandardButton.Yes:
            self.list_classes.takeItem(row)

    def _on_save(self):
        self.result_classes = [
            self.list_classes.item(i).text()
            for i in range(self.list_classes.count())
        ]

        old_classes = list(self.meta.get("classes") or [])
        if old_classes != self.result_classes:
            removed = [c for c in old_classes if c not in self.result_classes]
            reordered = (
                old_classes != self.result_classes
                and not removed
                and len(old_classes) == len(self.result_classes)
            )
            if removed or reordered:
                r = QMessageBox.warning(
                    self,
                    "整合性警告",
                    "クラス定義に削除または順序変更が含まれます。\n"
                    "既存の YOLO .txt ファイル（class_id は 0,1,2... のまま）と\n"
                    "意味がずれる可能性があります。保存しますか？",
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                )
                if r != QMessageBox.StandardButton.Save:
                    return
        self.accept()

    def get_values(self) -> Dict[str, Any]:
        return {
            "date_captured": self.edit_date.text() or None,
            "location": self.edit_location.text() or None,
            "notes": self.edit_notes.toPlainText() or None,
            "classes": self.result_classes,
        }