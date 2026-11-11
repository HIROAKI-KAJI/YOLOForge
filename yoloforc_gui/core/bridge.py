"""YoloForC ライブラリのラッパー。GUI スレッド専用。"""
import os
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

from PySide6.QtWidgets import QMessageBox

from YoloForC import YoloForC
from YoloForC.exceptions import YFCError
from YoloForC.storage.initializer import RootInitializer
from YoloForC.validator.structure import analyze_folder as _analyze_folder
from YoloForC.models import ImportResult

from .dataset_parsers import detect_and_extract_metadata

class YFCBridge:
    def __init__(self, parent_widget=None):
        """parent_widget: QMessageBox の親ウィンドウとして渡す（None可）"""
        self.parent = parent_widget
        self._yfc: Optional[YoloForC] = None
        self._root_path: Optional[Path] = None
        
        # 起動時は未接続状態を正とする
        self.ready = False

    def initialize_root(self, path_str: str) -> bool:
        """
        GUI（Welcome Dashboard等）から指定されたパスで YoloForC を初期化する。
        未初期化フォルダの場合は、自動的にルート初期化（.yoloforc_rootの生成）を行う。
        """
        p = Path(path_str).resolve()
        
        try:
            # 指定されたパスがルートマーカーを持っていない場合は初期化（新規作成）
            if not RootInitializer.is_initialized(p):
                YoloForC.init_root(p)
            
            # YoloForCバックエンドのインスタンス生成
            self._yfc = YoloForC(root=p)
            self._root_path = p
            self.ready = True
            return True
        except Exception as e:
            QMessageBox.critical(self.parent, "接続エラー", f"ワークスペースの初期化に失敗しました:\n{e}")
            self.ready = False
            self._yfc = None
            self._root_path = None
            return False

    # --- 内部ヘルパー ---

    def _call(self, func, *args, **kwargs) -> Any:
        """例外をキャッチして UI に表示。成功時は結果を返す。"""
        if not self.ready or not self._yfc:
            QMessageBox.warning(self.parent, "未接続", "ワークスペースが初期化されていません。")
            return None
            
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
        if not self.ready:
            return []
        return self._yfc.list_datasets()

    def get_dataset_meta(self, dataset_name: str) -> Optional[Dict[str, Any]]:
        if not self.ready:
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
        if not self.ready:
            return []
        return self._yfc.list_uuids(dataset_name)

    def get_uuid_detail(self, dataset_name: str, uuid: str) -> Optional[Dict[str, Any]]:
        if not self.ready:
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

    def extract_metadata_from_source(self, path: str) -> Optional[Dict[str, Any]]:
        """インポート元のディレクトリからメタデータ（クラスやメモ）を自動抽出する"""
        try:
            return detect_and_extract_metadata(Path(path))
        except Exception as e:
            print(f"Failed to parse metadata: {e}")
            return None

    def import_folder_async(
        self,
        dataset_name: str,
        source: str,
        classes: Optional[List[str]],
        note: str,
        annotator: str,
        tags: Optional[List[str]],
        progress_callback=None
    ) -> Optional[ImportResult]:
        """バックグラウンドワーカーから呼ばれるコールバック付きインポート"""
        if not self.ready or not self._yfc:
            raise Exception("ワークスペースが初期化されていません。")
        
        # YoloForC (バックエンド) の import_folder に progress_callback を渡す
        return self._yfc.import_folder(
            source=source,
            dataset_name=dataset_name,
            classes=classes,
            note=note,
            annotator=annotator,
            tags=tags,
            progress_callback=progress_callback
        )

    def analyze_source_structure(self, path: str) -> Optional[Dict[str, Any]]:
        """インポート前の構造プレビュー（YoloForCのインスタンスに依存しない純粋関数として処理）"""
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