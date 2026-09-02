from __future__ import annotations

import shutil
from pathlib import Path

from automation.listening.publish.stage import clear_staging


class PublishRollback:
    def __init__(self) -> None:
        self.index_backup: str | None = None
        self.index_path: Path | None = None
        self.published_dir: Path | None = None
        self.video_id: str = ""

    def backup_index(self, index_path: Path) -> None:
        self.index_path = index_path
        self.index_backup = index_path.read_text(encoding="utf-8")

    def record_publish(self, target_dir: Path, video_id: str) -> None:
        self.published_dir = target_dir
        self.video_id = video_id

    def rollback(self) -> None:
        if self.index_path and self.index_backup is not None:
            self.index_path.write_text(self.index_backup, encoding="utf-8")
        if self.published_dir and self.published_dir.exists():
            shutil.rmtree(self.published_dir, ignore_errors=True)
        if self.video_id:
            clear_staging(self.video_id)
