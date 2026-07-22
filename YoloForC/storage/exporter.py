"""UUID管理構造を YOLO 学習器（ultralytics等）が直接読める構成へ出力する"""
import shutil
from pathlib import Path
from typing import List, Optional

import yaml as pyyaml

from ..models import DatasetMeta
from ..exceptions import YFCStorageError
from .proxy import StorageProxy
from .index_manager import IndexManager
from .dataset_meta import DatasetMetaManager


class YoloExporter:
    def __init__(self, dataset_dir: Path):
        self.dataset_dir = Path(dataset_dir)

    def export(
        self,
        output_dir: Path,
        mode: str = "symlink",
        filter_status: Optional[str] = None,
        filter_tags: Optional[List[str]] = None,
    ) -> Path:
        """UUID 管理下の画像・ラベルを output_dir/images/train, labels/train へ集約出力する。

        Args:
            output_dir: 学習用データセットの出力先
            mode: "symlink" or "copy"
            filter_status: 指定すればその status のUUIDのみ出力（例: "approved"）
            filter_tags: 指定すればいずれかのタグを含むUUIDのみ出力

        Returns:
            出力された output_dir のパス
        """
        output_dir = Path(output_dir).resolve()
        out_img_dir = output_dir / "images" / "train"
        out_lbl_dir = output_dir / "labels" / "train"
        out_img_dir.mkdir(parents=True, exist_ok=True)
        out_lbl_dir.mkdir(parents=True, exist_ok=True)

        proxy = StorageProxy(self.dataset_dir)
        idx = IndexManager(self.dataset_dir).load_index()

        written = 0
        for rec in idx.get("records", []):
            # --- フィルタ ---
            if filter_status and rec.get("status") != filter_status:
                continue
            if filter_tags:
                tags = set(rec.get("batch_tags") or rec.get("tags") or [])
                if not any(t in tags for t in filter_tags):
                    continue

            uid = rec["uuid"]
            for img_path in proxy.list_images(uid):
                dst_name = f"{uid}_{img_path.name}"
                dst_img = out_img_dir / dst_name
                src_lbl = proxy.uuid_dir(uid) / "labels" / f"{img_path.stem}.txt"
                dst_lbl = out_lbl_dir / f"{uid}_{img_path.stem}.txt"

                # image
                if mode == "symlink":
                    if dst_img.exists() or dst_img.is_symlink():
                        dst_img.unlink()
                    dst_img.symlink_to(img_path.resolve())
                elif mode == "copy":
                    if not dst_img.exists():
                        shutil.copy2(str(img_path), str(dst_img))
                else:
                    raise ValueError(f"Unknown export mode: {mode}")

                # label（存在すれば）
                if src_lbl.exists():
                    if mode == "symlink":
                        if dst_lbl.exists() or dst_lbl.is_symlink():
                            dst_lbl.unlink()
                        dst_lbl.symlink_to(src_lbl.resolve())
                    elif mode == "copy":
                        if not dst_lbl.exists():
                            shutil.copy2(str(src_lbl), str(dst_lbl))

                written += 1

        # --- data.yaml 生成 ---
        meta_mgr = DatasetMetaManager(self.dataset_dir)
        if meta_mgr.exists():
            dataset_meta = meta_mgr.read()
        else:
            dataset_meta = DatasetMeta(
                dataset_name=self.dataset_dir.name, classes=[]
            )

        names = {i: c for i, c in enumerate(dataset_meta.classes)}

        data = {
            "path": str(output_dir),
            "train": "images/train",
            "val": "images/train",  # 当面 train と同じ。val 分割は将来拡張
            "nc": len(dataset_meta.classes),
            "names": names,
        }

        try:
            (output_dir / "data.yaml").write_text(
                pyyaml.safe_dump(
                    data,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            raise YFCStorageError(f"data.yaml 書き込み失敗: {e}")

        return output_dir