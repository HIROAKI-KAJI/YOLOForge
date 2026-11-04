from pathlib import Path
from typing import List, Tuple
from .base import BaseImportStrategy
from ...validator.structure import SourceStructure

class KYoloStrategy(BaseImportStrategy):
   def process(self, uid: str, source: Path, struct: SourceStructure, progress_callback=None):
        image_count = 0
        label_count = 0
        warnings = []
        total = len(struct.image_files)

        for i, img_path in enumerate(struct.image_files):
            # --- コピー処理 ---
            self.storage.safe_copy_image(img_path, uid)
            image_count += 1

            label_path = struct.label_map.get(img_path.stem)
            if label_path and Path(label_path).exists():
                self.storage.safe_copy_label(Path(label_path), uid)
                label_count += 1
            else:
                warnings.append(f"No label file for image: {img_path.name}")

            if progress_callback:
                progress_callback(i + 1, total, f"処理中: {img_path.name}")

        return image_count, label_count, warnings