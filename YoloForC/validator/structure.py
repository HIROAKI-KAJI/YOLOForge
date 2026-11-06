"""外部フォルダの構造をスキャンし、画像とラベルファイル（txt, xml, json）の対応関係を把握する"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
# 今後の拡張に対応するため xml (Pascal VOC) と json (LabelMe/COCO) を追加
LABEL_EXTS = {".txt", ".xml", ".json"}

@dataclass
class SourceStructure:
    pattern: str                    # "voc", "standard", "standard_split", "flat", "unknown"
    image_files: List[Path]         # 画像の絶対パス（ソート済み）
    label_map: Dict[str, Path]      # stem -> ラベルファイル (.txt/.xml/.json) の絶対パス
    root: Path
    split: Optional[str] = None     # standard_split の場合の "train" 等


# --- private helpers ---

def _collect_images(dir_path: Path) -> List[Path]:
    return sorted(
        f.resolve()
        for f in dir_path.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS
    )

def _collect_images_recursive(dir_path: Path) -> List[Path]:
    return sorted(
        f.resolve()
        for f in dir_path.rglob("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS
    )

def _collect_labels(dir_path: Path, exts: set = LABEL_EXTS) -> List[Path]:
    """classes.txt はクラス名定義ファイルなのでラベルとして除外"""
    return sorted(
        f.resolve()
        for f in dir_path.iterdir()
        if (
            f.is_file()
            and f.suffix.lower() in exts
            and f.name != "classes.txt"
        )
    )

def _collect_labels_recursive(dir_path: Path, exts: set = LABEL_EXTS) -> List[Path]:
    """classes.txt はクラス名定義ファイルなのでラベルとして除外"""
    return sorted(
        f.resolve()
        for f in dir_path.rglob("*")
        if (
            f.is_file()
            and f.suffix.lower() in exts
            and f.name != "classes.txt"
        )
    )

def _stem_map(files: List[Path]) -> Dict[str, Path]:
    return {f.stem: f for f in files}


# --- public ---

def analyze_folder(path: Path) -> SourceStructure:
    """ソースディレクトリを走査し、画像と同名ラベルの対応マップを返す。"""
    root = Path(path).resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")

    # -------------------------------------------------------------
    # Pattern VOC: Pascal VOC形式 (JPEGImages/ + Annotations/)
    # -------------------------------------------------------------
    jpeg_dir = root / "JPEGImages"
    ann_dir = root / "Annotations"
    if jpeg_dir.is_dir():
        lbl_map = _stem_map(_collect_labels_recursive(ann_dir, {".xml"})) if ann_dir.is_dir() else {}
        return SourceStructure(
            pattern="voc",
            image_files=_collect_images_recursive(jpeg_dir),
            label_map=lbl_map,
            root=root,
        )

    # -------------------------------------------------------------
    # Pattern A: standard — images/ + (labels/ または annotations/)
    # -------------------------------------------------------------
    img_dir = root / "images"
    if img_dir.is_dir():
        lbl_dir = root / "labels"
        # COCO等の場合は labels/ が無くても画像だけ認識して pattern="standard" とする
        lbl_map = _stem_map(_collect_labels_recursive(lbl_dir)) if lbl_dir.is_dir() else {}
        return SourceStructure(
            pattern="standard",
            image_files=_collect_images_recursive(img_dir),
            label_map=lbl_map,
            root=root,
        )

    # -------------------------------------------------------------
    # Pattern B: standard_split — train/images + train/labels 等
    # -------------------------------------------------------------
    for split in ("train", "valid", "val", "test"):
        sd_img = root / split / "images"
        if sd_img.is_dir():
            sd_lbl = root / split / "labels"
            lbl_map = _stem_map(_collect_labels_recursive(sd_lbl)) if sd_lbl.is_dir() else {}
            return SourceStructure(
                pattern="standard_split",
                image_files=_collect_images_recursive(sd_img),
                label_map=lbl_map,
                root=root,
                split=split,
            )

    # -------------------------------------------------------------
    # Pattern C: flat — 画像とラベルが同一フォルダに混在 (LabelMe等)
    # -------------------------------------------------------------
    imgs = _collect_images(root)
    lbls = _collect_labels(root)
    if imgs:
        return SourceStructure(
            pattern="flat",
            image_files=imgs,
            label_map=_stem_map(lbls),
            root=root,
        )

    # -------------------------------------------------------------
    # Pattern D: unknown
    # -------------------------------------------------------------
    return SourceStructure(
        pattern="unknown",
        image_files=[],
        label_map={},
        root=root,
    )