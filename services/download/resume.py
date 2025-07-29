"""
Manages the state of resumable downloads, allowing the system to recover
from interruptions and continue downloading partial files.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class DownloadState(BaseModel):
    """Represents the state of a single download task."""

    task_id: str
    video_id: str
    video_url: str
    output_path: str
    quality: str
    downloaded_bytes: int = 0
    total_bytes: Optional[int] = None
    partial_file_path: Optional[str] = None
    resume_supported: bool = True
    resume_attempts: int = 0
    max_resume_attempts: int = 3
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_resume_attempt: Optional[datetime] = None


class DownloadStateManager:
    """Manages the persistence of download states."""

    def __init__(self, state_dir: str = "logs/download_state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    async def save_state(self, state: DownloadState) -> None:
        """Saves the download state to a file."""
        state.updated_at = datetime.now(timezone.utc)
        state_file = self.state_dir / f"{state.task_id}.json"
        with open(state_file, "w") as f:
            json.dump(state.model_dump(), f, indent=4, default=str)

    async def load_state(self, task_id: str) -> Optional[DownloadState]:
        """Loads a download state from a file."""
        state_file = self.state_dir / f"{task_id}.json"
        if not state_file.exists():
            return None
        with open(state_file, "r") as f:
            data = json.load(f)
            return DownloadState(**data)

    async def delete_state(self, task_id: str) -> None:
        """Deletes a download state file."""
        state_file = self.state_dir / f"{task_id}.json"
        if state_file.exists():
            os.remove(state_file)

    async def list_resumable_downloads(self) -> List[DownloadState]:
        """Lists all persisted download states that could be resumed."""
        resumable_states = []
        for state_file in self.state_dir.glob("*.json"):
            task_id = state_file.stem
            state = await self.load_state(task_id)
            if state and state.resume_supported:
                resumable_states.append(state)
        return resumable_states


class PartialDownloadResumer:
    """Handles the logic for resuming partial downloads."""

    def __init__(self, state_manager: DownloadStateManager):
        self.state_manager = state_manager

    def check_partial_file(self, output_path: str, video_id: str) -> Optional[str]:
        """Checks for existing partial download files."""
        output_dir = Path(output_path)
        # Common partial file extensions used by yt-dlp
        for extension in [".part", ".ytdl"]:
            for partial_file in output_dir.glob(f"{video_id}*{extension}"):
                if partial_file.exists():
                    return str(partial_file)
        return None

    async def validate_resume_possibility(
        self, state: DownloadState
    ) -> Tuple[bool, str]:
        """Validates if a download can be resumed based on its state."""
        if not state.resume_supported:
            return False, "Resume is not supported for this download."
        if state.resume_attempts >= state.max_resume_attempts:
            return (
                False,
                f"Maximum resume attempts ({state.max_resume_attempts}) reached.",
            )
        if not state.partial_file_path or not Path(state.partial_file_path).exists():
            return False, "No partial file found to resume from."
        return True, "Download can be resumed."
