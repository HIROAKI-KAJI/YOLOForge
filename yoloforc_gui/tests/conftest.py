"""テスト用共通フィクスチャ"""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator
import pytest
from PySide6.QtWidgets import QApplication

# yoloforc_gui と YoloForC をインポート可能にする
_GUI_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _GUI_ROOT.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from YoloForC import YoloForC
from yoloforc_gui.core.bridge import YFCBridge


@pytest.fixture(scope="session")
def qapp():
    """pytest-qt が自動生成する前に、sys.argv を制御したい場合に備えて定義（任意）"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    yield app
    app.quit()


@pytest.fixture
def temp_yfc_root() -> Generator[Path, None, None]:
    """一時ディレクトリを YoloForC ルートとして初期化する。
    テスト後に自動削除される。
    """
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir) / "yfc_test_root"
        YoloForC.init_root(root, comment="test environment")
        yield root.resolve()


@pytest.fixture
def preconfigured_bridge(
    temp_yfc_root: Path, monkeypatch
) -> Generator[YFCBridge, None, None]:
    """ダイアログを出さずに初期化済みルートで接続する Bridge。
    テスト中に QFileDialog 等が出るのを防ぐ。
    """
    # 環境変数でルートを固定
    monkeypatch.setenv("YFC_ROOT", str(temp_yfc_root))
    # bridge.__init__ 内のダイアログを出さないよう、QMessageBox の static メソッドを無害化
    monkeypatch.setattr(
        "core.bridge.QMessageBox.question",
        lambda *a, **k: __import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        "core.bridge.QMessageBox.critical",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "core.bridge.QMessageBox.warning",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "core.bridge.QMessageBox.information",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "core.bridge.QFileDialog.getExistingDirectory",
        lambda *a, **k: str(temp_yfc_root),
    )

    bridge = YFCBridge()
    # 本 fixture 使用時は必ず初期化済みなので ready=True が期待値
    assert bridge.ready
    yield bridge
    # 特にクリーンアップ不要（tempdir の自動削除で消える）