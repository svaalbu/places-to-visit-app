from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "generating", "repairing", "ready", "failed"]


class BBoxMM(BaseModel):
    x: float
    y: float
    z: float


class WarningItem(BaseModel):
    code: str
    message: str


class JobCreateResponse(BaseModel):
    id: str
    status: JobStatus
    provider: str
    target_size_mm: float


class JobStatusResponse(BaseModel):
    id: str
    status: JobStatus
    provider: str
    target_size_mm: float
    prepared_size_mm: Optional[float] = None
    error: Optional[str] = None
    warnings: List[WarningItem] = Field(default_factory=list)
    bbox_mm: Optional[BBoxMM] = None
    min_extent_mm: Optional[float] = None
    is_watertight: Optional[bool] = None
    triangle_count: Optional[int] = None
    preview_available: bool = False
    export_3mf_available: bool = False
    export_stl_available: bool = False
    studio_note: str = (
        "Open the 3MF in Bambu Studio on a computer. Set printer to "
        "Bambu Lab P2S 0.4 nozzle, PLA, 0.20 mm Standard. Bambu Handy cannot slice this file."
    )
