# yoloforc_gui/widgets/progress_dialog.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PySide6.QtCore import Qt

class ProgressDialog(QDialog):
    def __init__(self, parent=None, title="インポート処理中"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 150)
        self.setWindowModality(Qt.WindowModality.ApplicationModal) # 他の操作をブロック

        layout = QVBoxLayout(self)

        self.lbl_format = QLabel("フォーマットを判定中...")
        self.lbl_format.setStyleSheet("font-weight: bold; color: #4CAF50;")
        layout.addWidget(self.lbl_format)

        self.lbl_status = QLabel("準備中...")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

    def update_progress(self, current: int, total: int, msg: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.lbl_status.setText(f"{current} / {total} : {msg}")

    def set_format(self, fmt: str):
        self.lbl_format.setText(f"検出フォーマット: {fmt}")