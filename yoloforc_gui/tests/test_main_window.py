"""メインウィンドウの画面遷移テスト"""
import pytest
from PySide6.QtWidgets import QMessageBox

from widgets.main_window import MainWindow


@pytest.fixture
def main_window(qtbot, preconfigured_bridge, monkeypatch):
    """テスト用メインウィンドウ"""
    # 新規作成ダイアログ等が出ないよう抑制
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    mw = MainWindow(preconfigured_bridge)
    qtbot.addWidget(mw)
    return mw


def test_initial_state_shows_list(main_window):
    """初期表示はデータセット一覧画面（index 0）"""
    assert main_window.stack.currentIndex() == 0


def test_create_and_open_dataset_flow(
    qtbot, main_window, preconfigured_bridge, monkeypatch
):
    """データセット作成 → 一覧更新 → 詳細画面遷移 をテスト"""
    # データセット作成
    assert preconfigured_bridge.init_dataset(
        "demo_ds",
        classes=["a", "b", "c"],
        notes="test note",
    )

    # ナビ更新（手動またはシグナル）
    main_window.refresh_nav()

    # 一覧に表示されているか
    nav = main_window.nav_list
    items = [nav.item(i).text() for i in range(nav.count())]
    assert "demo_ds" in items

    # 詳細画面を開く
    main_window.open_dataset_detail("demo_ds")
    assert main_window.stack.currentIndex() == 1
    assert main_window.page_detail.dataset_name == "demo_ds"
    assert "a, b, c" in main_window.page_detail.lbl_classes.text()


def test_back_button_returns_to_list(main_window, preconfigured_bridge):
    """戻るボタンで一覧画面に戻る"""
    # 事前準備
    preconfigured_bridge.init_dataset("nav_test", classes=["x"])
    main_window.refresh_nav()
    main_window.open_dataset_detail("nav_test")

    assert main_window.stack.currentIndex() == 1

    # 戻るボタンクリック
    main_window.page_detail.btn_back.click()
    assert main_window.stack.currentIndex() == 0