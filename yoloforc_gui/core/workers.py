# yoloforc_gui/core/workers.py
from PySide6.QtCore import QThread, Signal
from typing import Optional, List, Dict, Any
from pathlib import Path

class ImportWorker(QThread):
    # シグナルの定義
    progressChanged = Signal(int, int, str)  # current, total, message
    formatDetected = Signal(str)             # 検知したフォーマット
    finishedSuccessfully = Signal(object)    # 成功時 (ImportResult等)
    errorOccurred = Signal(str)              # エラー時

    def __init__(self, bridge, dataset_name, source, classes, note, annotator, tags):
        super().__init__()
        self.bridge = bridge
        self.dataset_name = dataset_name
        self.source = source
        self.classes = classes
        self.note = note
        self.annotator = annotator
        self.tags = tags

    def run(self):
        try:
            # 内部でバックエンドの progress_callback に繋ぎ込むためのコールバック関数
            def on_progress(current: int, total: int, msg: str):
                self.progressChanged.emit(current, total, msg)
                if "形式を検知" in msg:
                    # メッセージからフォーマット文字列を抽出する等の簡易処理
                    fmt = msg.split(":")[-1].split("。")[0].strip()
                    self.formatDetected.emit(fmt)

            # Bridgeに新設する非同期用インポートメソッドを呼ぶ
            result = self.bridge.import_folder_async(
                dataset_name=self.dataset_name,
                source=self.source,
                classes=self.classes,
                note=self.note,
                annotator=self.annotator,
                tags=self.tags,
                progress_callback=on_progress
            )
            self.finishedSuccessfully.emit(result)
            
        except Exception as e:
            self.errorOccurred.emit(str(e))