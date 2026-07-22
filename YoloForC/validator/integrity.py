from pathlib import Path
from typing import List
from ..models import ValidationIssue
from ..storage.proxy import StorageProxy

class IntegrityValidator:
    def __init__(self, dataset_dir: Path):
        self.storage = StorageProxy(dataset_dir)
    
    def validate_uuid(self, uuid_dir: Path) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        uid = uuid_dir.name
        
        # 1. 必須構造
        for need in ["image", "labels"]:
            if not (uuid_dir / need).is_dir():
                issues.append(ValidationIssue("error", uid, f"{need}/ ディレクトリが存在しません"))
        
        meta = self.storage.read_meta_yaml(uuid_dir)
        
        # 2. image/labels ファイル名一致
        imgs = {p.stem for p in (uuid_dir / "image").glob("*.*")}
        lbls = {p.stem for p in (uuid_dir / "labels").glob("*.txt")}
        
        no_label = imgs - lbls
        no_image = lbls - imgs
        
        if no_label:
            issues.append(ValidationIssue("warning", uid, f"ラベルなし画像: {no_label}"))
        if no_image:
            issues.append(ValidationIssue("error", uid, f"画像なしラベル: {no_image}"))
        
        # 3. meta.yaml と実ファイル数の一致
        meta_img = meta.get("image_count")
        if meta_img is not None and meta_img != len(imgs):
            issues.append(ValidationIssue("warning", uid, 
                f"meta.image_count({meta_img}) != 実ファイル数({len(imgs)})"))
        
        return issues