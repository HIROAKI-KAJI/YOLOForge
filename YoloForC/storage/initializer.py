from pathlib import Path
from typing import Optional
from datetime import datetime

import yaml

from ..exceptions import YFCStorageError


class RootInitializer:
    """YoloForC 管理ルートの初期化・検証を担当。
    ルート直下にマーカーファイル `.yoloforc_root` を配置し、
    「このディレクトリは YoloForC によって初期化された正規の保存先」であることを示す。
    """
    MARKER_NAME = ".yoloforc_root"

    @classmethod
    def initialize(cls, path: Path, comment: Optional[str] = None) -> Path:
        """指定パスを YoloForC ルートとして初期化する。
        ディレクトリが存在しなければ作成し、マーカーファイルを書き込む。
        既に初期化済みでも再実行は可能（冪等）。
        """
        root = Path(path).resolve()

        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise YFCStorageError(f"ルートディレクトリの作成に失敗しました: {root}\n→ {e}")

        marker = root / cls.MARKER_NAME
        content = {
            "initialized_at": datetime.now().isoformat(),
            "version": 1,                    # 将来のフォーマット変更に備えたバージョン
            "comment": comment or "",
        }

        try:
            marker.write_text(
                yaml.safe_dump(content, allow_unicode=True, sort_keys=False),
                encoding="utf-8"
            )
        except OSError as e:
            raise YFCStorageError(f"マーカーファイルの書き込みに失敗しました: {marker}\n→ {e}")

        return root

    @classmethod
    def is_initialized(cls, path: Path) -> bool:
        """指定パスが既に YoloForC ルートとして初期化されているかを確認。"""
        return (Path(path) / cls.MARKER_NAME).is_file()

    @classmethod
    def ensure_initialized(cls, path: Path):
        """未初期化なら例外を投げる（Config などから使う）。"""
        if not cls.is_initialized(path):
            raise YFCStorageError(
                f"{path} は YoloForC ルートとして初期化されていません。\n"
                f"以下を実行してください: YoloForC.init_root('{path}')"
            )