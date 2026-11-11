"""メインウィンドウ。左ナビ + 右コンテンツ(QStackedWidget)"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QListWidget, QLabel, QSplitter, QMessageBox, QPushButton
)
from PySide6.QtGui import (
    QAction
)

from ..core.bridge import YFCBridge

from .plugin_settings_dialog import PluginSettingsDialog

from .dataset_list_page import DatasetListPage
from .dataset_detail_page import DatasetDetailPage
from .welcome_dashboard import WelcomeDashboard

# ワークスペース全体レポート用
from pathlib import Path
from PySide6.QtWidgets import QPushButton, QMessageBox
from .dataset_report_dialog import DatasetReportDialog
from ..core.reporter import DatasetReporter

class MainWindow(QMainWindow):
    def __init__(self, bridge: YFCBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle("YOLO FORGE")
        self.resize(1200, 800)

        # MENU
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("設定(&S)")
        
        plugin_action = QAction("プラグイン管理(&P)", self)
        plugin_action.triggered.connect(self._open_plugin_settings)
        settings_menu.addAction(plugin_action)

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
        self.btn_switch_workspace = QPushButton("ワークスペース切替")
        self.btn_switch_workspace.clicked.connect(self._show_welcome)
        left_layout.addWidget(self.btn_switch_workspace)

        # ワークスペース単位の操作用ボタングループ
        self.btn_workspace_report = QPushButton("ワークスペース全体レポート")
        self.btn_workspace_report.setStyleSheet("font-weight: bold; background-color: #2d5a2d; padding: 5px; margin-top: 6px;")
        self.btn_workspace_report.clicked.connect(self._open_workspace_report)
        left_layout.addWidget(self.btn_workspace_report)

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


    def _open_plugin_settings(self):
        dlg = PluginSettingsDialog(self)
        dlg.exec()

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


    def _open_workspace_report(self):
        """ワークスペース全体の全バッチを横断した品質レポートを表示する"""
        if not self.bridge.ready or not self.bridge._root_path:
            QMessageBox.warning(self, "エラー", "ワークスペースが読み込まれていません。")
            return

        dataset_names = self.bridge.list_datasets()
        if not dataset_names:
            QMessageBox.information(self, "情報", "ワークスペースにデータセットが存在しません。")
            return
            
        all_images = []
        all_labels = []
        workspace_classes = []
        
        for dname in dataset_names:
            # ワークスペース内でタグが統一されている前提なので、最初のクラス定義を流用
            if not workspace_classes:
                meta = self.bridge.get_dataset_meta(dname)
                if meta and "classes" in meta:
                    workspace_classes = meta["classes"]
            
            # 各データセット内の全UUIDファイルを集約
            records = self.bridge.list_uuids(dname)
            for rec in records:
                uuid = rec.get("uuid")
                if not uuid:
                    continue
                
                detail = self.bridge.get_uuid_detail(dname, uuid)
                if detail and "files" in detail:
                    all_images.extend([Path(p) for p in detail["files"].get("images", [])])
                    all_labels.extend([Path(p) for p in detail["files"].get("labels", [])])
                    
        if not all_images:
            QMessageBox.information(self, "情報", "ワークスペース内に画像が存在しません。")
            return
            
        # 汎用レポーターに全パスを渡してダイアログを起動
        reporter = DatasetReporter("Workspace All Datasets", all_images, all_labels, workspace_classes)
        dlg = DatasetReportDialog(reporter, self)
        dlg.exec()