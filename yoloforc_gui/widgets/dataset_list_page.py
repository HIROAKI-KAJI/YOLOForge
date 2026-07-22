"""データセット一覧・新規登録画面"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QPushButton,
    QHBoxLayout, QLabel, QInputDialog, QMessageBox,
)


class DatasetListPage(QWidget):
    datasetSelected = str  # シグナル用（外部で connect）

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("データセット一覧"))

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        toolbar = QHBoxLayout()
        self.btn_new = QPushButton("+ 新規データセット")
        self.btn_new.clicked.connect(self._on_new)
        self.btn_reload = QPushButton("再読み込み")
        self.btn_reload.clicked.connect(self.refresh)
        toolbar.addWidget(self.btn_new)
        toolbar.addWidget(self.btn_reload)
        layout.addLayout(toolbar)

        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        names = self.bridge.list_datasets()
        self.list_widget.addItems(sorted(names))

    def current_name(self) -> str:
        item = self.list_widget.currentItem()
        return item.text() if item else ""

    def _on_double_click(self):
        name = self.current_name()
        if name:
            # 親（MainWindow）に委譲するため、直接開かずにシグナル的に処理
            # ここでは window() を使って親に伝える簡易方式
            mw = self.window()
            if hasattr(mw, "open_dataset_detail"):
                mw.open_dataset_detail(name)

    def _on_new(self):
        name, ok = QInputDialog.getText(
            self, "新規データセット", "データセット名（英数字）:"
        )
        if not ok or not name:
            return

        # 英数字簡易チェック（ライブラリ側でもチェックされるが先に弾く）
        if not name.replace("_", "").replace("-", "").isalnum():
            QMessageBox.warning(self, "入力エラー", "英数字、アンダースコア、ハイフンのみ使用可能です。")
            return

        if name in self.bridge.list_datasets():
            QMessageBox.warning(self, "重複", f"'{name}' は既に存在します。")
            return

        cls_text, ok2 = QInputDialog.getText(
            self,
            "クラス定義",
            "クラス名をカンマ区切りで入力:",
            text="class0, class1",
        )
        if not ok2:
            return
        classes = [c.strip() for c in cls_text.split(",") if c.strip()]
        if not classes:
            QMessageBox.warning(self, "入力エラー", "クラス名は1つ以上必要です。")
            return

        notes, ok3 = QInputDialog.getText(
            self, "メモ（任意）", "Notes:", text=""
        )
        notes = notes if ok3 else ""

        success = self.bridge.init_dataset(
            name=name,
            classes=classes,
            notes=notes,
        )
        if success:
            QMessageBox.information(self, "完了", f"データセット '{name}' を作成しました。")
            self.refresh()