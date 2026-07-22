"""YoloForC ライブラリのラッパー。GUI スレッド専用。"""
import os
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

from PySide6.QtWidgets import QFileDialog, QMessageBox

from YoloForC import YoloForC
from YoloForC.exceptions import YFCError
from YoloForC.storage.initializer import RootInitializer
from YoloForC.validator.structure import analyze_folder as _analyze_folder
from YoloForC.models import ImportResult


class YFCBridge:
    def __init__(self, parent_widget=None):
        """parent_widget: QMessageBox の親ウィンドウとして渡す（None可）"""
        self.parent = parent_widget
        self._yfc: Optional[YoloForC] = None
        self._root_path: Optional[Path] = None
        self.ready = False

        self._resolve_root()
        if self._root_path:
            try:
                self._yfc = YoloForC(root=self._root_path)
                self.ready = True
            except Exception as e:
                QMessageBox.critical(self.parent, "接続エラー", str(e))

    # --- 内部ヘルパー ---

    def _resolve_root(self):
        """環境変数 > ダイアログ選択/作成 でルートを解決"""
        env_root = os.environ.get("YFC_ROOT")
        if env_root:
            p = Path(env_root).resolve()
            if RootInitializer.is_initialized(p):
                self._root_path = p
                return

        # ダイアログで既存選択を促す
        reply = QMessageBox.question(
            None,
            "YoloForC ルート設定",
            "YFC_ROOT が未設定です。\n"
            "既存のルートを選択しますか？\n"
            "（いいえ = 新規作成）",
        )
        if reply == QMessageBox.StandardButton.Yes:
            path_str, _ = QFileDialog.getOpenFileName(
                None,
                "ルートマーカー (.yoloforc_root) を選択",
                str(Path.home()),
                "Marker (.yoloforc_root)",
            )
            # 実際にはファイル選択ではなくフォルダ選択の方が自然なので、
            # ファイルダイアログで選択されたパスの親を採用
            if path_str:
                p = Path(path_str).parent
                if RootInitializer.is_initialized(p):
                    self._root_path = p
                else:
                    QMessageBox.warning(None, "未初期化", "選択されたフォルダは管理下ではありません。")
        else:
            path_str = QFileDialog.getExistingDirectory(
                None, "新規ルートの作成先フォルダを選択"
            )
            if path_str:
                p = Path(path_str).resolve()
                YoloForC.init_root(p)
                QMessageBox.information(
                    None, "完了",
                    f"以下にルートを初期化しました:\n{p}"
                )
                self._root_path = p

    def _call(self, func, *args, **kwargs) -> Any:
        """例外をキャッチして UI に表示。成功時は結果を返す。"""
        try:
            return func(*args, **kwargs)
        except YFCError as e:
            QMessageBox.critical(None, "YoloForC エラー", str(e))
        except Exception as e:
            QMessageBox.critical(None, "予期しないエラー", f"{type(e).__name__}: {e}")
        return None

    # --- データセット ---

    def init_dataset(
        self,
        name: str,
        classes: List[str],
        notes: str = "",
        date_captured: str = "",
        location: str = "",
    ) -> bool:
        res = self._call(
            self._yfc.init_dataset,
            dataset_name=name,
            classes=classes,
            notes=notes,
            date_captured=date_captured,
            location=location,
        )
        return res is not None

    def list_datasets(self) -> List[str]:
        if not self._yfc:
            return []
        return self._yfc.list_datasets()

    def get_dataset_meta(self, dataset_name: str) -> Optional[Dict[str, Any]]:
        if not self._yfc:
            return None
        meta = self._call(self._yfc.get_dataset_meta, dataset_name)
        if meta is None:
            return None
        # DatasetMeta dataclass -> dict
        if hasattr(meta, "__dataclass_fields__"):
            return asdict(meta)
        return meta

    def update_dataset_meta(self, dataset_name: str, **kwargs) -> bool:
        res = self._call(self._yfc.update_dataset_meta, dataset_name, **kwargs)
        return res is not None

    def rebuild_index(self, dataset_name: str) -> bool:
        res = self._call(self._yfc.rebuild_index, dataset_name)
        return res is not None

    def list_uuids(self, dataset_name: str) -> List[Dict[str, Any]]:
        if not self._yfc:
            return []
        return self._yfc.list_uuids(dataset_name)

    def get_uuid_detail(self, dataset_name: str, uuid: str) -> Optional[Dict[str, Any]]:
        if not self._yfc:
            return None
        return self._call(self._yfc.get_uuid_detail, dataset_name, uuid)

    def delete_uuid(self, dataset_name: str, uuid: str) -> bool:
        reply = QMessageBox.question(
            None,
            "確認",
            f"UUID {uuid} を完全に削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False
        self._call(self._yfc.delete_uuid, dataset_name, uuid)
        return True

    # --- インポート ---

    def import_folder(
        self,
        dataset_name: str,
        source: str,
        classes: Optional[List[str]],
        note: str,
        annotator: str,
        tags: Optional[List[str]],
    ) -> Optional[ImportResult]:
        return self._call(
            self._yfc.import_folder,
            source=source,
            dataset_name=dataset_name,
            classes=classes,
            note=note,
            annotator=annotator,
            tags=tags,
        )

    def analyze_source_structure(self, path: str) -> Optional[Dict[str, Any]]:
        """インポート前の構造プレビュー"""
        try:
            struct = _analyze_folder(Path(path))
            return {
                "pattern": struct.pattern,
                "image_count": len(struct.image_files),
                "label_count": len(struct.label_map),
            }
        except Exception as e:
            QMessageBox.warning(None, "構造解析エラー", str(e))
            return None

    # --- エクスポート（将来的に利用可能） ---
    def export_yolo_ready(
        self,
        dataset_name: str,
        output_dir: str,
        mode: str = "symlink",
        filter_status: Optional[str] = None,
    ) -> Optional[Path]:
        return self._call(
            self._yfc.export_yolo_ready,
            dataset_name=dataset_name,
            output_dir=output_dir,
            mode=mode,
            filter_status=filter_status,
        )