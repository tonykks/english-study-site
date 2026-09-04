from __future__ import annotations

import shutil
from pathlib import Path

from automation.listening.config import LISTENING_ROOT, level_folder
from automation.listening.generate.update_index import append_listening_card
from automation.listening.publish.rollback import PublishRollback
from automation.listening.publish.stage import clear_staging


def publish_to_repo(
    stage_dir: Path,
    level: int,
    content_id: str,
    card: dict,
    dry_run: bool = False,
) -> str:
    target_dir = LISTENING_ROOT / level_folder(level) / content_id
    index_path = LISTENING_ROOT / "index.html"
    rollback = PublishRollback()

    if target_dir.exists():
        raise ValueError(f"Target folder already exists: {target_dir}")

    if dry_run:
        msg = append_listening_card(index_path, card, dry_run=True)
        return f"dry-run: would publish to {target_dir}; index: {msg}"

    rollback.backup_index(index_path)
    try:
        shutil.copytree(
            stage_dir,
            target_dir,
            ignore=shutil.ignore_patterns("manifest.json"),
        )
        rollback.record_publish(target_dir, card.get("video_id", ""))
        result = append_listening_card(index_path, card, dry_run=False)
        clear_staging(card.get("video_id", ""))
        return f"published to {target_dir}; index: {result}"
    except Exception:
        rollback.rollback()
        raise
