"""エントリーポイント。YoloForCへのパスを解決し、GUIを起動する。"""
import sys
from pathlib import Path

# YoloForCライブラリへのパスを追加（並列配置前提）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from .app import YoloForCApp


def main():
    app = YoloForCApp(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()