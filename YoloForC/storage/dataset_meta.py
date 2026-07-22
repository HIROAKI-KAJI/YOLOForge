"""dataset.yaml の読み書きを担当。
人間が編集するメタ情報と、システムが更新する total_images を統合して管理する。
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from ..models import DatasetMeta
from ..exceptions import YFCStorageError


DATASET_YAML_NAME = "dataset.yaml"


class DatasetMetaManager:
    def __init__(self, dataset_dir: Path):
        self.dataset_dir = Path(dataset_dir)
        self._path = self.dataset_dir / DATASET_YAML_NAME

    def exists(self) -> bool:
        return self._path.is_file()

    def create_template(
        self,
        dataset_name: str,
        classes: Optional[list] = None,
        date_captured: Optional[str] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> DatasetMeta:
        """dataset.yaml の雛形を新規作成する。
        データセットフォルダが未存在でも自動作成する。
        """
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

        meta = DatasetMeta(
            dataset_name=dataset_name,
            date_captured=date_captured,
            location=location,
            notes=notes,
            classes=list(classes) if classes else [],
            total_images=0,
        )
        self.write(meta)
        return meta

    def read(self) -> DatasetMeta:
        """dataset.yaml を読み込み DatasetMeta として返す。
        ファイルが存在しない場合は YFCStorageError。
        """
        if not self._path.exists():
            raise YFCStorageError(
                f"dataset.yaml が見つかりません: {self._path}\n"
                f"init_dataset() で雛形を作成してください。"
            )

        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            raise YFCStorageError(f"dataset.yaml の読み込みに失敗: {self._path}\n-> {e}")

        return DatasetMeta(
            dataset_name=raw.get("dataset_name", self.dataset_dir.name),
            date_captured=raw.get("date_captured"),
            location=raw.get("location"),
            notes=raw.get("notes"),
            classes=raw.get("classes", []) or [],
            total_images=raw.get("total_images", 0) or 0,
        )

    def write(self, meta: DatasetMeta):
        """DatasetMeta を、指定されたキー順序で書き出す。
        None 値も明示的に出力し、雛形としての可読性を保つ。
        """
        # ユーザーが示した順序を維持するため、挿入順を制御した dict を構築
        data: Dict[str, Any] = {}

        data["date_captured"] = meta.date_captured
        data["location"] = meta.location
        data["notes"] = meta.notes
        data["classes"] = list(meta.classes)
        data["dataset_name"] = meta.dataset_name
        data["total_images"] = int(meta.total_images)

        try:
            text = yaml.safe_dump(
                data,
                allow_unicode=True,
                sort_keys=False,          # 挿入順を維持
                default_flow_style=False, # block style
            )
            self._path.write_text(text, encoding="utf-8")
        except Exception as e:
            raise YFCStorageError(f"dataset.yaml の書き込みに失敗: {self._path}\n-> {e}")

    def patch(self, **kwargs) -> DatasetMeta:
        """既存 dataset.yaml の指定フィールドのみを更新して書き戻す。
        存在しないキーは無視せずエラーとする（誤字防止）。
        """
        allowed = {"date_captured", "location", "notes",
                   "classes", "dataset_name", "total_images"}
        unknown = set(kwargs) - allowed
        if unknown:
            raise YFCStorageError(f"dataset.yaml に無効なフィールド: {unknown}")

        meta = self.read()
        for k, v in kwargs.items():
            setattr(meta, k, v)
        self.write(meta)
        return meta

    def update_total_images(self, count: int) -> DatasetMeta:
        """total_images のみを安全に更新（IndexManager 等から呼び出し想定）"""
        return self.patch(total_images=count)