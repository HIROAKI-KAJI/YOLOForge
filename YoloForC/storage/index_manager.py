import yaml
from pathlib import Path
from typing import List, Dict

from YoloForC.storage.dataset_meta import DatasetMetaManager
from .proxy import StorageProxy

class IndexManager:
    def __init__(self, dataset_dir: Path):
        self.dataset_dir = dataset_dir
        self.index_path = dataset_dir / "index.yaml"
    
    def rebuild(self) -> Dict:
        """全UUIDフォルダを走査して index.yaml を再構築"""
        proxy = StorageProxy(self.dataset_dir)
        records = []
        
        total_images = 0
        for uuid_dir in proxy.list_uuid_dirs():
            meta = proxy.read_meta_yaml(uuid_dir)
            img_count = len(list((uuid_dir / "image").glob("*.*")))
            lbl_count = len(list((uuid_dir / "labels").glob("*.txt")))
            total_images += img_count
            
            records.append({
                "uuid": uuid_dir.name,
                "path": str(uuid_dir.relative_to(self.dataset_dir)),
                "image_count": img_count,
                "label_count": lbl_count,
                "status": meta.get("status", "draft"),
                "annotator": meta.get("annotator"),
                "tags": meta.get("tags", []),
                "imported_from": meta.get("source_format"),
                "updated_at": meta.get("updated_at"),
            })
        
        index = {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "dataset_name": self.dataset_dir.name,
            "total_uuid_count": len(records),
            "total_image_count": total_images,
            "records": records,
        }
        
        self.index_path.write_text(
            yaml.safe_dump(index, allow_unicode=True, sort_keys=False),
            encoding="utf-8"
        )

        # dataset.yaml の total_images を更新
        try:
            meta_mgr = DatasetMetaManager(self.dataset_dir)
            if meta_mgr.exists():
                meta_mgr.update_total_images(total_images)
        except Exception:
            # dataset.yaml が存在しない（まだinit_datasetしていない）場合は無視
            pass
        return index
    
    def load_index(self) -> Dict:
        if not self.index_path.exists():
            return {}
        return yaml.safe_load(self.index_path.read_text(encoding="utf-8")) or {}