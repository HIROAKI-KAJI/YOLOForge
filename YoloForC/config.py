import os
from pathlib import Path
from typing import Optional

from .exceptions import YFCConfigError
from .storage.initializer import RootInitializer


class Config:
    """YoloForC の保存ルート設定を一元管理。
    未初期化のパスは strict モードで拒否し、誤ったディレクトリ指定を防ぐ。
    """
    def __init__(
        self,
        root_override: Optional[Path] = None,
        strict: bool = True,        # True で「未初期化パス」を拒否
    ):
        # 1. 候補パスの解決（優先順位: 引数 > 環境変数）
        if root_override is not None:
            candidate = Path(root_override).resolve()
        elif "YFC_ROOT" in os.environ:
            candidate = Path(os.environ["YFC_ROOT"]).resolve()
        else:
            raise YFCConfigError(
                "YoloForC ルートパスが未設定です。以下のいずれかを実行してください:\n",
                "  1) YoloForC.init_root('/path/to/root') で初期化\n",
                "  2) YoloForC(root='/path/to/root') で明示指定\n",
                "  3) 環境変数 YFC_ROOT を設定"
            )

        # 2. 存在チェック
        if not candidate.exists():
            raise YFCConfigError(
                f"指定されたパスが存在しません: {candidate}\n"
                f"存在しないパスは利用できません。init_root() を使えば自動作成されます。"
            )

        self.root = candidate

        # 3. 初期化済みチェック（strictモード時）
        if strict and not RootInitializer.is_initialized(self.root):
            raise YFCConfigError(
                f"{self.root} は YoloForC 管理下にありません（未初期化）。\n"
                f"初回のみ以下を実行してください:\n"
                f"  YoloForC.init_root('{self.root}')"
            )

    def dataset_dir(self, dataset_name: str) -> Path:
        """dataset_name に該当する保存先ディレクトリパスを返す。
        dataset_name は英数字、アンダースコア、ハイフンのみ許可（フォルダ名安全）。
        """
        if not dataset_name:
            raise YFCConfigError("dataset_name が空です")

        allowed = dataset_name.replace("_", "").replace("-", "")
        if not allowed.isalnum():
            raise YFCConfigError(
                f"不正な dataset_name '{dataset_name}'。英数字/アンダースコア/ハイフンのみ使用可能です。"
            )

        return self.root / dataset_name