"""インポートフロー統合テスト（Bridge + ImportWizard + 実際のファイルコピー）"""
import pytest
from pathlib import Path
from PySide6.QtWidgets import QMessageBox

from widgets.import_wizard import ImportWizard


@pytest.fixture
def sample_yolo_dataset(tmp_path: Path) -> Path:
    """ダミーの YOLO フォルダを作成"""
    root = tmp_path / "sample_yolo"
    images = root / "images"
    labels = root / "labels"
    images.mkdir(parents=True)
    labels.mkdir(parents=True)

    # ダミー画像（PIL で最小 1x1 PNG を生成）
    try:
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        img.save(images / "0001.jpg")
        img.save(images / "0002.jpg")
    except ImportError:
        # Pillow が無い場合は空ファイルで代用（構造テスト用）
        (images / "0001.jpg").write_bytes(b"")
        (images / "0002.jpg").write_bytes(b"")

    # YOLO ラベル
    (labels / "0001.txt").write_text("0 0.5 0.5 0.1 0.1\n")
    (labels / "0002.txt").write_text("1 0.3 0.3 0.2 0.2\n")

    return root


@pytest.fixture
def wizard(qtbot, preconfigured_bridge, sample_yolo_dataset):
    """ダイアログを無害化しつつウィザードを生成"""
    wiz = ImportWizard(
        bridge=preconfigured_bridge,
        dataset_name="test_set",
        default_classes=["dog", "cat"],
    )
    qtbot.addWidget(wiz)
    # accept/reject 中に表示されるメッセージボックスを抑制
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    yield wiz
    monkeypatch.undo()


def test_wizard_accepts_drop_and_shows_preview(qtbot, wizard, sample_yolo_dataset):
    """D&D 後にプレビューが更新され、OK ボタンが有効になる"""
    # 初期状態は disabled
    assert not wizard.btns.button(wizard.btns.StandardButton.Ok).isEnabled()

    # ドロップをシミュレート
    wizard._on_drop(str(sample_yolo_dataset))

    assert "standard" in wizard.lbl_pattern.text()
    assert "Images: 2" in wizard.lbl_counts.text()
    assert wizard.btns.button(wizard.btns.StandardButton.Ok).isEnabled()


def test_import_executes_and_creates_uuid(
    qtbot, preconfigured_bridge, wizard, sample_yolo_dataset,
    monkeypatch
):
    """実際にインポートを実行し、UUID が生成される"""
    # 事前にデータセットを作成
    preconfigured_bridge.init_dataset(
        "test_set", classes=["dog", "cat"]
    )

    # ドロップ
    wizard._on_drop(str(sample_yolo_dataset))
    wizard.edit_note.setText("unit test batch")
    wizard.edit_annotator.setText("pytest")

    # accept は内部的に _execute -> import_folder を呼ぶ
    # メッセージボックスを抑制
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    # インポート実行
    wizard._execute()

    # インポート成功後、ダイアログは accept 状態になっているはず
    # （メッセージボックスが模擬的に閉じられた後）
    # UUID が生成されていることを確認
    uuids = preconfigured_bridge.list_uuids("test_set")
    assert len(uuids) == 1
    assert uuids[0]["image_count"] == 2
    assert uuids[0]["label_count"] == 2