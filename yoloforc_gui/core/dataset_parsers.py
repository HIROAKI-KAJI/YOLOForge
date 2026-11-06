# yoloforc_gui/core/dataset_parsers.py
import yaml
import json
from pathlib import Path
from typing import Optional, Dict, Any

import xml.etree.ElementTree as ET #XML解析用

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
    # 制限を撤廃し、全ファイルを走査してクラスの取りこぼしを防ぐ
    for jpath in json_files:
        try:
            with open(jpath, 'r', encoding='utf-8') as f:
                import json
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
        "dataset_name": folder_path.name,
    }

def parse_coco_info(folder_path: Path) -> Optional[Dict[str, Any]]:
    """MS COCOのJSONファイルからクラス（カテゴリ）を抽出"""
    json_files = list(folder_path.glob("*.json")) + list(folder_path.glob("annotations/*.json"))
    
    for jpath in json_files:
        try:
            with open(jpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "images" in data and "categories" in data and "annotations" in data:
                    # COCOのカテゴリをID順にソートして抽出
                    classes = [cat["name"] for cat in sorted(data["categories"], key=lambda x: x["id"])]
                    return {
                        "format": "MS COCO",
                        "classes": classes,
                        "notes": f"MS COCO形式からのインポート ({jpath.name})",
                        "dataset_name": folder_path.name,
                    }
        except Exception:
            continue
    return None


def parse_voc_info(folder_path: Path) -> Optional[Dict[str, Any]]:
    """Pascal VOCのXMLファイルからクラス（タグ）を抽出"""
    xml_files = list(folder_path.glob("*.xml")) + list(folder_path.glob("Annotations/*.xml"))
    if not xml_files:
        return None
        
    classes = set()
    # 制限を撤廃し、全ファイルを走査してクラスの取りこぼしを防ぐ
    import xml.etree.ElementTree as ET
    for xpath in xml_files:
        try:
            tree = ET.parse(xpath)
            root = tree.getroot()
            for obj in root.findall("object"):
                name = obj.find("name")
                if name is not None and name.text:
                    classes.add(name.text)
        except Exception:
            continue
            
    if not classes:
        return None
        
    return {
        "format": "Pascal VOC",
        "classes": sorted(list(classes)),
        "notes": "Pascal VOC (XML) 形式からのインポート",
        "dataset_name": folder_path.name,
    }


def detect_and_extract_metadata(folder_path: Path) -> Optional[Dict[str, Any]]:
    """複数のパーサーを順に試し、対応フォーマットのメタデータを返す"""
    # 1. 独自フォーマット
    meta = parse_kyolo_info(folder_path)
    if meta: return meta

    # 2. COCO フォーマット
    meta = parse_coco_info(folder_path)
    if meta: return meta
    
    # 3. LabelMe フォーマット
    meta = parse_labelme_info(folder_path)
    if meta: return meta

    # 4. Pascal VOC フォーマット
    meta = parse_voc_info(folder_path)
    if meta: return meta
    
    # 今後 COCO 等を追加する場合はここに追記
    return None