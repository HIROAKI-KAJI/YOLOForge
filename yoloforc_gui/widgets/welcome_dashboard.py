from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QFileDialog, QMessageBox, QGroupBox
)
from PySide6.QtCore import Signal, QSettings

class WelcomeDashboard(QWidget):
    # ワークスペースが決定した際に MainWindow へ通知するシグナル
    workspaceSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("YOLOForge", "WorkspaceManager")
        self._setup_ui()
        self._load_recent_workspaces()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # タイトルと簡単な説明
        title = QLabel("<h1>YOLO FORGE</h1>")
        desc = QLabel(
            "YOLOデータセットの一元管理ツールです。<br>"
            "既存のワークスペース（保存先フォルダ）を開くか、新しく作成してください。"
        )
        layout.addWidget(title)
        layout.addWidget(desc)

        # アクションボタン
        btn_layout = QHBoxLayout()
        self.btn_open = QPushButton("📂 ワークスペースを開く / 作成する")
        self.btn_open.setMinimumHeight(50)
        self.btn_open.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.btn_open.clicked.connect(self._on_open_workspace)
        btn_layout.addWidget(self.btn_open)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 最近開いたワークスペース（履歴）
        history_group = QGroupBox("最近開いたワークスペース")
        history_layout = QVBoxLayout(history_group)
        self.list_recent = QListWidget()
        self.list_recent.itemDoubleClicked.connect(self._on_recent_selected)
        history_layout.addWidget(self.list_recent)
        layout.addWidget(history_group)

    def _load_recent_workspaces(self):
        self.list_recent.clear()
        # QSettings から履歴リストを取得（デフォルトは空リスト）
        recents = self.settings.value("recent_workspaces", [])
        if isinstance(recents, str):
            recents = [recents] # 万が一単一文字列だった場合のフォールバック
        for path in recents:
            if Path(path).exists(): # 存在するパスのみ表示
                self.list_recent.addItem(path)

    def _add_to_recent(self, path: str):
        recents = self.settings.value("recent_workspaces", [])
        if isinstance(recents, str):
            recents = [recents]
        
        if path in recents:
            recents.remove(path)
        recents.insert(0, path) # 先頭に追加
        
        # 履歴は最大10件まで保持
        recents = recents[:10]
        self.settings.setValue("recent_workspaces", recents)
        self._load_recent_workspaces()

    def _on_open_workspace(self):
        # フォルダ選択ダイアログを表示
        path = QFileDialog.getExistingDirectory(self, "ワークスペースフォルダを選択")
        if path:
            self._add_to_recent(path)
            self.workspaceSelected.emit(path)

    def _on_recent_selected(self, item):
        path = item.text()
        if Path(path).exists():
            self._add_to_recent(path) # 選択したものを先頭に移動
            self.workspaceSelected.emit(path)
        else:
            QMessageBox.warning(self, "エラー", f"フォルダが存在しません:\n{path}")
            self._load_recent_workspaces() # 存在しないパスを履歴から消去するためにリロード