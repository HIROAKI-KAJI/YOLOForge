"""データセット一覧・新規登録画面"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QPushButton,
    QHBoxLayout, QLabel,QDialog, QInputDialog, QMessageBox,
)

from .new_dataset_dialog import NewDatasetDialog
from .progress_dialog import ProgressDialog
from ..core.workers import ImportWorker

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
        dlg = NewDatasetDialog(self.bridge, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        vals = dlg.get_values()
        name = vals["name"]
        classes = vals["classes"]
        notes = vals["notes"]
        source_path = vals["source_path"]  # ← 追加

        # バリデーション
        if not name.replace("_", "").replace("-", "").isalnum():
            QMessageBox.warning(self, "入力エラー", "英数字、アンダースコア、ハイフンのみ使用可能です。")
            return

        if name in self.bridge.list_datasets():
            QMessageBox.warning(self, "重複", f"'{name}' は既に存在します。")
            return

        if not classes:
            QMessageBox.warning(self, "入力エラー", "クラス名は1つ以上必要です。")
            return

        # 1. データセットの初期化 (dataset.yaml の作成)
        success = self.bridge.init_dataset(
            name=name,
            classes=classes,
            notes=notes,
        )

        if success:
            if source_path:
                # 同時インポートを非同期で実行
                self.progress_dlg = ProgressDialog(self, title=f"初期インポート — {name}")
                self.worker = ImportWorker(
                    bridge=self.bridge, dataset_name=name, source=source_path,
                    classes=classes, note="初回インポート (データセット作成時)",
                    annotator="", tags=["initial_import"]
                )
                
                self.worker.progressChanged.connect(self.progress_dlg.update_progress)
                self.worker.formatDetected.connect(self.progress_dlg.set_format)
                
                def on_success(res):
                    self.progress_dlg.accept()
                    QMessageBox.information(self, "完了", f"データセットを作成し、インポートを完了しました。\nImages: {res.image_count}")
                    self.refresh()
                
                def on_error(err):
                    self.progress_dlg.reject()
                    QMessageBox.warning(self, "警告", f"データセットは作成されましたが、インポートに失敗しました:\n{err}")
                    self.refresh()
                
                self.worker.finishedSuccessfully.connect(on_success)
                self.worker.errorOccurred.connect(on_error)
                
                self.worker.start()
                self.progress_dlg.exec()
            else:
                QMessageBox.information(self, "完了", f"データセット '{name}' を手動で作成しました。")
                self.refresh()
            
            self.refresh()