# YoloForC/importer/strategies/voc.py
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple
from .base import BaseImportStrategy
from ...validator.structure import SourceStructure

# VOC形式のXMLを解析してYOLO形式に変換するインポート戦略
# パサーではあくまで　画像とタグ付けした結果のXMLのフォルダが渡されているモノとして処理を行う。

class VocStrategy(BaseImportStrategy):
    def process(self, uid: str, source: Path, struct: SourceStructure, progress_callback=None) -> Tuple[int, int, List[str]]:
        image_count = 0
        label_count = 0
        warnings = []
        total = len(struct.image_files)

        for i, img_path in enumerate(struct.image_files):
            self.storage.safe_copy_image(img_path, uid)
            image_count += 1

            # XMLファイルを探す (同階層 または annotations/ フォルダ等)
            xml_path = img_path.with_suffix(".xml")
            if not xml_path.exists():
                alt_xml = source / "Annotations" / f"{img_path.stem}.xml"
                if alt_xml.exists():
                    xml_path = alt_xml

            if xml_path.exists():
                try:
                    tree = ET.parse(xml_path)
                    root = tree.getroot()
                    
                    size_node = root.find("size")
                    if size_node is None:
                        warnings.append(f"Size info missing in {xml_path.name}")
                        continue
                        
                    img_w = float(size_node.find("width").text)
                    img_h = float(size_node.find("height").text)
                    
                    if img_w <= 0 or img_h <= 0:
                        warnings.append(f"Invalid image size in {xml_path.name}")
                        continue

                    yolo_lines = []
                    for obj in root.findall("object"):
                        name = obj.find("name").text
                        if name not in self.dataset_classes:
                            warnings.append(f"Unknown class '{name}' skipped in {xml_path.name}")
                            continue
                            
                        class_id = self.dataset_classes.index(name)
                        bndbox = obj.find("bndbox")
                        
                        xmin = float(bndbox.find("xmin").text)
                        ymin = float(bndbox.find("ymin").text)
                        xmax = float(bndbox.find("xmax").text)
                        ymax = float(bndbox.find("ymax").text)
                        
                        # YOLO相対座標 (中心x, 中心y, 幅, 高さ) に変換
                        bw = xmax - xmin
                        bh = ymax - ymin
                        x_center = (xmin + bw / 2.0) / img_w
                        y_center = (ymin + bh / 2.0) / img_h
                        w_norm = bw / img_w
                        h_norm = bh / img_h
                        
                        # 0.0 ~ 1.0 にクランプ
                        x_center = max(0.0, min(1.0, x_center))
                        y_center = max(0.0, min(1.0, y_center))
                        w_norm = max(0.0, min(1.0, w_norm))
                        h_norm = max(0.0, min(1.0, h_norm))
                        
                        yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")
                    
                    if yolo_lines:
                        labels_dir = self.storage.dataset_dir / uid / "labels"
                        labels_dir.mkdir(parents=True, exist_ok=True)
                        txt_name = img_path.with_suffix(".txt").name
                        (labels_dir / txt_name).write_text("\n".join(yolo_lines) + "\n", encoding="utf-8")
                        label_count += 1
                        
                except Exception as e:
                    warnings.append(f"Failed to parse {xml_path.name}: {e}")
            else:
                warnings.append(f"No XML for image: {img_path.name}")

            if progress_callback:
                progress_callback(i + 1, total, f"Pascal VOC変換中: {img_path.name}")

        return image_count, label_count, warnings