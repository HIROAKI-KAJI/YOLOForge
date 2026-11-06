# yoloforc_gui/core/dataset_parsers.py
import yaml
import json
from pathlib import Path
from typing import Optional, Dict, Any

def parse_kyolo_info(folder_path: Path) -> Optional[Dict[str, Any]]:
    """独自の dataset_info.yaml からメタデータを抽出"""
    info_file = folder_path / "dataset_info.yaml"
    if not info_file.exists():
        return None
    try:
        with open(info_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return None
            return {
                "format": "KYOLO (独自形式)",
                "classes": [str(c) for c in data.get("classes", [])],
                "notes": str(data.get("notes", "")),
                "dataset_name": str(data.get("dataset_name", "")),
            }
    except Exception:
        return None

def parse_labelme_info(folder_path: Path) -> Optional[Dict[str, Any]]:
    """LabelMeのJSONファイル群からクラス（タグ）を動的に抽出"""
    json_files = list(folder_path.glob("*.json"))
    if not json_files:
        return None
    
    classes = set()
    # パフォーマンスのため、最初の50件だけ走査してクラスを拾い上げる
    for jpath in json_files[:50]:
        try:
            with open(jpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for shape in data.get("shapes", []):
                    lbl = shape.get("label")
                    if lbl:
                        classes.add(lbl)
        except Exception:
            continue
    
    if not classes:
        return None
        
    return {
        "format": "LabelMe",
        "classes": sorted(list(classes)),
        "notes": "LabelMe形式からのインポート",
        "dataset_name": folder_path.name,  # フォルダ名を仮のデータセット名にする
    }

def detect_and_extract_metadata(folder_path: Path) -> Optional[Dict[str, Any]]:
    """複数のパーサーを順に試し、対応フォーマットのメタデータを返す"""
    # 1. 独自フォーマット
    meta = parse_kyolo_info(folder_path)
    if meta: return meta
    
    # 2. LabelMe フォーマット
    meta = parse_labelme_info(folder_path)
    if meta: return meta
    
    # 今後 COCO 等を追加する場合はここに追記
    return None