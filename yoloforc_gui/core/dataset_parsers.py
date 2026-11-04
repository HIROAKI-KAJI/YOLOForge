# yoloforc_gui/core/dataset_parsers.py
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

def parse_dataset_info(folder_path: Path) -> Optional[Dict[str, Any]]:
    """YOLOFORC向けの dataset_info.yaml からメタデータを抽出"""
    info_file = folder_path / "dataset_info.yaml"
    if not info_file.exists():
        return None
    
    try:
        with open(info_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return None
            return {
                "classes": [str(c) for c in data.get("classes", [])],
                "notes": str(data.get("notes", "")),
                "dataset_name": str(data.get("dataset_name", "")),
                "location": str(data.get("location", "")),
                "date_captured": str(data.get("date_captured", "")),
            }
    except Exception:
        return None