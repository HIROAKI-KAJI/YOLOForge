"""メインウィンドウ。左ナビ + 右コンテンツ(QStackedWidget)"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
    QListWidget, QLabel, QSplitter,
)

from ..core.bridge import YFCBridge
from .dataset_list_page import DatasetListPage
from .dataset_detail_page import DatasetDetailPage


class MainWindow(QMainWindow):
    def __init__(self, bridge: YFCBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle("YoloForC GUI")
        self.resize(1200, 800)

        # 中央ウィジェット
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        splitter = QSplitter()
        main_layout.addWidget(splitter)

        # 左ペイン：ナビ
        left = QWidget()
        left_layout = QHBoxLayout(left)
        self.nav_list = QListWidget()
        self.nav_list.itemClicked.connect(self._on_nav_clicked)
        left_layout.addWidget(self.nav_list)
        splitter.addWidget(left)

        # 右ペイン：コンテンツ
        self.stack = QStackedWidget()

        self.page_list = DatasetListPage(self.bridge)
        self.page_detail = DatasetDetailPage(self.bridge)

        self.stack.addWidget(self.page_list)   # index 0
        self.stack.addWidget(self.page_detail) # index 1

        splitter.addWidget(self.stack)
        splitter.setSizes([280, 920])

        # ナビ初期化
        self.refresh_nav()

        # 一覧ページからの戻り
        self.page_detail.btn_back.clicked.connect(self.show_list)
        
    def refresh_nav(self):
        self.nav_list.clear()
        names = self.bridge.list_datasets()
        self.nav_list.addItems(sorted(names))

    def _on_nav_clicked(self):
        item = self.nav_list.currentItem()
        if item:
            self.open_dataset_detail(item.text())

    def open_dataset_detail(self, name: str):
        self.page_detail.set_dataset(name)
        self.stack.setCurrentIndex(1)

    def show_list(self):
        self.refresh_nav()
        self.page_list.refresh()
        self.stack.setCurrentIndex(0)

    # シグナル接続
    def showEvent(self, event):
        # ウィンドウ表示時にナビ更新
        self.refresh_nav()
        super().showEvent(event)