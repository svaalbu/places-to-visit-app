from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    id: str
    status: str
    provider: str
    target_size_mm: float
    created_at: str
    updated_at: str
    error: Optional[str] = None
    warnings: List[Dict[str, str]] = field(default_factory=list)
    bbox_mm: Optional[Dict[str, float]] = None
    min_extent_mm: Optional[float] = None
    is_watertight: Optional[bool] = None
    triangle_count: Optional[int] = None
    prepared_size_mm: Optional[float] = None
    y_up_source: bool = False
    source_ext: str = "glb"

    def to_public(self) -> Dict[str, Any]:
        ready = self.status == "ready"
        return {
            "id": self.id,
            "status": self.status,
            "provider": self.provider,
            "target_size_mm": self.target_size_mm,
            "prepared_size_mm": self.prepared_size_mm,
            "error": self.error,
            "warnings": self.warnings,
            "bbox_mm": self.bbox_mm,
            "min_extent_mm": self.min_extent_mm,
            "is_watertight": self.is_watertight,
            "triangle_count": self.triangle_count,
            "preview_available": ready,
            "export_3mf_available": ready,
            "export_stl_available": ready,
        }


class JobStore:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or settings.job_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def job_dir(self, job_id: str) -> Path:
        path = self.root / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _meta_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job.json"

    def save(self, record: JobRecord) -> None:
        record.updated_at = _now()
        path = self._meta_path(record.id)
        with self._lock:
            path.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")

    def get(self, job_id: str) -> Optional[JobRecord]:
        path = self._meta_path(job_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return JobRecord(**data)

    def update(self, job_id: str, **fields: Any) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            raise KeyError(job_id)
        for key, value in fields.items():
            setattr(record, key, value)
        self.save(record)
        return record

    def write_bytes(self, job_id: str, name: str, data: bytes) -> Path:
        path = self.job_dir(job_id) / name
        path.write_bytes(data)
        return path

    def read_bytes(self, job_id: str, name: str) -> Optional[bytes]:
        path = self.job_dir(job_id) / name
        if not path.exists():
            return None
        return path.read_bytes()


store = JobStore()
