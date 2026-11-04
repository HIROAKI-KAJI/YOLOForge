import json
from pathlib import Path
from typing import List, Tuple
from .base import BaseImportStrategy
from ...validator.structure import SourceStructure

class LabelMeStrategy(BaseImportStrategy):
    def process(self, uid: str, source: Path, struct: SourceStructure) -> Tuple[int, int, List[str]]:
        image_count = 0
        label_count = 0
        warnings = []

        for img_path in struct.image_files:
            self.storage.safe_copy_image(img_path, uid)
            image_count += 1

            # 画像と同じディレクトリにある同名の .json を探す
            json_path = img_path.with_suffix(".json")
            if not json_path.exists():
                warnings.append(f"No JSON for image: {img_path.name}")
                continue

            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                img_w = data.get("imageWidth")
                img_h = data.get("imageHeight")
                if not img_w or not img_h:
                    warnings.append(f"Image dimensions missing in JSON: {json_path.name}")
                    continue

                yolo_lines = []
                for shape in data.get("shapes", []):
                    label = shape.get("label")
                    points = shape.get("points")
                    
                    if label not in self.dataset_classes:
                        warnings.append(f"Unknown class '{label}' skipped in {json_path.name}")
                        continue
                        
                    class_id = self.dataset_classes.index(label)

                    # ポリゴンや矩形の座標からBBoxを計算
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    xmin, xmax = min(x_coords), max(x_coords)
                    ymin, ymax = min(y_coords), max(y_coords)

                    # YOLO形式 (0~1) に正規化
                    x_center = ((xmin + xmax) / 2) / img_w
                    y_center = ((ymin + ymax) / 2) / img_h
                    width = (xmax - xmin) / img_w
                    height = (ymax - ymin) / img_h

                    yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

                # 変換した内容をTXTとして保存 (StorageProxyにテキスト書き出しメソッドがない場合は直接Pathで保存)
                if yolo_lines:
                    labels_dir = self.storage.dataset_dir / uid / "labels"
                    labels_dir.mkdir(parents=True, exist_ok=True)
                    txt_name = img_path.with_suffix(".txt").name
                    (labels_dir / txt_name).write_text("\n".join(yolo_lines) + "\n", encoding="utf-8")
                    label_count += 1

            except Exception as e:
                warnings.append(f"Failed to parse {json_path.name}: {e}")

        return image_count, label_count, warnings