"""YTArchive CLI - Command-line interface for YouTube video archiving."""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional

import click
import httpx
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns


def safe_error_message(e) -> str:
    """Safely convert an exception to a string, handling coroutine objects."""
    import inspect
    import asyncio

    # Handle coroutine objects specifically
    if inspect.iscoroutine(e):
        # Close the coroutine to prevent the warning
        try:
            e.close()
        except Exception:
            pass
        return f"Coroutine error: {getattr(e, '__name__', 'unknown')}"

    # Handle other awaitable objects
    if hasattr(e, "__await__"):
        return f"Awaitable error: {type(e).__name__}"

    # Handle Task objects
    if isinstance(e, asyncio.Task):
        return f"Task error: {e}"

    # For regular exceptions, convert to string safely
    try:
        return str(e)
    except Exception:
        return f"Error converting exception to string: {type(e).__name__}"


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

    async def get_playlist_metadata(self, playlist_id: str) -> Dict[str, Any]:
        """Get playlist metadata."""
        response = await self.client.get(
            f"{SERVICES['metadata']}/api/v1/metadata/playlist/{playlist_id}"
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
            console.print(f"[red]Error: {safe_error_message(e)}[/red]")


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
            console.print(f"[red]Error: {safe_error_message(e)}[/red]")


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
            console.print(f"[red]Error: {safe_error_message(e)}[/red]")


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


@cli.group()
def recovery() -> None:
    """Manage recovery plans for failed and unavailable videos."""
    pass


@recovery.command()
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def list(json_output: bool) -> None:
    """List all recovery plans."""
    asyncio.run(_list_recovery_plans(json_output))


@recovery.command()
@click.argument("plan_id")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def show(plan_id: str, json_output: bool) -> None:
    """Show details of a specific recovery plan."""
    asyncio.run(_show_recovery_plan(plan_id, json_output))


@recovery.command()
@click.option(
    "--unavailable-videos",
    "unavailable_videos_file",
    help="JSON file containing unavailable videos data",
    type=click.Path(exists=True),
)
@click.option(
    "--failed-downloads",
    "failed_downloads_file",
    help="JSON file containing failed downloads data",
    type=click.Path(exists=True),
)
def create(
    unavailable_videos_file: Optional[str], failed_downloads_file: Optional[str]
) -> None:
    """Create a new recovery plan from failed/unavailable videos."""
    asyncio.run(
        _create_recovery_plan(
            unavailable_videos_file=unavailable_videos_file,
            failed_downloads_file=failed_downloads_file,
        )
    )


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
            console.print(f"[red]Error: {safe_error_message(e)}[/red]")


async def _list_recovery_plans(json_output: bool):
    """Async implementation of recovery plan listing."""
    async with YTArchiveAPI() as api:
        try:
            # Get storage stats to find work plans directory
            stats_response = await api.client.get(
                f"{SERVICES['storage']}/api/v1/storage/stats"
            )
            stats_response.raise_for_status()

            # List work plan files from the work plans directory
            work_plans_dir = Path("~/.ytarchive/data/work_plans").expanduser()

            if not work_plans_dir.exists():
                if json_output:
                    console.print(json.dumps({"work_plans": []}))
                else:
                    console.print("[yellow]No work plans directory found.[/yellow]")
                return

            plan_files = list(work_plans_dir.glob("*_plan.json"))

            if not plan_files:
                if json_output:
                    console.print(json.dumps({"work_plans": []}))
                else:
                    console.print("[yellow]No work plans found.[/yellow]")
                return

            work_plans = []
            for plan_file in sorted(plan_files):
                try:
                    with open(plan_file) as f:
                        plan_data = json.load(f)

                    plan_info = {
                        "plan_id": plan_data.get(
                            "plan_id", plan_file.stem.replace("_plan", "")
                        ),
                        "created_at": plan_data.get("created_at", "Unknown"),
                        "total_videos": plan_data.get("total_videos", 0),
                        "unavailable_count": plan_data.get("unavailable_count", 0),
                        "failed_count": plan_data.get("failed_count", 0),
                        "path": str(plan_file),
                    }
                    work_plans.append(plan_info)
                except Exception as e:
                    console.print(f"[red]Error reading {plan_file}: {e}[/red]")

            if json_output:
                console.print(json.dumps({"work_plans": work_plans}, indent=2))
            else:
                if work_plans:
                    table = Table(title="Work Plans")
                    table.add_column("Plan ID", style="cyan")
                    table.add_column("Created", style="green")
                    table.add_column("Total Videos", justify="right")
                    table.add_column("Unavailable", justify="right", style="yellow")
                    table.add_column("Failed", justify="right", style="red")

                    for plan in work_plans:
                        table.add_row(
                            plan["plan_id"],
                            plan["created_at"],
                            str(plan["total_videos"]),
                            str(plan["unavailable_count"]),
                            str(plan["failed_count"]),
                        )

                    console.print(table)
                else:
                    console.print("[yellow]No work plans found.[/yellow]")

        except httpx.HTTPError as e:
            console.print(f"[red]HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {safe_error_message(e)}[/red]")


async def _show_recovery_plan(plan_id: str, json_output: bool):
    """Async implementation of recovery plan display."""
    try:
        work_plans_dir = Path("~/.ytarchive/data/work_plans").expanduser()
        plan_file = work_plans_dir / f"{plan_id}_plan.json"

        if not plan_file.exists():
            console.print(f"[red]Work plan '{plan_id}' not found.[/red]")
            return

        with open(plan_file) as f:
            plan_data = json.load(f)

        if json_output:
            console.print(json.dumps(plan_data, indent=2))
        else:
            # Display work plan details
            panel = Panel(
                f"Plan ID: {plan_data.get('plan_id', plan_id)}\n"
                f"Created: {plan_data.get('created_at', 'Unknown')}\n"
                f"Total Videos: {plan_data.get('total_videos', 0)}\n"
                f"Unavailable: {plan_data.get('unavailable_count', 0)}\n"
                f"Failed: {plan_data.get('failed_count', 0)}\n"
                f"Notes: {plan_data.get('notes', 'No notes')}",
                title=f"Work Plan: {plan_id}",
                border_style="blue",
            )
            console.print(panel)

            # Show unavailable videos
            if plan_data.get("unavailable_videos"):
                console.print("\n[yellow]Unavailable Videos:[/yellow]")
                unavailable_table = Table()
                unavailable_table.add_column("Video ID", style="cyan")
                unavailable_table.add_column("Title", style="white")
                unavailable_table.add_column("Reason", style="yellow")
                unavailable_table.add_column("Detected At", style="green")

                for video in plan_data["unavailable_videos"]:
                    unavailable_table.add_row(
                        video.get("video_id", "N/A"),
                        video.get("title", "N/A"),
                        video.get("reason", "N/A"),
                        video.get("detected_at", "N/A"),
                    )
                console.print(unavailable_table)

            # Show failed downloads
            if plan_data.get("failed_downloads"):
                console.print("\n[red]Failed Downloads:[/red]")
                failed_table = Table()
                failed_table.add_column("Video ID", style="cyan")
                failed_table.add_column("Title", style="white")
                failed_table.add_column("Attempts", justify="right", style="red")
                failed_table.add_column("Last Attempt", style="green")

                for video in plan_data["failed_downloads"]:
                    failed_table.add_row(
                        video.get("video_id", "N/A"),
                        video.get("title", "N/A"),
                        str(video.get("attempts", 0)),
                        video.get("last_attempt", "N/A"),
                    )
                console.print(failed_table)

    except FileNotFoundError:
        console.print(f"[red]Work plan '{plan_id}' not found.[/red]")
    except json.JSONDecodeError:
        console.print(f"[red]Invalid JSON in work plan file '{plan_id}'.[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


async def _create_recovery_plan(
    unavailable_videos_file: Optional[str], failed_downloads_file: Optional[str]
):
    """Async implementation of recovery plan creation."""
    async with YTArchiveAPI() as api:
        try:
            unavailable_videos = []
            failed_downloads = []

            # Load unavailable videos data
            if unavailable_videos_file:
                with open(unavailable_videos_file) as f:
                    unavailable_data = json.load(f)
                    if isinstance(unavailable_data, list):
                        unavailable_videos = unavailable_data
                    elif (
                        isinstance(unavailable_data, dict)
                        and "unavailable_videos" in unavailable_data
                    ):
                        unavailable_videos = unavailable_data["unavailable_videos"]

            # Load failed downloads data
            if failed_downloads_file:
                with open(failed_downloads_file) as f:
                    failed_data = json.load(f)
                    if isinstance(failed_data, list):
                        failed_downloads = failed_data
                    elif (
                        isinstance(failed_data, dict)
                        and "failed_downloads" in failed_data
                    ):
                        failed_downloads = failed_data["failed_downloads"]

            if not unavailable_videos and not failed_downloads:
                console.print(
                    "[yellow]No unavailable videos or failed downloads provided. Please specify at least one JSON file.[/yellow]"
                )
                return

            # Create work plan via Storage Service API
            payload = {
                "unavailable_videos": unavailable_videos,
                "failed_downloads": failed_downloads,
            }

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Creating work plan...", total=None)

                response = await api.client.post(
                    f"{SERVICES['storage']}/api/v1/storage/work-plan", json=payload
                )
                response.raise_for_status()
                result = response.json()

                progress.remove_task(task)

            if result.get("success"):
                data = result.get("data", {})
                console.print("[green]Work plan created successfully![/green]")
                console.print(f"Plan ID: {data.get('plan_id')}")
                console.print(f"Path: {data.get('path')}")
                console.print(f"Total Videos: {data.get('total_videos')}")
                console.print(f"Unavailable: {data.get('unavailable_count')}")
                console.print(f"Failed: {data.get('failed_count')}")
            else:
                console.print(
                    f"[red]Failed to create work plan: {result.get('error', 'Unknown error')}[/red]"
                )

        except FileNotFoundError as e:
            console.print(f"[red]File not found: {e}[/red]")
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON format: {e}[/red]")
        except httpx.HTTPError as e:
            console.print(f"[red]HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {safe_error_message(e)}[/red]")


@cli.group()
def playlist():
    """Manage playlist downloads and operations."""
    pass


@playlist.command("download")
@click.argument("playlist_url")
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
@click.option("--max-concurrent", "-c", default=3, help="Maximum concurrent downloads")
@click.option(
    "--metadata-only", is_flag=True, help="Download only metadata (no video files)"
)
def playlist_download(
    playlist_url: str,
    quality: str,
    output: str,
    max_concurrent: int,
    metadata_only: bool,
):
    """Download all videos from a YouTube playlist."""
    asyncio.run(
        _download_playlist(playlist_url, quality, output, max_concurrent, metadata_only)
    )


@playlist.command("info")
@click.argument("playlist_url")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def playlist_info(playlist_url: str, json_output: bool):
    """Get information about a YouTube playlist."""
    asyncio.run(_get_playlist_info(playlist_url, json_output))


@playlist.command("status")
@click.argument("job_id")
@click.option("--watch", "-w", is_flag=True, help="Watch for status changes")
def playlist_status(job_id: str, watch: bool):
    """Check the status of a playlist download job."""
    asyncio.run(_get_playlist_status(job_id, watch))


async def _download_playlist(
    playlist_url: str,
    quality: str,
    output: str,
    max_concurrent: int,
    metadata_only: bool,
):
    """Async implementation of playlist download."""
    async with YTArchiveAPI() as api:
        try:
            console.print("[blue]🎵 Starting playlist download...[/blue]")
            console.print(f"[blue]📝 Playlist URL: {playlist_url}[/blue]")
            console.print(f"[blue]🎬 Quality: {quality}[/blue]")
            console.print(f"[blue]📂 Output: {output}[/blue]")
            console.print(f"[blue]⚡ Max concurrent: {max_concurrent}[/blue]")

            # Extract playlist ID from URL
            playlist_id = _extract_playlist_id(playlist_url)
            if not playlist_id:
                console.print(f"[red]❌ Invalid playlist URL: {playlist_url}[/red]")
                return

            # Get playlist metadata
            console.print("[yellow]📊 Fetching playlist information...[/yellow]")
            playlist_metadata = await api.get_playlist_metadata(playlist_id)

            if not playlist_metadata:
                console.print("[red]❌ Failed to fetch playlist metadata[/red]")
                return

            # Display playlist info
            console.print(
                Panel(
                    f"[bold green]📝 {playlist_metadata['title']}[/bold green]\n"
                    f"[blue]👤 Channel: {playlist_metadata.get('channel_title', 'Unknown')}[/blue]\n"
                    f"[blue]🎬 Videos: {len(playlist_metadata['videos'])}[/blue]\n"
                    f"[blue]📝 Description: {playlist_metadata.get('description', 'No description')[:100]}...[/blue]",
                    title="[bold blue]🎵 Playlist Information[/bold blue]",
                )
            )

            # Create playlist download job
            job_data = {
                "job_type": "PLAYLIST_DOWNLOAD",
                "playlist_id": playlist_id,
                "config": {
                    "quality": quality,
                    "output_path": output,
                    "max_concurrent": max_concurrent,
                    "metadata_only": metadata_only,
                    "videos": playlist_metadata["videos"],
                },
            }

            job_response = await api.create_job(
                job_type="PLAYLIST_DOWNLOAD",
                video_id=playlist_id,
                config=job_data["config"],
            )

            job_id = job_response["job_id"]
            console.print(f"[green]✅ Playlist download job created: {job_id}[/green]")

            # Start job execution
            await api.execute_job(job_id)
            console.print("[green]🚀 Playlist download started![/green]")

            # Monitor progress
            await _monitor_playlist_progress(
                api, job_id, len(playlist_metadata["videos"])
            )

        except httpx.HTTPError as e:
            console.print(f"[red]❌ HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error: {safe_error_message(e)}[/red]")


async def _get_playlist_info(playlist_url: str, json_output: bool):
    """Async implementation of playlist info fetching."""
    async with YTArchiveAPI() as api:
        try:
            # Extract playlist ID from URL
            playlist_id = _extract_playlist_id(playlist_url)
            if not playlist_id:
                console.print(f"[red]❌ Invalid playlist URL: {playlist_url}[/red]")
                return

            # Get playlist metadata
            console.print("[yellow]📊 Fetching playlist information...[/yellow]")
            playlist_metadata = await api.get_playlist_metadata(playlist_id)

            if not playlist_metadata:
                console.print("[red]❌ Failed to fetch playlist metadata[/red]")
                return

            if json_output:
                console.print(json.dumps(playlist_metadata, indent=2))
            else:
                # Display playlist info in rich format
                console.print(
                    Panel(
                        f"[bold green]📝 {playlist_metadata['title']}[/bold green]\n"
                        f"[blue]👤 Channel: {playlist_metadata.get('channel_title', 'Unknown')}[/blue]\n"
                        f"[blue]🎬 Videos: {len(playlist_metadata['videos'])}[/blue]\n"
                        f"[blue]📅 Created: {playlist_metadata.get('created_date', 'Unknown')}[/blue]\n"
                        f"[blue]📝 Description: {playlist_metadata.get('description', 'No description')}[/blue]",
                        title="[bold blue]🎵 Playlist Information[/bold blue]",
                    )
                )

                # Display video list
                if playlist_metadata["videos"]:
                    table = Table(title="📼 Playlist Videos")
                    table.add_column("#", style="cyan")
                    table.add_column("Title", style="green")
                    table.add_column("Duration", style="blue")
                    table.add_column("Status", style="yellow")

                    for i, video in enumerate(playlist_metadata["videos"][:10]):
                        table.add_row(
                            str(i + 1),
                            video.get("title", "Unknown"),
                            format_duration(video.get("duration_seconds")),
                            video.get("availability", "Available"),
                        )

                    if len(playlist_metadata["videos"]) > 10:
                        table.add_row(
                            "...",
                            f"... and {len(playlist_metadata['videos']) - 10} more",
                            "",
                            "",
                        )

                    console.print(table)

        except httpx.HTTPError as e:
            console.print(f"[red]❌ HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error: {safe_error_message(e)}[/red]")


async def _get_playlist_status(job_id: str, watch: bool):
    """Async implementation of playlist status checking."""
    async with YTArchiveAPI() as api:
        try:
            if watch:
                console.print(
                    "[blue]👀 Watching playlist job status (Ctrl+C to exit)...[/blue]"
                )

                while True:
                    job_status = await api.get_job(job_id)

                    # Display current status
                    _display_playlist_job_status(job_status)

                    if job_status["status"] in ["completed", "failed", "cancelled"]:
                        break

                    await asyncio.sleep(2)
            else:
                job_status = await api.get_job(job_id)
                _display_playlist_job_status(job_status)

        except KeyboardInterrupt:
            console.print("\n[yellow]⏹️ Stopped watching job status[/yellow]")
        except httpx.HTTPError as e:
            console.print(f"[red]❌ HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error: {safe_error_message(e)}[/red]")


def _extract_playlist_id(playlist_url: str) -> Optional[str]:
    """Extract playlist ID from YouTube playlist URL."""
    import re

    # Match playlist URL patterns
    patterns = [
        r"[&?]list=([^&]+)",  # Standard playlist parameter
        r"/playlist\?list=([^&]+)",  # Direct playlist URL
    ]

    for pattern in patterns:
        match = re.search(pattern, playlist_url)
        if match:
            return match.group(1)

    return None


def _display_playlist_job_status(job_status: Dict[str, Any]):
    """Display playlist job status in rich format."""
    status = job_status["status"]
    progress = job_status.get("progress", {})

    # Status color mapping
    status_colors = {
        "pending": "yellow",
        "running": "blue",
        "completed": "green",
        "failed": "red",
        "cancelled": "orange",
    }

    status_color = status_colors.get(status, "white")

    # Create status panel
    status_info = (
        f"[bold {status_color}]📋 Status: {status.upper()}[/bold {status_color}]\n"
        f"[blue]🆔 Job ID: {job_status['job_id']}[/blue]\n"
        f"[blue]🎵 Type: {job_status['job_type']}[/blue]\n"
        f"[blue]📅 Created: {job_status['created_at']}[/blue]"
    )

    if progress:
        completed = progress.get("completed_videos", 0)
        total = progress.get("total_videos", 0)
        failed = progress.get("failed_videos", 0)

        if total > 0:
            percentage = (completed / total) * 100
            status_info += (
                f"\n[green]✅ Progress: {completed}/{total} ({percentage:.1f}%)[/green]"
            )
            if failed > 0:
                status_info += f"\n[red]❌ Failed: {failed}[/red]"

    console.print(
        Panel(status_info, title="[bold blue]🎵 Playlist Job Status[/bold blue]")
    )


async def _monitor_playlist_progress(api: YTArchiveAPI, job_id: str, total_videos: int):
    """Monitor playlist download progress with rich real-time updates."""
    from datetime import datetime, timezone

    with Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
        expand=True,
    ) as progress:
        # Initialize progress task
        main_task = progress.add_task(
            "Initializing playlist processing...",
            total=total_videos if total_videos > 0 else 100,
        )

        last_update_time = datetime.now(timezone.utc)

        while True:
            try:
                job_status = await api.get_job(job_id)
                job_progress = job_status.get("progress", {})
                current_time = datetime.now(timezone.utc)

                # Extract rich progress data
                phase = job_progress.get("phase", "unknown")
                completed_videos = job_progress.get("completed_videos", 0)
                failed_videos = job_progress.get("failed_videos", 0)
                total_playlists = job_progress.get("total_playlists", 1)
                processed_playlists = job_progress.get("processed_playlists", 0)
                current_playlist = job_progress.get("current_playlist", {})
                current_video = job_progress.get("current_video", {})
                download_speed = job_progress.get("download_speed", 0.0)
                progress_percentage = job_progress.get("progress_percentage", 0)
                phase_details = job_progress.get(
                    "current_phase_details", "Processing..."
                )
                estimated_completion = job_progress.get("estimated_completion")

                # Update main progress bar
                if phase == "downloading" and total_videos > 0:
                    progress.update(
                        main_task,
                        completed=completed_videos + failed_videos,
                        description=f"Downloading playlist videos ({completed_videos + failed_videos}/{total_videos})",
                    )
                elif progress_percentage > 0:
                    progress.update(
                        main_task,
                        completed=progress_percentage,
                        total=100,
                        description=f"Processing playlists ({phase})",
                    )
                else:
                    progress.update(main_task, description=phase_details)

                # Display detailed status every few seconds or on phase changes
                time_since_update = (current_time - last_update_time).total_seconds()
                if time_since_update >= 5 or phase in [
                    "fetching_metadata",
                    "creating_jobs",
                    "playlist_completed",
                ]:
                    last_update_time = current_time

                    # Create status table
                    status_table = Table(show_header=True, header_style="bold magenta")
                    status_table.add_column("Metric", style="cyan", no_wrap=True)
                    status_table.add_column("Value", style="white")

                    # Add status rows
                    status_table.add_row(
                        "Phase",
                        f"[bold yellow]{phase.replace('_', ' ').title()}[/bold yellow]",
                    )
                    status_table.add_row(
                        "Playlists", f"{processed_playlists}/{total_playlists}"
                    )

                    if total_videos > 0:
                        success_rate = (
                            round(
                                (completed_videos / (completed_videos + failed_videos))
                                * 100,
                                1,
                            )
                            if (completed_videos + failed_videos) > 0
                            else 0
                        )
                        status_table.add_row(
                            "Videos Completed",
                            f"{completed_videos + failed_videos}/{total_videos}",
                        )
                        status_table.add_row(
                            "Success Rate",
                            f"[green]{success_rate}%[/green] ({completed_videos} successful, {failed_videos} failed)",
                        )

                    if download_speed > 0:
                        status_table.add_row(
                            "Download Speed", f"{download_speed:.1f} videos/min"
                        )

                    if estimated_completion:
                        try:
                            eta_dt = datetime.fromisoformat(
                                estimated_completion.replace("Z", "+00:00")
                            )
                            eta_str = eta_dt.strftime("%H:%M:%S")
                            status_table.add_row(
                                "Est. Completion", f"[blue]{eta_str}[/blue]"
                            )
                        except (ValueError, TypeError):
                            pass

                    # Current playlist info
                    if current_playlist:
                        playlist_info = f"[bold]{current_playlist.get('title', current_playlist.get('id', 'Unknown'))}[/bold]"
                        if "total_videos" in current_playlist:
                            playlist_info += (
                                f" ({current_playlist['total_videos']} videos)"
                            )
                        status_table.add_row("Current Playlist", playlist_info)

                    # Current video info
                    if current_video and current_video.get("title"):
                        video_status = current_video.get("status", "unknown")
                        video_info = f"[bold]{current_video['title']}[/bold] - [italic]{video_status}[/italic]"
                        status_table.add_row("Current Video", video_info)

                    # Create panels
                    status_panel = Panel(
                        status_table,
                        title="[bold blue]Playlist Progress Status[/bold blue]",
                        border_style="blue",
                    )

                    # Phase details panel
                    details_panel = Panel(
                        f"[italic]{phase_details}[/italic]",
                        title="[bold green]Current Operation[/bold green]",
                        border_style="green",
                    )

                    # Display panels
                    console.print(Columns([status_panel, details_panel]))
                    console.print("")

                # Check for completion
                if job_status["status"] in ["completed", "failed", "cancelled"]:
                    # Final status display
                    if job_status["status"] == "completed":
                        final_success_rate = (
                            round((completed_videos / total_videos) * 100, 1)
                            if total_videos > 0
                            else 0
                        )
                        console.print(
                            Panel(
                                f"[bold green]✅ Playlist download completed successfully![/bold green]\n\n"
                                f"📊 Final Statistics:\n"
                                f"   • Total Videos: {total_videos}\n"
                                f"   • Successfully Downloaded: [green]{completed_videos}[/green]\n"
                                f"   • Failed Downloads: [red]{failed_videos}[/red]\n"
                                f"   • Success Rate: [bold]{final_success_rate}%[/bold]\n"
                                f"   • Download Speed: {download_speed:.1f} videos/min",
                                title="[bold green]🎉 Playlist Download Complete[/bold green]",
                                border_style="green",
                            )
                        )
                    elif job_status["status"] == "failed":
                        error_details = job_status.get("error_details", "Unknown error")
                        console.print(
                            Panel(
                                f"[bold red]❌ Playlist download failed[/bold red]\n\n"
                                f"Error: {error_details}\n\n"
                                f"Progress before failure:\n"
                                f"   • Videos Completed: {completed_videos + failed_videos}/{total_videos}\n"
                                f"   • Successful: {completed_videos}\n"
                                f"   • Failed: {failed_videos}",
                                title="[bold red]❌ Download Failed[/bold red]",
                                border_style="red",
                            )
                        )
                    else:
                        console.print(
                            Panel(
                                f"[bold yellow]⏹️ Playlist download was cancelled[/bold yellow]\n\n"
                                f"Progress when cancelled:\n"
                                f"   • Videos Completed: {completed_videos + failed_videos}/{total_videos}\n"
                                f"   • Successful: {completed_videos}\n"
                                f"   • Failed: {failed_videos}",
                                title="[bold yellow]⏹️ Download Cancelled[/bold yellow]",
                                border_style="yellow",
                            )
                        )
                    break

                await asyncio.sleep(2)  # More frequent updates for better UX

            except Exception as e:
                console.print(
                    f"[red]❌ Error monitoring progress: {safe_error_message(e)}[/red]"
                )
                await asyncio.sleep(5)  # Wait longer on error
                break


if __name__ == "__main__":
    cli()
