"""データセット詳細画面：閲覧、インポート、Rebuild、設定編集、VIEWボタン。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QTableView, QMessageBox, QGroupBox, QDialog,
)

from ..core.bridge import YFCBridge
from ..models.view_models import UUIDTableModel
from .import_wizard import ImportWizard
from .dataset_meta_dialog import DatasetMetaEditDialog
from .button_delegate import ButtonDelegate
from .uuid_viewer_dialog import UUIDViewerDialog


class DatasetDetailPage(QWidget):
    def __init__(self, bridge: YFCBridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.dataset_name: str = ""

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # === dataset.yaml 表示 ===
        meta_group = QGroupBox("Dataset Meta (dataset.yaml)")
        meta_layout = QFormLayout(meta_group)

        self.lbl_name = QLabel("-")
        self.lbl_classes = QLabel("-")
        self.lbl_total = QLabel("-")
        self.lbl_notes = QLabel("-")

        meta_layout.addRow("Name:", self.lbl_name)
        meta_layout.addRow("Classes:", self.lbl_classes)
        meta_layout.addRow("Total Images:", self.lbl_total)
        meta_layout.addRow("Notes:", self.lbl_notes)
        layout.addWidget(meta_group)

        # === ツールバー ===
        tbar = QHBoxLayout()
        self.btn_back = QPushButton("← 一覧へ戻る")
        self.btn_edit_meta = QPushButton("✏ 設定編集")
        self.btn_rebuild = QPushButton("Rebuild Index")
        self.btn_import = QPushButton("+ インポート")

        tbar.addWidget(self.btn_back)
        tbar.addWidget(self.btn_edit_meta)
        tbar.addStretch()
        tbar.addWidget(self.btn_rebuild)
        tbar.addWidget(self.btn_import)
        layout.addLayout(tbar)

        # === UUID 一覧 ===
        layout.addWidget(QLabel("Batches (UUIDs):"))
        self.table = QTableView()
        self._model = UUIDTableModel(self)
        self.table.setModel(self._model)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)

        # --- Action 列にボタン Delegate を設定 ---
        self._btn_delegate = ButtonDelegate(label="VIEW", parent=self)
        # Action 列 = インデックス 6
        self.table.setItemDelegateForColumn(6, self._btn_delegate)
        self._btn_delegate.buttonClicked.connect(self._open_uuid_viewer)

        layout.addWidget(self.table)

        # === シグナル ===
        self.btn_rebuild.clicked.connect(self._on_rebuild)
        self.btn_import.clicked.connect(self._on_import)
        self.btn_edit_meta.clicked.connect(self._on_edit_meta)

    def set_dataset(self, name: str):
        self.dataset_name = name
        self.setWindowTitle(f"Dataset: {name}")
        self.refresh()

    def refresh(self):
        meta = self.bridge.get_dataset_meta(self.dataset_name)
        if meta:
            self.lbl_name.setText(str(meta.get("dataset_name") or "-"))
            cls = meta.get("classes") or []
            self.lbl_classes.setText(", ".join(cls) if cls else "(未定義)")
            self.lbl_total.setText(str(meta.get("total_images") or 0))
            self.lbl_notes.setText(str(meta.get("notes") or meta.get("note") or "-"))
        else:
            self.lbl_name.setText("-")
            self.lbl_classes.setText("-")
            self.lbl_total.setText("-")
            self.lbl_notes.setText("-")

        records = self.bridge.list_uuids(self.dataset_name)
        self._model.refresh(records)

    def _on_rebuild(self):
        if self.bridge.rebuild_index(self.dataset_name):
            QMessageBox.information(self, "完了", "Index を再構築しました。")
            self.refresh()

    def _on_import(self):
        meta = self.bridge.get_dataset_meta(self.dataset_name)
        default_classes = list(meta.get("classes") or []) if meta else []

        wiz = ImportWizard(
            self.bridge,
            self.dataset_name,
            default_classes,
            parent=self,
        )
        if wiz.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_edit_meta(self):
        """dataset.yaml の classes / notes / date_captured 等を編集"""
        meta = self.bridge.get_dataset_meta(self.dataset_name)
        if not meta:
            QMessageBox.warning(self, "エラー", "メタデータが読み込めません。")
            return

        dlg = DatasetMetaEditDialog(meta, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        values = dlg.get_values()
        # None のものは除外（update_dataset_meta で無視されるようにするため、None 送ってもよいが安全のため）
        patch = {k: v for k, v in values.items() if v is not None}

        # 変更検出（空打ち防止）
        changed = False
        for k, v in patch.items():
            if meta.get(k) != v:
                changed = True
                break

        if not changed:
            return

        if self.bridge.update_dataset_meta(self.dataset_name, **patch):
            QMessageBox.information(self, "完了", "設定を保存しました。")
            self.refresh()

    def _open_uuid_viewer(self, row: int):
        idx = self._model.index(row, 0)
        uuid = idx.data()
        detail = self.bridge.get_uuid_detail(self.dataset_name, uuid)
        if not detail:
            QMessageBox.warning(self, "エラー", "UUID 情報が取得できません。")
            return

        paths = detail.get("files")
        if not paths or not paths.get("images"):
            QMessageBox.warning(self, "エラー", "ファイル情報がありません。")
            return

        from pathlib import Path

        first_img = Path(paths["images"][0])
        first_lbl = Path(paths["labels"][0]) if paths.get("labels") else None

        img_dir = str(first_img.parent if first_img.is_file() else first_img)
        lbl_dir = str(first_lbl.parent if (first_lbl and first_lbl.is_file()) else (first_lbl or ""))

        # dataset.yaml からクラス名を取得
        meta = self.bridge.get_dataset_meta(self.dataset_name)
        class_names = meta.get("classes", []) if meta else []

        dlg = UUIDViewerDialog(
            uuid=uuid,
            image_dir=img_dir,
            labels_dir=lbl_dir,
            class_names=class_names,  # ← 追加
            parent=self,
        )
        dlg.exec()
        self.refresh()