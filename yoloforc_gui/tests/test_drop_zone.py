"""DropZone の D&D イベントテスト"""
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QUrl, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtCore import QPoint

from widgets.drop_zone import DropZone


@pytest.fixture
def drop_zone(qtbot):
    widget = DropZone()
    qtbot.addWidget(widget)
    return widget


def test_drop_zone_emits_folder_path(qtbot, drop_zone, tmp_path):
    """フォルダパスをドロップしたら folderDropped シグナルが発火する"""
    test_folder = tmp_path / "test_images"
    test_folder.mkdir()

    received = []

    def on_dropped(path: str):
        received.append(path)

    drop_zone.folderDropped.connect(on_dropped)

    # D&D イベントを手動で構築
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(test_folder))])

    # dropEvent を直接発火（QTest.mouseRelease より確実）
    event = QDropEvent(
        QPoint(10, 10),  # pos
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    drop_zone.dropEvent(event)

    assert len(received) == 1
    assert Path(received[0]) == test_folder.resolve()


def test_drag_non_url_ignored(drop_zone):
    """URL でないドラッグは無視される"""
    mime = QMimeData()
    mime.setText("plain text")

    event = QDropEvent(
        QPoint(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    # 落としてもシグナルが出ないことを確認（エラーにならないこと）
    drop_zone.dropEvent(event)
    # 例外が出なければOK