from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path

@dataclass
class BBox:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float

@dataclass
class ImageAnnotation:
    filename: str          # 拡張子付き
    width: int
    height: int
    bboxes: List[BBox] = field(default_factory=list)

@dataclass
class ImportResult:
    uuid: str
    dataset_name: str
    image_count: int
    label_count: int
    warnings: List[str] = field(default_factory=list)

@dataclass
class UuidRecord:
    uuid: str
    path: Path
    image_count: int
    label_count: int
    status: str
    annotator: Optional[str]
    tags: List[str] = field(default_factory=list)

@dataclass
class ValidationIssue:
    level: str          # "error" | "warning"
    uuid: str           # 全体エラーなら "__dataset__"
    message: str

@dataclass
class DatasetValidationReport:
    dataset_name: str
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


@dataclass
class DatasetMeta:
    dataset_name: str
    date_captured: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    classes: List[str] = field(default_factory=list)
    total_images: int = 0