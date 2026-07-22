"""物理ストレージへの読み書きを抽象化"""
import shutil
import uuid as uuid_lib
from pathlib import Path
from typing import List, Dict, Optional

from ..exceptions import YFCStorageError


class StorageProxy:
    def __init__(self, dataset_dir: Path):
        self.dataset_dir = Path(dataset_dir)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

    # --- パス解決 ---

    def uuid_dir(self, uuid: str) -> Path:
        return self.dataset_dir / uuid

    def exists(self, uuid: str) -> bool:
        return self.uuid_dir(uuid).is_dir()

    # --- UUID 管理 ---

    def generate_uuid_dir(self) -> Path:
        uid = uuid_lib.uuid4().hex[:12]
        dst = self.dataset_dir / uid
        if dst.exists():
            return self.generate_uuid_dir()
        dst.mkdir(parents=True)
        (dst / "image").mkdir()
        (dst / "labels").mkdir()
        return dst

    def list_uuid_dirs(self) -> List[Path]:
        if not self.dataset_dir.exists():
            return []
        return [d for d in self.dataset_dir.iterdir() if d.is_dir()]

    def delete_uuid(self, uuid: str):
        target = self.uuid_dir(uuid)
        if target.exists():
            shutil.rmtree(target)

    # --- YAML メタ ---

    def read_meta_yaml(self, uuid: str) -> Dict:
        import yaml
        p = self.uuid_dir(uuid) / "meta.yaml"
        if not p.exists():
            return {}
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception as e:
            raise YFCStorageError(f"meta.yaml read failed: {p}\n-> {e}")

    def write_meta_yaml(self, uuid: str, data: Dict):
        import yaml
        p = self.uuid_dir(uuid) / "meta.yaml"
        try:
            p.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8"
            )
        except Exception as e:
            raise YFCStorageError(f"meta.yaml write failed: {p}\n-> {e}")

    # --- image / labels / root file コピー ---

    def safe_copy_image(self, src: Path, uuid: str, dst_name: Optional[str] = None) -> Path:
        name = dst_name or Path(src).name
        dst = self.uuid_dir(uuid) / "image" / name
        if dst.exists():
            raise YFCStorageError(f"image already exists: {dst}")
        try:
            shutil.copy2(str(src), str(dst))
        except Exception as e:
            raise YFCStorageError(f"image copy failed: {src} -> {dst}\n-> {e}")
        return dst

    def safe_copy_label(self, src: Path, uuid: str, dst_name: Optional[str] = None) -> Path:
        name = dst_name or Path(src).name
        dst = self.uuid_dir(uuid) / "labels" / name
        if dst.exists():
            raise YFCStorageError(f"label already exists: {dst}")
        try:
            shutil.copy2(str(src), str(dst))
        except Exception as e:
            raise YFCStorageError(f"label copy failed: {src} -> {dst}\n-> {e}")
        return dst

    def copy_to_uuid_root(self, src: Path, uuid: str, dst_name: Optional[str] = None) -> Path:
        """classes.txt / data.yaml 等、UUID 直下に配置する付属ファイル用"""
        name = dst_name or Path(src).name
        dst = self.uuid_dir(uuid) / name
        if dst.exists():
            raise YFCStorageError(f"file already exists at uuid root: {dst}")
        try:
            shutil.copy2(str(src), str(dst))
        except Exception as e:
            raise YFCStorageError(f"root copy failed: {src} -> {dst}\n-> {e}")
        return dst

    # --- リスト取得 ---

    def list_images(self, uuid: str) -> List[Path]:
        d = self.uuid_dir(uuid) / "image"
        if not d.exists():
            return []
        return sorted(f for f in d.iterdir() if f.is_file())

    def list_labels(self, uuid: str) -> List[Path]:
        d = self.uuid_dir(uuid) / "labels"
        if not d.exists():
            return []
        return sorted(
            f for f in d.iterdir()
            if f.is_file() and f.suffix == ".txt"
        )