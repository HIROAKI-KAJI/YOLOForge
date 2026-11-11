from PySide6.QtCore import QSettings
import importlib
import pkgutil
import sys
from pathlib import Path

class PluginManager:
    """プラグインの有効/無効状態を管理するクラス"""
    def __init__(self):
        self.settings = QSettings("YOLOForge", "Plugins")
        self.plugins_dir = Path("plugins")
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            
        # plugins ディレクトリをモジュール探索パスに追加
        if str(self.plugins_dir.resolve().parent) not in sys.path:
            sys.path.insert(0, str(self.plugins_dir.resolve().parent))

    def get_available_plugins(self):
        """pluginsディレクトリ内の利用可能なプラグイン名を取得"""
        plugins = []
        for _, name, _ in pkgutil.iter_modules([str(self.plugins_dir)]):
            plugins.append(name)
        return plugins

    def is_enabled(self, plugin_name):
        # デフォルトは無効
        return self.settings.value(f"{plugin_name}_enabled", False, type=bool)

    def set_enabled(self, plugin_name, enabled):
        self.settings.setValue(f"{plugin_name}_enabled", enabled)

    def get_enabled_plugins(self):
        return [p for p in self.get_available_plugins() if self.is_enabled(p)]
