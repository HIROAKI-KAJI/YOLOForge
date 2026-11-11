"""メインウィンドウ。左ナビ + 右コンテンツ(QStackedWidget)"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QListWidget, QLabel, QSplitter, QMessageBox, QPushButton
)

from ..core.bridge import YFCBridge
from .dataset_list_page import DatasetListPage
from .dataset_detail_page import DatasetDetailPage
from .welcome_dashboard import WelcomeDashboard

class MainWindow(QMainWindow):
    def __init__(self, bridge: YFCBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle("YOLO FORGE")
        self.resize(1200, 800)

        # 中央ウィジェットと全体レイアウト
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0) # 画面全体を使う

        # 最上位の StackedWidget (0: Welcome, 1: Main Workspace)
        self.root_stack = QStackedWidget()
        main_layout.addWidget(self.root_stack)

        # --- 0: Welcome Dashboard ---
        self.welcome_page = WelcomeDashboard()
        self.welcome_page.workspaceSelected.connect(self._initialize_workspace)
        self.root_stack.addWidget(self.welcome_page)

        # --- 1: Main Workspace (既存の Splitter 構成) ---
        self.workspace_widget = QWidget()
        workspace_layout = QHBoxLayout(self.workspace_widget)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter()
        workspace_layout.addWidget(splitter)

        # 左ペイン：ナビ
        left = QWidget()
        left_layout = QVBoxLayout(left)
        
        # ワークスペース切り替えボタンを追加
        self.btn_switch_workspace = QPushButton("🏠 ワークスペース切替")
        self.btn_switch_workspace.clicked.connect(self._show_welcome)
        left_layout.addWidget(self.btn_switch_workspace)

        self.nav_list = QListWidget()
        self.nav_list.itemClicked.connect(self._on_nav_clicked)
        left_layout.addWidget(self.nav_list)
        splitter.addWidget(left)

        # 右ペイン：コンテンツ (既存の Dataset リスト/詳細)
        self.content_stack = QStackedWidget()
        self.page_list = DatasetListPage(self.bridge)
        self.page_detail = DatasetDetailPage(self.bridge)
        
        self.content_stack.addWidget(self.page_list)   # index 0
        self.content_stack.addWidget(self.page_detail) # index 1

        splitter.addWidget(self.content_stack)
        splitter.setSizes([280, 920])

        self.root_stack.addWidget(self.workspace_widget)

        # 初期表示は Welcome
        self.root_stack.setCurrentWidget(self.welcome_page)

        # 一覧ページからの戻り
        self.page_detail.btn_back.clicked.connect(self.show_list)

    def _initialize_workspace(self, root_path: str):
        """ワークスペースパスを受け取り、バックエンドを初期化してメイン画面へ遷移"""
        try:
            # bridge 経由で YoloForC を初期化する処理
            # （bridge.py に initialize_root(path) メソッドを追加した）
            self.bridge.initialize_root(root_path) 
            self.setWindowTitle(f"YOLO FORGE - {root_path}")
            
            # データセット一覧を更新してメイン画面へ
            self.refresh_nav()
            self.page_list.refresh()
            self.content_stack.setCurrentWidget(self.page_list)
            self.root_stack.setCurrentWidget(self.workspace_widget)
            
        except Exception as e:
            QMessageBox.critical(self, "初期化エラー", f"ワークスペースの初期化に失敗しました:\n{e}")

    def _show_welcome(self):
        """ダッシュボードへ戻る"""
        self.setWindowTitle("YOLO FORGE")
        self.root_stack.setCurrentWidget(self.welcome_page)

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
        self.content_stack.setCurrentWidget(self.page_detail)

    def show_list(self):
        self.refresh_nav()
        self.page_list.refresh()
        self.content_stack.setCurrentWidget(self.page_list)