"""フォルダドロップ用ウィジェット"""
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, Signal


class DropZone(QWidget):
    folderDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)

        self.label = QLabel(
            "ここにフォルダをドロップ\n"
            "(YOLO: images/ + labels/ またはフラット配置)",
            self,
        )
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

        self.setStyleSheet("""
            DropZone {
                background-color: #2d2d2d;
                color: #cccccc;
                border: 2px dashed #666666;
                border-radius: 8px;
                font-size: 14px;
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.label.setText(f"選択: {path}")
                self.folderDropped.emit(path)
        event.acceptProposedAction()