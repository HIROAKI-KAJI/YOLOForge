from PySide6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QPushButton, QHBoxLayout, QMessageBox, QLabel

from ..core.config import plugin_manager

class PluginSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("プラグイン設定")
        self.resize(300, 400)
        self.manager = plugin_manager
        self.checkboxes = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        available = self.manager.get_available_plugins()
        
        if not available:
            layout.addWidget(QLabel("利用可能なプラグインが見つかりません。\n（プロジェクト直下の 'plugins' フォルダに配置してください）"))
            
        for p in available:
            cb = QCheckBox(p)
            cb.setChecked(self.manager.is_enabled(p))
            layout.addWidget(cb)
            self.checkboxes[p] = cb
            
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存して閉じる")
        btn_save.clicked.connect(self._save)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _save(self):
        for p, cb in self.checkboxes.items():
            self.manager.set_enabled(p, cb.isChecked())
        QMessageBox.information(self, "保存完了", "設定を保存しました。\n変更を反映させるにはビューアを開き直すか、アプリを再起動してください。")
        self.accept()
