from pathlib import Path
from typing import List, Optional

from .config import Config
from .storage.proxy import StorageProxy

from .storage.index_manager import IndexManager
from .storage.initializer import RootInitializer
from .storage.dataset_meta import DatasetMetaManager

from .importer.batch import BatchImporter
from .validator.integrity import IntegrityValidator
from .models import ImportResult, DatasetValidationReport, ValidationIssue, UuidRecord, DatasetMeta
from .exceptions import YFCValidationError, YFCStorageError

class YoloForC:
    """
    Class to handle YOLO Dataset manager. YOLO Forge Connector. 
    This class is responsible for managing the YOLO dataset and connecting to the YOLO Forge.
    """
    def __init__(self, root: Optional[Path] = None):
        self.config = Config(root_override=root)

    # --- ルート初期化（クラスメソッド：インスタンス化前に呼び出し可能） ---
    @staticmethod
    def init_root(path: Path, comment: Optional[str] = None) -> Path:
        """新規のストレージルートを初期化する。
        初回セットアップ時に1回実行することで、そのパスを以降の YoloForC インスタンスで利用可能になる。
        """
        return RootInitializer.initialize(Path(path), comment=comment)

    def _proxy(self, dataset_name: str):
        from .storage.proxy import StorageProxy
        return StorageProxy(self.config.dataset_dir(dataset_name))
    def import_folder(self, source: Path, dataset_name: str,
                      tags: Optional[List[str]] = None,
                      annotator: Optional[str] = None) -> ImportResult:
        dset_dir = self.config.dataset_dir(dataset_name)
        importer = BatchImporter(dset_dir)
        return importer.import_folder(Path(source), tags=tags, annotator=annotator)

    # --- データセット単位メタ管理 ---

    def init_dataset(
        self,
        dataset_name: str,
        classes: Optional[List[str]] = None,
        date_captured: Optional[str] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> DatasetMeta:
        """データセットフォルダを新規作成し、dataset.yaml の雛形を生成する。
        既に存在する場合は上書きしない（read→返す）。
        """
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
        """dataset.yaml の指定フィールドを更新する。
        例: update_dataset_meta("defect", notes="追記", total_images=1500)
        """
        return DatasetMetaManager(self.config.dataset_dir(dataset_name)).patch(**kwargs)
    
    def validate_dataset(self, dataset_name: str, rebuild_index: bool = False) -> DatasetValidationReport:
        dset_dir = self.config.dataset_dir(dataset_name)
        report = DatasetValidationReport(dataset_name=dataset_name)
        validator = IntegrityValidator(dset_dir)
        storage = self._proxy(dataset_name)
        
        for uuid_dir in storage.list_uuid_dirs():
            issues = validator.validate_uuid(uuid_dir)
            report.errors.extend([i for i in issues if i.level == "error"])
            report.warnings.extend([i for i in issues if i.level == "warning"])
        
        if rebuild_index:
            IndexManager(dset_dir).rebuild()
        
        return report
    
    def rebuild_index(self, dataset_name: str) -> dict:
        dset_dir = self.config.dataset_dir(dataset_name)
        return IndexManager(dset_dir).rebuild()
    
    def list_uuids(self, dataset_name: str, status: Optional[str] = None) -> List[UuidRecord]:
        dset_dir = self.config.dataset_dir(dataset_name)
        idx = IndexManager(dset_dir).load_index()
        records = []
        for rec in idx.get("records", []):
            if status and rec.get("status") != status:
                continue
            records.append(UuidRecord(**{k: rec[k] for k in rec if k in UuidRecord.__dataclass_fields__}))
        return records
    
    def get_uuid_paths(self, dataset_name: str, uuid: str):
        dset_dir = self.config.dataset_dir(dataset_name)
        uid_dir = dset_dir / uuid
        if not uid_dir.exists():
            raise FileNotFoundError
        return {
            "root": uid_dir,
            "image": uid_dir / "image",
            "labels": uid_dir / "labels",
            "meta": uid_dir / "meta.yaml",
        }
    
    def update_uuid_meta(self, dataset_name: str, uuid: str, patch: dict):
        """安全なメタ更新（上書き保護付き）"""
        import datetime
        ALLOWED = {"status", "tags", "annotator", "reviewer", "comment"}
        if not set(patch).issubset(ALLOWED):
            raise ValueError(f"許可されていないフィールド: {set(patch) - ALLOWED}")
        
        dset_dir = self.config.dataset_dir(dataset_name)
        uid_dir = dset_dir / uuid
        storage = self._proxy(dataset_name)
        meta = storage.read_meta_yaml(uid_dir)
        meta.update(patch)
        meta["updated_at"] = datetime.datetime.now().isoformat()
        storage.write_meta_yaml(uid_dir, meta)
    
    def import_folder(
        self,
        source: Path,
        dataset_name: str,
        classes: Optional[List[str]] = None,
        note: Optional[str] = None,
        tags: Optional[List[str]] = None,
        annotator: Optional[str] = None,
    ) -> ImportResult:
        """外部フォルダ（YOLO形式）を YoloForC 管理下へインポートする。
        事前に init_dataset() で dataset.yaml（classes含む）を作成しておく必要がある。

        Args:
            source: インポートする YOLO フォルダ
            dataset_name: データセット名
            classes: このバッチのクラス名リスト。呼び出し側が既に把握している場合に指定。
                    指定するとソースファイルの自動検出をスキップする。
            note: バッチ作業メモ
            tags: 任意タグ
            annotator: 実施者名
        """
        dset_dir = self.config.dataset_dir(dataset_name)

        from .storage.dataset_meta import DatasetMetaManager
        meta_mgr = DatasetMetaManager(dset_dir)
        if not meta_mgr.exists():
            raise YFCValidationError(
                f"dataset.yaml が見つかりません。 "
                f"init_dataset('{dataset_name}', classes=[...]) でデータセットを初期化してください。"
            )
        dataset_meta = meta_mgr.read()

        importer = BatchImporter(dset_dir, dataset_meta)
        return importer.import_folder(
            source=Path(source),
            classes=classes,
            note=note,
            tags=tags,
            annotator=annotator,
        )