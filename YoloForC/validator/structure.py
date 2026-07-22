"""外部フォルダの構造をスキャンし、画像と YOLO .txt の対応関係を把握する"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


@dataclass
class SourceStructure:
    pattern: str                    # "standard", "standard_split", "flat", "unknown"
    image_files: List[Path]         # 画像の絶対パス（ソート済み）
    label_map: Dict[str, Path]      # stem -> .txt の絶対パス
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


def _collect_labels(dir_path: Path) -> List[Path]:
    """classes.txt はクラス名定義ファイルなのでラベルとして除外"""
    return sorted(
        f.resolve()
        for f in dir_path.iterdir()
        if (
            f.is_file()
            and f.suffix.lower() == ".txt"
            and f.name != "classes.txt"
        )
    )


def _collect_labels_recursive(dir_path: Path) -> List[Path]:
    """classes.txt はクラス名定義ファイルなのでラベルとして除外"""
    return sorted(
        f.resolve()
        for f in dir_path.rglob("*")
        if (
            f.is_file()
            and f.suffix.lower() == ".txt"
            and f.name != "classes.txt"
        )
    )


def _stem_map(files: List[Path]) -> Dict[str, Path]:
    return {f.stem: f for f in files}


# --- public ---

def analyze_folder(path: Path) -> SourceStructure:
    """ソースディレクトリを走査し、画像と同名 .txt の対応マップを返す。"""
    root = Path(path).resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")

    # Pattern A: standard — images/ + labels/ （直下または train/val サブフォルダ）
    img_dir = root / "images"
    lbl_dir = root / "labels"
    if img_dir.is_dir() and lbl_dir.is_dir():
        return SourceStructure(
            pattern="standard",
            image_files=_collect_images_recursive(img_dir),
            label_map=_stem_map(_collect_labels_recursive(lbl_dir)),
            root=root,
        )

    # Pattern B: standard_split — train/images + train/labels 等
    for split in ("train", "valid", "val", "test"):
        sd_img = root / split / "images"
        sd_lbl = root / split / "labels"
        if sd_img.is_dir() and sd_lbl.is_dir():
            return SourceStructure(
                pattern="standard_split",
                image_files=_collect_images_recursive(sd_img),
                label_map=_stem_map(_collect_labels_recursive(sd_lbl)),
                root=root,
                split=split,
            )

    # Pattern C: flat — 画像と .txt が同一フォルダに混在
    imgs = _collect_images(root)
    lbls = _collect_labels(root)
    if imgs:
        return SourceStructure(
            pattern="flat",
            image_files=imgs,
            label_map=_stem_map(lbls),
            root=root,
        )

    return SourceStructure(
        pattern="unknown",
        image_files=[],
        label_map={},
        root=root,
    )