# YoloForC/importer/strategies/coco.py
import json
from pathlib import Path
from typing import List, Tuple, Dict, Any
from .base import BaseImportStrategy
from ...validator.structure import SourceStructure

class CocoStrategy(BaseImportStrategy):
    def process(self, uid: str, source: Path, struct: SourceStructure, progress_callback=None) -> Tuple[int, int, List[str]]:
        image_count = 0
        label_count = 0
        warnings = []

        # 1. COCO JSONの探索 (直下、または annotations/ フォルダ内)
        json_files = list(source.glob("*.json")) + list(source.glob("annotations/*.json"))
        coco_data = None
        for jpath in json_files:
            try:
                with open(jpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "images" in data and "categories" in data and "annotations" in data:
                        coco_data = data
                        break
            except Exception:
                continue
                
        if not coco_data:
            warnings.append("COCO形式のJSON (images, categories, annotations を含む) が見つかりませんでした。")
            return image_count, label_count, warnings

        # 2. COCOデータのマッピング構築
        # カテゴリID -> YOLOクラスインデックス
        cat_id_to_yolo_idx = {}
        for cat in coco_data.get("categories", []):
            cat_name = cat.get("name")
            if cat_name in self.dataset_classes:
                cat_id_to_yolo_idx[cat.get("id")] = self.dataset_classes.index(cat_name)
            else:
                warnings.append(f"Unknown category '{cat_name}' in COCO JSON.")

        # 画像ファイル名 -> (image_id, width, height)
        img_name_to_info = {
            Path(img["file_name"]).name: (img["id"], img["width"], img["height"])
            for img in coco_data.get("images", [])
        }

        # image_id -> アノテーションリスト
        img_id_to_anns = {}
        for ann in coco_data.get("annotations", []):
            img_id = ann.get("image_id")
            if img_id not in img_id_to_anns:
                img_id_to_anns[img_id] = []
            img_id_to_anns[img_id].append(ann)

        total = len(struct.image_files)

        # 3. ファイルコピーとYOLO変換
        for i, img_path in enumerate(struct.image_files):
            self.storage.safe_copy_image(img_path, uid)
            image_count += 1
            
            img_info = img_name_to_info.get(img_path.name)
            if img_info:
                img_id, img_w, img_h = img_info
                anns = img_id_to_anns.get(img_id, [])
                
                yolo_lines = []
                for ann in anns:
                    cat_id = ann.get("category_id")
                    if cat_id not in cat_id_to_yolo_idx:
                        continue # 未知のクラスやマッピング対象外はスキップ
                        
                    yolo_class_id = cat_id_to_yolo_idx[cat_id]
                    bbox = ann.get("bbox") # COCO: [x_min, y_min, width, height]
                    if not bbox or len(bbox) != 4:
                        continue
                        
                    x_min, y_min, bw, bh = bbox
                    
                    # YOLO相対座標 (中心x, 中心y, 幅, 高さ) に変換
                    x_center = (x_min + bw / 2.0) / img_w
                    y_center = (y_min + bh / 2.0) / img_h
                    w_norm = bw / img_w
                    h_norm = bh / img_h
                    
                    # 範囲クランプ (0.0 ~ 1.0)
                    x_center = max(0.0, min(1.0, x_center))
                    y_center = max(0.0, min(1.0, y_center))
                    w_norm = max(0.0, min(1.0, w_norm))
                    h_norm = max(0.0, min(1.0, h_norm))
                    
                    yolo_lines.append(f"{yolo_class_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")
                
                # TXT出力
                if yolo_lines:
                    labels_dir = self.storage.dataset_dir / uid / "labels"
                    labels_dir.mkdir(parents=True, exist_ok=True)
                    txt_name = img_path.with_suffix(".txt").name
                    (labels_dir / txt_name).write_text("\n".join(yolo_lines) + "\n", encoding="utf-8")
                    label_count += 1
            else:
                warnings.append(f"Image {img_path.name} not found in COCO JSON.")

            if progress_callback:
                progress_callback(i + 1, total, f"MS COCO変換中: {img_path.name}")

        return image_count, label_count, warnings