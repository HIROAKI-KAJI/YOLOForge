from pathlib import Path
from typing import Optional, List, Dict
import shutil

from .config import Config
from .storage.initializer import RootInitializer
from .storage.proxy import StorageProxy
from .storage.index_manager import IndexManager
from .storage.dataset_meta import DatasetMetaManager
from .storage.exporter import YoloExporter
from .importer.batch import BatchImporter
from .models import ImportResult, DatasetMeta
from .exceptions import YFCValidationError, YFCNotFoundError


class YoloForC:
    """YoloForC ファサード。外部ツール・フロントエンドはこのクラスのみを利用する。"""

    def __init__(self, root: Optional[Path] = None):
        self.config = Config(root_override=root, strict=True)

    # --- ルート初期化 ---

    @staticmethod
    def init_root(path: Path, comment: Optional[str] = None) -> Path:
        """ストレージルートを初期化する。初回セットアップ時に1回実行する。"""
        return RootInitializer.initialize(Path(path), comment=comment)

    # --- データセット単位メタ管理 ---

    def init_dataset(
        self,
        dataset_name: str,
        classes: Optional[List[str]] = None,
        date_captured: Optional[str] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> DatasetMeta:
        """データセットフォルダを新規作成し、dataset.yaml の雛形を生成する。"""
        mgr = DatasetMetaManager(self.config.dataset_dir(dataset_name))
        if mgr.exists():
            return mgr.read()
        return mgr.create_template(
            dataset_name=dataset_name,
            classes=classes,
            date_captured=date_captured,
            location=location,
            notes=notes,
        )

    def get_dataset_meta(self, dataset_name: str) -> DatasetMeta:
        """dataset.yaml を読み込む"""
        return DatasetMetaManager(self.config.dataset_dir(dataset_name)).read()

    def update_dataset_meta(self, dataset_name: str, **kwargs) -> DatasetMeta:
        """dataset.yaml の指定フィールドを更新する"""
        return DatasetMetaManager(self.config.dataset_dir(dataset_name)).patch(**kwargs)

    # --- インポート ---

    def import_folder(
        self,
        source: Path,
        dataset_name: str,
        classes: Optional[List[str]] = None,
        note: Optional[str] = None,
        tags: Optional[List[str]] = None,
        annotator: Optional[str] = None,
    ) -> ImportResult:
        """外部フォルダ（YOLO形式）を UUID 管理下へインポートする。
        完了後、自動で index.yaml と dataset.yaml total_images を同期する。
        """
        dset_dir = self.config.dataset_dir(dataset_name)

        meta_mgr = DatasetMetaManager(dset_dir)
        if not meta_mgr.exists():
            raise YFCValidationError(
                f"dataset.yaml が見つかりません。 "
                f"init_dataset('{dataset_name}', classes=[...]) でデータセットを初期化してください。"
            )
        dataset_meta = meta_mgr.read()

        importer = BatchImporter(dset_dir, dataset_meta)
        result = importer.import_folder(
            source=Path(source),
            classes=classes,
            note=note,
            tags=tags,
            annotator=annotator,
        )

        # 自動同期: index.yaml + total_images
        self.rebuild_index(dataset_name)

        return result

    # --- インデックス・検索 ---

    def rebuild_index(self, dataset_name: str) -> Dict:
        """index.yaml を全走査で再構築し、dataset.yaml の total_images も同期する。
        フロントの「更新ボタン」相当。
        """
        dset_dir = self.config.dataset_dir(dataset_name)
        result = IndexManager(dset_dir).rebuild()

        # dataset.yaml の total_images も自動更新
        try:
            total = result.get("total_image_count", 0)
            DatasetMetaManager(dset_dir).update_total_images(total)
        except Exception:
            pass
        return result

    def list_datasets(self) -> List[str]:
        """ルート下のデータセット名一覧（dataset.yaml の存在するもののみ）"""
        root = self.config.root
        if not root.exists():
            return []
        return [
            d.name for d in root.iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and (d / "dataset.yaml").exists()
        ]

    def list_uuids(
        self,
        dataset_name: str,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """UUID レコード一覧。フロントの表一覧表示用。"""
        mgr = IndexManager(self.config.dataset_dir(dataset_name))
        idx = mgr.load_index()
        records = idx.get("records", [])
        if status:
            records = [r for r in records if r.get("status") == status]
        return records

    def get_uuid_detail(self, dataset_name: str, uuid: str) -> Dict:
        """特定UUIDの詳細情報とファイル一覧を取得する。"""
        proxy = StorageProxy(self.config.dataset_dir(dataset_name))
        if not proxy.exists(uuid):
            raise YFCNotFoundError(f"UUID not found: {uuid} in dataset '{dataset_name}'")

        return {
            "meta": proxy.read_meta_yaml(uuid),
            "files": {
                "images": [str(p) for p in proxy.list_images(uuid)],
                "labels": [str(p) for p in proxy.list_labels(uuid)],
            },
        }

    # --- 削除 ---

    def delete_uuid(self, dataset_name: str, uuid: str):
        """指定UUIDフォルダを完全削除する。index.yaml は次回 rebuild で整合性が取れる。"""
        proxy = StorageProxy(self.config.dataset_dir(dataset_name))
        if not proxy.exists(uuid):
            raise YFCNotFoundError(f"UUID not found: {uuid} in dataset '{dataset_name}'")
        proxy.delete_uuid(uuid)

    def delete_dataset(self, dataset_name: str):
        """データセットフォルダ全体を削除する。"""
        dset_dir = self.config.dataset_dir(dataset_name)
        if not dset_dir.exists():
            raise YFCNotFoundError(f"Dataset not found: {dataset_name}")
        shutil.rmtree(dset_dir)

    # --- 学習連携（エクスポート） ---

    def export_yolo_ready(
        self,
        dataset_name: str,
        output_dir: Path,
        mode: str = "symlink",
        filter_status: Optional[str] = None,
        filter_tags: Optional[List[str]] = None,
    ) -> Path:
        """学習器に直接渡せる YOLO 構成を output_dir へ出力する。
        シンボリックリンク or コピーで UUID 下のファイルを集約する。
        """
        dset_dir = self.config.dataset_dir(dataset_name)
        if not dset_dir.exists():
            raise YFCNotFoundError(f"Dataset not found: {dataset_name}")
        exporter = YoloExporter(dset_dir)
        return exporter.export(
            Path(output_dir),
            mode=mode,
            filter_status=filter_status,
            filter_tags=filter_tags,
        )