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

        # Bridge インスタンスのみ作成（初期化は後続のWelcome Dashboardで行う）
        self.bridge = YFCBridge(self.activeWindow())

        # メインウィンドウ表示
        self.main_window = MainWindow(self.bridge)
        self.main_window.show()

        # メインウィンドウ表示
        self.main_window = MainWindow(self.bridge)
        self.main_window.show()