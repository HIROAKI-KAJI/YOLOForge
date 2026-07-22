"""QApplication と メインウィンドウの初期化"""
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .core.bridge import YFCBridge
from .widgets.main_window import MainWindow


class YoloForCApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("YoloForC GUI")
        self.setApplicationVersion("0.1.0")

        # Bridge 初期化（未設定ならダイアログで誘導）
        self.bridge = YFCBridge(self.activeWindow())
        if not self.bridge.ready:
            QMessageBox.critical(
                None, "初期化エラー",
                "YoloForC ルートが初期化されていないか、設定されていません。\n"
                "アプリケーションを終了します。"
            )
            sys.exit(1)

        # メインウィンドウ表示
        self.main_window = MainWindow(self.bridge)
        self.main_window.show()