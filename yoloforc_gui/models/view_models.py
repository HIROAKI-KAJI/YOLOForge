from typing import List, Dict, Any

from PySide6.QtGui import QStandardItemModel, QStandardItem


class UUIDTableModel(QStandardItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # TAGS の次に Action 列を追加
        self.setHorizontalHeaderLabels([
            "UUID", "Images", "Labels", "Status", "Annotator", "Tags", "Action"
        ])

    def refresh(self, records: List[Dict[str, Any]]):
        self.removeRows(0, self.rowCount())
        for rec in records:
            row = [
                QStandardItem(rec.get("uuid", "")),
                QStandardItem(str(rec.get("image_count", 0))),
                QStandardItem(str(rec.get("label_count", 0))),
                QStandardItem(str(rec.get("status", ""))),
                QStandardItem(str(rec.get("annotator") or "")),
                QStandardItem(
                    ", ".join(rec.get("batch_tags") or rec.get("tags") or [])
                ),
                QStandardItem(""),   # Action 列は空（Delegate でボタン描画）
            ]
            for it in row:
                it.setEditable(False)
            self.appendRow(row)