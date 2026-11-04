from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple
from ...storage.proxy import StorageProxy
from ...validator.structure import SourceStructure

class BaseImportStrategy(ABC):
    def __init__(self, storage: StorageProxy, dataset_classes: List[str]):
        self.storage = storage
        self.dataset_classes = dataset_classes

    @abstractmethod
    def process(self, uid: str, source: Path, struct: SourceStructure) -> Tuple[int, int, List[str]]:
        """
        画像をコピーし、ラベルを YOLO TXT形式に変換/配置する。
        Returns:
            (image_count, label_count, warnings)
        """
        pass