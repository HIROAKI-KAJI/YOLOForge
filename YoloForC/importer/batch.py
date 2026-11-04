"""YOLO 形式フォルダを UUID 管理単位へ取り込む。
呼び出し側が classes を把握している場合は引数で渡し、
ソースフォルダの自動検出を省略・不要なファイル出力を避ける。
"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from ..storage.proxy import StorageProxy
from ..models import ImportResult, DatasetMeta
from ..validator.structure import analyze_folder, SourceStructure
from ..exceptions import YFCValidationError, YFCStorageError

from .strategies.kyolo_text import KYoloStrategy
from .strategies.labelme import LabelMeStrategy

class BatchImporter:
    def __init__(self, dataset_dir: Path, dataset_meta: DatasetMeta):
        self.storage = StorageProxy(dataset_dir)
        self.dataset_classes = list(dataset_meta.classes) if dataset_meta.classes else []
        self.dataset_name = dataset_meta.dataset_name

    def import_folder(
        self,
        source: Path,
        classes: Optional[List[str]] = None,
        note: Optional[str] = None,
        tags: Optional[List[str]] = None,
        annotator: Optional[str] = None,
        progress_callback=None, # progress_callback: (current, total, message)
    ) -> ImportResult:
        """source ディレクトリ（YOLO 準拠）を1バッチとして UUID 下に保存する。

        Args:
            source: YOLO 形式フォルダのパス
            classes: 呼び出し側が指定するクラス名リスト。
                     指定があればソースファイルの自動検出をスキップする。
            note: このバッチの作業メモ
            tags: バッチに対する任意タグ
            annotator: ラベリング実施者名
        """
        source = Path(source).resolve()
        if not source.is_dir():
            raise YFCValidationError(f"source is not a directory: {source}")

        struct = analyze_folder(source)
        if struct.pattern == "unknown":
            raise YFCValidationError(
                f"unrecognized folder structure. expected YOLO layout (images/labels/ or flat mixed): {source}"
            )
        if not struct.image_files:
            raise YFCValidationError(f"no images found in source: {source}")

        # --- クラス解決・検証 ---
        if classes is not None:
            # 呼び出し側が明示指定 → 自動検出をスキップ
            source_classes = [str(c) for c in classes]
        else:
            # フォールバック: ソースファイルから自動検出
            source_classes = self._resolve_source_classes(source, struct)

        self._validate_classes(source_classes, struct)

        # progress_callback ===============
        # 形式の判定を先に行い、総ファイル数を把握
        fmt = self._detect_format(struct)
        total_files = len(struct.image_files)
        
        if progress_callback:
            progress_callback(0, total_files, f"形式を検知しました: {fmt.upper()}。コピーを開始します...")
        # /progress_callback ===============


        # UUID 発行。ここから例外が出ればロールバック
        uuid_dir = self.storage.generate_uuid_dir()
        uid = uuid_dir.name

        try:
            return self._copy_transaction(
                uid=uid,
                struct=struct,
                source=source,
                source_classes=source_classes,
                note=note,
                tags=tags,
                annotator=annotator,
                progress_callback=progress_callback # ← Strategyに渡す
            )
        except Exception:
            self.storage.delete_uuid(uid)
            raise

    def _detect_format(self, struct) -> str:
        """画像と同じ階層のファイルを見て形式を判定する"""
        if not struct.image_files:
            return "unknown"
        # 最初の数枚の画像に対してJSONが存在するかチェック
        for img in struct.image_files[:5]:
            if img.with_suffix(".json").exists():
                return "labelme"
        return "yolo"

    def _copy_transaction(
        self, uid, struct, source, source_classes, note, tags, annotator, progress_callback=None
    )-> ImportResult:
        # 1. 形式の判定
        fmt = self._detect_format(struct)
        
        # 2. ルーティング
        if fmt == "labelme":
            strategy = LabelMeStrategy(self.storage, self.dataset_classes)
        else:
            strategy = KYoloStrategy(self.storage, self.dataset_classes)

        # 3. 実際のコピーと変換を委譲
        image_count, label_count, warnings = strategy.process(
            uid=uid, 
            source=source, 
            struct=struct, 
            progress_callback=progress_callback
        )

        # 4. 付属ファイルのコピー (既存処理)
        extra_candidates = ["classes.txt", "data.yaml", "data.yml", "dataset_info.yaml"]
        copied_extras = []
        for name in extra_candidates:
            src_file = source / name
            if src_file.is_file():
                try:
                    self.storage.copy_to_uuid_root(src_file, uid)
                    copied_extras.append(name)
                except Exception:
                    pass

        # メタ情報書き出し
        meta = {
            "uuid": uid,
            "source_format": "YOLO",
            "source_path": str(source),
            "imported_at": datetime.now().isoformat(),
            "annotator": annotator,
            "note": note or "",
            "classes": source_classes,
            "batch_tags": list(tags) if tags else [],
            "status": "draft",
            "image_count": image_count,
            "label_count": label_count,
            "folder_pattern": struct.pattern,
            "split": struct.split,
            "extra_files": copied_extras,
        }
        self.storage.write_meta_yaml(uid, meta)

        return ImportResult(
            uuid=uid,
            dataset_name=self.dataset_name,
            image_count=image_count,
            label_count=label_count,
            warnings=warnings,
        )

    # --- class validation ---

    def _validate_classes(self, source_classes: List[str], struct: SourceStructure) -> None:
        """dataset.yaml のマスタークラス定義とソースを検証する。
        - source_classes が指定されていれば：dataset_classes のサブセットか確認
        - class_id のみの場合（YOLO .txt）：dataset_classes の範囲内か確認
        """
        if source_classes:
            unknown = set(source_classes) - set(self.dataset_classes)
            if unknown:
                raise YFCValidationError(
                    f"指定/検出されたクラス名のうち、dataset.yaml に未定義のものがあります: {sorted(unknown)}\n"
                    f"dataset_classes: {self.dataset_classes}"
                )
            return

        # クラス名リストが空の場合：class_id で範囲チェック
        max_id = -1
        for img_path in struct.image_files:
            lbl = struct.label_map.get(img_path.stem)
            if not lbl:
                continue
            try:
                for line in lbl.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if parts:
                        cid = int(parts[0])
                        if cid > max_id:
                            max_id = cid
            except Exception:
                continue

        if self.dataset_classes and max_id >= len(self.dataset_classes):
            raise YFCValidationError(
                f"ラベル内の class_id ({max_id}) が、"
                f"dataset.yaml の classes 数 ({len(self.dataset_classes)}) を超えています。\n"
                f"dataset_classes: {self.dataset_classes}"
            )

        if not self.dataset_classes and max_id >= 0:
            raise YFCValidationError(
                f"dataset.yaml に classes が定義されていませんが、"
                f"ラベルに class_id ({max_id}) が存在します。"
            )

    # --- fallback: ソースファイルからの自動検出（呼び出し側が未指定の場合のみ） ---

    def _resolve_source_classes(self, source: Path, struct: SourceStructure) -> List[str]:
        """ソースフォルダからクラス名リストを抽出する。
        import_folder(classes=[...]) で指定されていれば本メソッドは呼ばれない。
        """
        # 1. data.yaml の names
        candidates = [source / "data.yaml", source / "data.yml"]
        if struct.split:
            candidates.insert(0, source / struct.split / "data.yaml")

        for cyaml in candidates:
            if not cyaml.is_file():
                continue
            try:
                raw = yaml.safe_load(cyaml.read_text(encoding="utf-8")) or {}
                names = raw.get("names")
                if isinstance(names, dict):
                    sorted_items = sorted(names.items(), key=lambda x: int(x[0]))
                    return [str(v) for _, v in sorted_items]
                elif isinstance(names, list):
                    return [str(v) for v in names]
            except Exception:
                continue

        # 2. classes.txt
        txt_candidates = [
            source / "classes.txt",
            source / "labels" / "classes.txt",
        ]
        if struct.split:
            txt_candidates.insert(0, source / struct.split / "classes.txt")
            txt_candidates.insert(1, source / struct.split / "labels" / "classes.txt")

        for csrc in txt_candidates:
            if not csrc.is_file():
                continue
            try:
                raw = csrc.read_text(encoding="utf-8")
                names = [
                    line.strip()
                    for line in raw.splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                if names:
                    return names
            except Exception:
                continue

        return []