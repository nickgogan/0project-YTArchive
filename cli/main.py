"""YTArchive CLI - Command-line interface for YouTube video archiving."""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Rich console for styled output
console = Console()

# Service URLs
SERVICES = {
    "jobs": "http://localhost:8000",
    "metadata": "http://localhost:8001",
    "download": "http://localhost:8002",
    "storage": "http://localhost:8003",
    "logging": "http://localhost:8004",
}


class YTArchiveAPI:
    """API client for communicating with YTArchive services."""

    def __init__(self):
        self.client = httpx.AsyncClient()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def create_job(
        self, job_type: str, video_id: str, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new job."""
        payload = {"job_type": job_type, "video_id": video_id, "config": config or {}}

        response = await self.client.post(
            f"{SERVICES['jobs']}/api/v1/jobs", json=payload
        )
        response.raise_for_status()
        return response.json()

    async def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get job status."""
        response = await self.client.get(f"{SERVICES['jobs']}/api/v1/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    async def execute_job(self, job_id: str) -> Dict[str, Any]:
        """Execute a job."""
        response = await self.client.put(
            f"{SERVICES['jobs']}/api/v1/jobs/{job_id}/execute"
        )
        response.raise_for_status()
        return response.json()

    async def get_video_metadata(self, video_id: str) -> Dict[str, Any]:
        """Get video metadata."""
        response = await self.client.get(
            f"{SERVICES['metadata']}/api/v1/metadata/video/{video_id}"
        )
        response.raise_for_status()
        return response.json()

    async def start_download(
        self, video_id: str, quality: str = "1080p", output_path: str = "~/YTArchive"
    ) -> Dict[str, Any]:
        """Start video download."""
        payload = {
            "video_id": video_id,
            "quality": quality,
            "output_path": str(Path(output_path).expanduser()),
            "include_captions": True,
            "caption_languages": ["en"],
        }

        response = await self.client.post(
            f"{SERVICES['download']}/api/v1/download/video", json=payload
        )
        response.raise_for_status()
        return response.json()

    async def get_download_progress(self, task_id: str) -> Dict[str, Any]:
        """Get download progress."""
        response = await self.client.get(
            f"{SERVICES['download']}/api/v1/download/progress/{task_id}"
        )
        response.raise_for_status()
        return response.json()

    async def get_logs(
        self, service: Optional[str] = None, level: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get logs from logging service."""
        params = {}
        if service:
            params["service"] = service
        if level:
            params["level"] = level

        response = await self.client.get(f"{SERVICES['logging']}/logs", params=params)
        response.raise_for_status()
        return response.json()

    async def check_video_exists(self, video_id: str) -> Dict[str, Any]:
        """Check if video exists in storage."""
        response = await self.client.get(
            f"{SERVICES['storage']}/api/v1/storage/exists/{video_id}"
        )
        response.raise_for_status()
        return response.json()


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to readable format."""
    if not seconds:
        return "Unknown"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def format_file_size(bytes_count: Optional[int]) -> str:
    """Format file size in bytes to readable format."""
    if not bytes_count:
        return "Unknown"

    size = float(bytes_count)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@click.group()
@click.version_option(version="0.1.0", prog_name="ytarchive")
def cli():
    """YTArchive - YouTube Video Archiving System

    A comprehensive tool for downloading and archiving YouTube videos
    with metadata, thumbnails, and captions.
    """
    pass


@cli.command()
@click.argument("video_id")
@click.option(
    "--quality",
    "-q",
    default="1080p",
    type=click.Choice(["best", "1080p", "720p", "480p", "360p", "audio"]),
    help="Video quality to download",
)
@click.option(
    "--output", "-o", default="~/YTArchive", help="Output directory for downloads"
)
@click.option(
    "--metadata-only", is_flag=True, help="Only fetch metadata, do not download video"
)
def download(video_id: str, quality: str, output: str, metadata_only: bool):
    """Download a YouTube video with metadata and captions."""
    asyncio.run(_download_video(video_id, quality, output, metadata_only))


async def _download_video(
    video_id: str, quality: str, output: str, metadata_only: bool
):
    """Async implementation of video download."""
    async with YTArchiveAPI() as api:
        try:
            # Check if video already exists
            console.print(
                f"[blue]Checking if video {video_id} already exists...[/blue]"
            )
            exists_response = await api.check_video_exists(video_id)

            if exists_response.get("data", {}).get("exists"):
                console.print(
                    f"[yellow]Video {video_id} already exists in archive![/yellow]"
                )
                return

            # Get metadata first
            console.print(f"[blue]Fetching metadata for video {video_id}...[/blue]")

            with Progress(
                SpinnerColumn(), TextColumn("[progress.description]{task.description}")
            ) as progress:
                task = progress.add_task("Fetching metadata...", total=None)
                metadata_response = await api.get_video_metadata(video_id)
                progress.update(task, completed=True)

            if not metadata_response.get("success"):
                console.print(
                    f"[red]Failed to fetch metadata: {metadata_response.get('error', 'Unknown error')}[/red]"
                )
                return

            video_data = metadata_response["data"]

            # Display video information
            table = Table(title=f"Video Information: {video_id}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Title", video_data.get("title", "Unknown"))
            table.add_row("Channel", video_data.get("channel_title", "Unknown"))
            table.add_row("Duration", format_duration(video_data.get("duration")))
            table.add_row("View Count", f"{video_data.get('view_count', 0):,}")
            table.add_row("Upload Date", video_data.get("publish_date", "Unknown"))

            console.print(table)

            if metadata_only:
                console.print(
                    f"[green]Metadata fetched successfully for {video_id}![/green]"
                )
                return

            # Start download
            console.print(
                f"[blue]Starting download of {video_id} in {quality} quality...[/blue]"
            )

            download_response = await api.start_download(video_id, quality, output)

            if not download_response.get("success"):
                console.print(
                    f"[red]Failed to start download: {download_response.get('error', 'Unknown error')}[/red]"
                )
                return

            task_id = download_response["data"]["task_id"]
            console.print(f"[green]Download started! Task ID: {task_id}[/green]")

            # Monitor progress
            await _monitor_download_progress(api, task_id)

        except httpx.HTTPError as e:
            console.print(f"[red]HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


async def _monitor_download_progress(api: YTArchiveAPI, task_id: str):
    """Monitor download progress with a progress bar."""
    with Progress() as progress:
        download_task = progress.add_task("Downloading...", total=100)

        while True:
            try:
                progress_response = await api.get_download_progress(task_id)

                if not progress_response.get("success"):
                    console.print(
                        f"[red]Failed to get progress: {progress_response.get('error')}[/red]"
                    )
                    break

                progress_data = progress_response["data"]
                status = progress_data.get("status")
                percent = progress_data.get("progress_percent", 0)

                progress.update(download_task, completed=percent)

                if status == "completed":
                    console.print(
                        f"[green]Download completed! File: {progress_data.get('file_path')}[/green]"
                    )
                    break
                elif status == "failed":
                    console.print(
                        f"[red]Download failed: {progress_data.get('error')}[/red]"
                    )
                    break
                elif status == "cancelled":
                    console.print("[yellow]Download cancelled[/yellow]")
                    break

                await asyncio.sleep(2)  # Update every 2 seconds

            except Exception as e:
                console.print(f"[red]Error monitoring progress: {e}[/red]")
                break


@cli.command()
@click.argument("video_id")
@click.option("--json-output", is_flag=True, help="Output metadata as JSON")
def metadata(video_id: str, json_output: bool):
    """Fetch and display metadata for a YouTube video."""
    asyncio.run(_get_metadata(video_id, json_output))


async def _get_metadata(video_id: str, json_output: bool):
    """Async implementation of metadata fetching."""
    async with YTArchiveAPI() as api:
        try:
            console.print(f"[blue]Fetching metadata for video {video_id}...[/blue]")

            response = await api.get_video_metadata(video_id)

            if not response.get("success"):
                console.print(
                    f"[red]Failed to fetch metadata: {response.get('error', 'Unknown error')}[/red]"
                )
                return

            video_data = response["data"]

            if json_output:
                console.print(json.dumps(video_data, indent=2))
                return

            # Display formatted metadata
            panel_content = f"""
[bold]Title:[/bold] {video_data.get('title', 'N/A')}
[bold]Channel:[/bold] {video_data.get('channel_title', 'N/A')}
[bold]Duration:[/bold] {format_duration(video_data.get('duration'))}
[bold]Views:[/bold] {video_data.get('view_count', 0):,}
[bold]Likes:[/bold] {video_data.get('like_count', 0):,}
[bold]Upload Date:[/bold] {video_data.get('publish_date', 'N/A')}
[bold]Description:[/bold] {video_data.get('description', 'N/A')[:200]}...
"""

            console.print(
                Panel(
                    panel_content,
                    title=f"Video Metadata: {video_id}",
                    border_style="blue",
                )
            )

        except httpx.HTTPError as e:
            console.print(f"[red]HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.argument("job_id")
@click.option("--watch", "-w", is_flag=True, help="Watch job status continuously")
def status(job_id: str, watch: bool):
    """Check the status of a job."""
    asyncio.run(_get_job_status(job_id, watch))


async def _get_job_status(job_id: str, watch: bool):
    """Async implementation of job status checking."""
    async with YTArchiveAPI() as api:
        try:
            while True:
                response = await api.get_job(job_id)

                if not response.get("success"):
                    console.print(
                        f"[red]Failed to get job status: {response.get('error', 'Unknown error')}[/red]"
                    )
                    return

                job_data = response["data"]

                # Create status table
                table = Table(title=f"Job Status: {job_id}")
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="white")

                status_color = {
                    "PENDING": "yellow",
                    "RUNNING": "blue",
                    "COMPLETED": "green",
                    "FAILED": "red",
                }.get(job_data.get("status", "UNKNOWN"), "white")

                table.add_row(
                    "Status",
                    f"[{status_color}]{job_data.get('status', 'Unknown')}[/{status_color}]",
                )
                table.add_row("Type", job_data.get("job_type", "Unknown"))
                table.add_row("Video ID", job_data.get("video_id", "Unknown"))
                table.add_row("Created", job_data.get("created_at", "Unknown"))
                table.add_row("Started", job_data.get("started_at", "Not started"))
                table.add_row(
                    "Completed", job_data.get("completed_at", "Not completed")
                )

                if job_data.get("error"):
                    table.add_row("Error", f"[red]{job_data['error']}[/red]")

                console.clear()
                console.print(table)

                if not watch or job_data.get("status") in ["COMPLETED", "FAILED"]:
                    break

                await asyncio.sleep(3)  # Update every 3 seconds

        except httpx.HTTPError as e:
            console.print(f"[red]HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command()
@click.option("--service", "-s", help="Filter logs by service name")
@click.option(
    "--level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    help="Filter logs by level",
)
@click.option("--lines", "-n", default=50, help="Number of recent log lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output continuously")
def logs(service: Optional[str], level: Optional[str], lines: int, follow: bool):
    """View logs from the logging service."""
    asyncio.run(_view_logs(service, level, lines, follow))


async def _view_logs(
    service: Optional[str], level: Optional[str], lines: int, follow: bool
):
    """Async implementation of log viewing."""
    async with YTArchiveAPI() as api:
        try:
            while True:
                response = await api.get_logs(service, level)

                if not response.get("success"):
                    console.print(
                        f"[red]Failed to fetch logs: {response.get('error', 'Unknown error')}[/red]"
                    )
                    return

                logs_data = response.get("logs", [])

                if follow:
                    console.clear()

                # Display logs
                for log_entry in logs_data[-lines:]:
                    timestamp = log_entry.get("timestamp", "")
                    log_level = log_entry.get("level", "INFO")
                    log_service = log_entry.get("service", "unknown")
                    message = log_entry.get("message", "")

                    level_color = {
                        "DEBUG": "dim white",
                        "INFO": "blue",
                        "WARNING": "yellow",
                        "ERROR": "red",
                        "CRITICAL": "bold red",
                    }.get(log_level, "white")

                    console.print(
                        f"[dim]{timestamp}[/dim] [{level_color}]{log_level:8}[/{level_color}] [cyan]{log_service:12}[/cyan] {message}"
                    )

                if not follow:
                    break

                await asyncio.sleep(5)  # Update every 5 seconds

        except httpx.HTTPError as e:
            console.print(f"[red]HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    cli()
