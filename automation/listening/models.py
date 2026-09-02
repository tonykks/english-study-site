from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Segment:
    segment_id: str
    start: float
    end: float
    text_en: str
    source: str = "caption"

    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class VideoMeta:
    video_id: str
    title: str
    channel: str
    duration: float
    video_url: str


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    status: str  # PASS, BLOCKED, DRY_RUN
    message: str
    folder: str = ""
    video_id: str = ""
    staging_dir: str = ""
