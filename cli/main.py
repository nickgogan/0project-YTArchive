"""YTArchive CLI - Command-line interface for YouTube video archiving."""

import asyncio
import json
import os
import platform
import subprocess
import sys
import toml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import psutil

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


class RetryConfigType(click.ParamType):
    """Custom Click parameter type for retry config validation."""

    name = "retry_config"

    def convert(self, value, param, ctx):
        if not value:
            return {}

        # Valid retry strategies
        valid_strategies = {"exponential", "circuit_breaker", "adaptive", "fixed_delay"}

        # Split strategy name from parameters
        if ":" in value:
            strategy, params_str = value.split(":", 1)
        else:
            strategy = value
            params_str = ""

        strategy = strategy.strip()

        # Validate strategy name - Click will handle the exit code
        if strategy not in valid_strategies:
            self.fail(
                f"Invalid retry strategy '{strategy}'. Valid strategies are: {', '.join(sorted(valid_strategies))}",
                param,
                ctx,
            )

        return _parse_retry_config_dict(strategy, params_str)


def _parse_retry_config_dict(strategy: str, params_str: str) -> Dict[str, Any]:
    """Parse retry config parameters into dictionary."""
    config: Dict[str, Any] = {"retry_strategy": strategy}

    # Parse parameters if present
    if params_str:
        for param in params_str.split(","):
            if "=" in param:
                key, value = param.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Try to convert to appropriate type
                try:
                    # Try integer first
                    config[key] = int(value)
                except ValueError:
                    try:
                        # Try float
                        config[key] = float(value)
                    except ValueError:
                        # Keep as string
                        config[key] = value

    return config


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

    async def get_video_formats(self, video_id: str) -> Dict[str, Any]:
        """Get available video formats."""
        response = await self.client.get(
            f"{SERVICES['download']}/api/v1/download/formats/{video_id}"
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
    default="best",
    type=click.Choice(["best", "1080p", "720p", "480p", "360p", "audio"]),
    help="Video quality to download",
)
@click.option(
    "--output", "-o", default="~/YTArchive", help="Output directory for downloads"
)
@click.option(
    "--metadata-only", is_flag=True, help="Only fetch metadata, do not download video"
)
@click.option(
    "--retry-config",
    type=RetryConfigType(),
    help="Specify retry strategy for download failures (e.g., 'exponential', 'exponential:max_attempts=5,base_delay=2')",
)
@click.option(
    "--format-list",
    is_flag=True,
    help="Show available video formats and qualities",
)
@click.option(
    "--json",
    is_flag=True,
    help="Output format list in JSON format",
)
def download(
    video_id: str,
    quality: str,
    output: str,
    metadata_only: bool,
    retry_config: Dict[str, Any],
    format_list: bool,
    json: bool,
):
    """Download a YouTube video with metadata and captions."""
    asyncio.run(
        _download_video(
            video_id, quality, output, metadata_only, retry_config, format_list, json
        )
    )


async def _download_video(
    video_id: str,
    quality: str,
    output: str,
    metadata_only: bool,
    retry_config: Dict[str, Any],
    format_list: bool,
    json: bool,
):
    """Async implementation of video download."""
    async with YTArchiveAPI() as api:
        try:
            # Handle format list request
            if format_list:
                if not json:
                    console.print(
                        f"[blue]Fetching available formats for video {video_id}...[/blue]"
                    )
                try:
                    formats = await api.get_video_formats(video_id)
                    if json:
                        # Output raw JSON for JSON format
                        import json as json_module

                        console.print(json_module.dumps(formats))
                    else:
                        _display_video_formats(formats)
                    return
                except Exception as e:
                    if json:
                        import json as json_module

                        error_response = {"error": safe_error_message(e)}
                        console.print(json_module.dumps(error_response))
                        raise SystemExit(1)
                    else:
                        console.print(
                            f"[red]Error fetching formats: {safe_error_message(e)}[/red]"
                        )
                        raise SystemExit(1)

            # Display retry configuration if specified
            if retry_config:
                console.print(f"[yellow]Using {retry_config} retry strategy[/yellow]")

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

            # Parse retry configuration if provided
            job_config = {}
            if retry_config:
                job_config = retry_config.copy() if retry_config else {}
                console.print(
                    f"[yellow]Using retry configuration: {job_config}[/yellow]"
                )

            # Create download job
            console.print(
                f"[blue]Creating download job for {video_id} in {quality} quality...[/blue]"
            )

            job_response = await api.create_job(
                job_type="VIDEO_DOWNLOAD",
                video_id=video_id,
                config={"quality": quality, "output_path": output, **job_config},
            )

            if not job_response.get("success", True):  # Assume success if not specified
                console.print(
                    f"[red]Failed to create download job: {job_response.get('error', 'Unknown error')}[/red]"
                )
                return

            job_id = job_response.get("job_id")
            console.print(f"[green]Download job created! Job ID: {job_id}[/green]")

            # Execute the job
            await api.execute_job(job_id)

            # Monitor job progress
            await _monitor_job_progress(api, job_id)

        except httpx.HTTPError as e:
            console.print(f"[red]HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error: {safe_error_message(e)}[/red]")


async def _monitor_job_progress(api: YTArchiveAPI, job_id: str):
    """Monitor job progress with status updates."""
    with Progress() as progress:
        job_task = progress.add_task("Processing job...", total=None)

        while True:
            try:
                job_response = await api.get_job(job_id)

                if not job_response.get(
                    "success", True
                ):  # Assume success if not specified
                    console.print(
                        f"[red]Failed to get job status: {job_response.get('error')}[/red]"
                    )
                    break

                job_data = job_response.get("data", job_response)
                status = job_data.get("status")

                # Update progress display
                progress.update(job_task, description=f"Job status: {status}")

                if status == "COMPLETED":
                    console.print(
                        f"[green]Job completed successfully! Job ID: {job_id}[/green]"
                    )
                    break
                elif status == "FAILED":
                    console.print(
                        f"[red]Job failed: {job_data.get('error', 'Unknown error')}[/red]"
                    )
                    break
                elif status == "CANCELLED":
                    console.print("[yellow]Job cancelled[/yellow]")
                    break

                await asyncio.sleep(1)

            except Exception as e:
                console.print(
                    f"[red]Error monitoring job: {safe_error_message(e)}[/red]"
                )
                break


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

                await asyncio.sleep(1)

            except Exception as e:
                console.print(
                    f"[red]Error monitoring progress: {safe_error_message(e)}[/red]"
                )
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


@recovery.command("list")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def list_plans(json_output: bool) -> None:
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


@cli.command()
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results in JSON format",
)
@click.option(
    "--detailed",
    is_flag=True,
    help="Show detailed health information",
)
def health(json_output: bool, detailed: bool):
    """Check system health status for all YTArchive services."""
    asyncio.run(_check_system_health(json_output, detailed))


@cli.command()
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results in JSON format",
)
@click.option(
    "--run-tests",
    is_flag=True,
    help="Run quick diagnostic tests",
)
@click.option(
    "--check-config",
    is_flag=True,
    help="Validate system configuration",
)
def diagnostics(json_output: bool, run_tests: bool, check_config: bool):
    """Run comprehensive system diagnostics for YTArchive."""
    asyncio.run(_run_system_diagnostics(json_output, run_tests, check_config))


@cli.group()
def config():
    """Manage YTArchive configuration and settings."""
    pass


@config.command()
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results in JSON format",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Attempt to fix configuration issues automatically",
)
def validate(json_output: bool, fix: bool):
    """Validate YTArchive configuration and settings."""
    asyncio.run(_validate_configuration(json_output, fix))


@cli.group()
def playlist():
    """Manage playlist downloads and operations."""
    pass


@playlist.command("download")
@click.argument("playlist_url")
@click.option(
    "--quality",
    "-q",
    default="best",
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
            if not json_output:
                console.print("[yellow]📊 Fetching playlist information...[/yellow]")
            playlist_metadata = await api.get_playlist_metadata(playlist_id)

            if not playlist_metadata:
                if not json_output:
                    console.print("[red]❌ Failed to fetch playlist metadata[/red]")
                return

            if json_output:
                print(json.dumps(playlist_metadata, indent=2))
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

                    # Check if job exists
                    if job_status is None:
                        console.print(f"[red]❌ Job not found: {job_id}[/red]")
                        break

                    # Display current status
                    _display_playlist_job_status(job_status)

                    if job_status["status"] in ["completed", "failed", "cancelled"]:
                        break

                    await asyncio.sleep(2)
            else:
                job_status = await api.get_job(job_id)
                if job_status is None:
                    console.print(f"[red]❌ Job not found: {job_id}[/red]")
                    return
                _display_playlist_job_status(job_status)

        except KeyboardInterrupt:
            console.print("\n[yellow]⏹️ Stopped watching job status[/yellow]")
        except httpx.HTTPError as e:
            console.print(f"[red]❌ HTTP Error: {e}[/red]")
        except Exception as e:
            console.print(
                f"[red]An unexpected error occurred: {safe_error_message(e)}[/red]"
            )
            raise


def _get_performance_metrics() -> Dict[str, Any]:
    """Gathers performance metrics using psutil."""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage_percent": psutil.disk_usage(".").percent,
        "load_average": psutil.getloadavg() if hasattr(psutil, "getloadavg") else None,
        "boot_time": psutil.boot_time(),
    }


async def _check_system_health(json_output: bool, detailed: bool):
    """Async implementation of system health checking."""
    try:
        async with YTArchiveAPI() as api:
            health_data: Dict[str, Any] = {
                "timestamp": asyncio.get_event_loop().time(),
                "services": {},
                "overall_status": "healthy",
                "issues": [],
            }

            # Check each service health
            services = [
                ("jobs", "http://localhost:8001/health"),
                ("metadata", "http://localhost:8002/health"),
                ("storage", "http://localhost:8003/health"),
                ("download", "http://localhost:8004/health"),
                ("logging", "http://localhost:8005/health"),
            ]

            for service_name, health_url in services:
                try:
                    response = await api.client.get(health_url, timeout=5.0)
                    if response.status_code == 200:
                        service_data = response.json()
                        health_data["services"][service_name] = {
                            "status": "healthy",
                            "response_time_ms": response.elapsed.total_seconds() * 1000,
                            "details": service_data if detailed else None,
                        }
                    else:
                        health_data["services"][service_name] = {
                            "status": "unhealthy",
                            "error": f"HTTP {response.status_code}",
                        }
                        health_data["issues"].append(
                            f"{service_name} service returned {response.status_code}"
                        )
                        health_data["overall_status"] = "degraded"
                except Exception as e:
                    health_data["services"][service_name] = {
                        "status": "unavailable",
                        "error": str(e),
                    }
                    health_data["issues"].append(
                        f"{service_name} service unavailable: {str(e)}"
                    )
                    health_data["overall_status"] = "unhealthy"

            # Additional system checks if detailed
            if detailed:
                from pathlib import Path

                # System resource checks
                health_data["system"] = {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_usage": {
                        "logs": _get_directory_size("logs")
                        if Path("logs").exists()
                        else 0,
                        "free_space_gb": psutil.disk_usage(".").free / (1024**3),
                    },
                    "process_count": len(psutil.pids()),
                }

                # Check for critical directories
                critical_dirs = ["logs", "logs/temp"]
                for dir_path in critical_dirs:
                    if not Path(dir_path).exists():
                        health_data["issues"].append(
                            f"Critical directory missing: {dir_path}"
                        )
                        health_data["overall_status"] = "degraded"

            # Output results
            if json_output:
                console.print(json.dumps(health_data, indent=4))
            else:
                _display_health_status(health_data)

            return health_data

    except Exception as e:
        if json_output:
            error_data = {"error": str(e), "overall_status": "error"}
            console.print(json.dumps(error_data, indent=2))
        else:
            console.print(f"[red]Health check failed: {safe_error_message(e)}[/red]")


def _get_directory_size(path: str) -> int:
    """Get total size of directory in bytes."""
    from pathlib import Path

    total_size = 0
    try:
        for file_path in Path(path).rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except Exception:
        pass
    return total_size


def _display_health_status(
    health_data: Dict[str, Any], console: Optional[Console] = None
):
    """Display health status in rich format."""
    from rich.table import Table

    if console is None:
        from cli.main import console as default_console

        console = default_console

    # Overall status
    status_color = {
        "healthy": "green",
        "degraded": "yellow",
        "unhealthy": "red",
        "error": "red",
    }.get(health_data["overall_status"], "white")

    console.print(
        f"\n[bold {status_color}]System Status: {health_data['overall_status'].upper()}[/bold {status_color}]"
    )

    # Services table
    services_table = Table(title="🚀 Service Health Status")
    services_table.add_column("Service", style="cyan")
    services_table.add_column("Status", justify="center")
    services_table.add_column("Response Time", justify="right")
    services_table.add_column("Details")

    for service_name, service_data in health_data["services"].items():
        status = service_data["status"]
        status_icon = {"healthy": "✅", "unhealthy": "❌", "unavailable": "⚠️"}.get(
            status, "❓"
        )
        status_color = {
            "healthy": "green",
            "unhealthy": "red",
            "unavailable": "yellow",
        }.get(status, "white")

        response_time = ""
        if "response_time_ms" in service_data:
            response_time = f"{service_data['response_time_ms']:.1f}ms"

        details = service_data.get("error", "OK")

        services_table.add_row(
            service_name.title(),
            f"[{status_color}]{status_icon} {status}[/{status_color}]",
            response_time,
            details,
        )

    console.print(services_table)

    # System info if detailed
    if "system" in health_data:
        system_table = Table(title="💻 System Resources")
        system_table.add_column("Metric", style="cyan")
        system_table.add_column("Value", justify="right")

        system = health_data["system"]
        system_table.add_row("CPU Usage", f"{system['cpu_percent']:.1f}%")
        system_table.add_row("Memory Usage", f"{system['memory_percent']:.1f}%")
        system_table.add_row(
            "Free Disk Space", f"{system['disk_usage']['free_space_gb']:.1f} GB"
        )
        system_table.add_row(
            "Logs Directory Size",
            f"{system['disk_usage']['logs'] / 1024 / 1024:.1f} MB",
        )
        system_table.add_row("Running Processes", str(system["process_count"]))

        console.print(system_table)

    # Issues
    if health_data["issues"]:
        console.print("\n[bold red]⚠️  Issues Detected:[/bold red]")
        for issue in health_data["issues"]:
            console.print(f"  • [red]{issue}[/red]")
    else:
        console.print("\n[bold green]✅ No issues detected[/bold green]")

    console.print()


def _display_video_formats(formats: Dict[str, Any]):
    """Display available video formats in rich format."""
    from rich.table import Table

    if not formats or "formats" not in formats:
        console.print("[yellow]No format information available[/yellow]")
        return

    formats_table = Table(
        title=f"🎥 Available Formats for {formats.get('video_id', 'Unknown')}"
    )
    formats_table.add_column("Format ID", style="cyan")
    formats_table.add_column("Quality", justify="center")
    formats_table.add_column("Resolution", justify="center")
    formats_table.add_column("File Size", justify="right")
    formats_table.add_column("Extension", justify="center")
    formats_table.add_column("Note")

    for fmt in formats.get("formats", []):
        format_id = fmt.get("format_id", "N/A")
        quality = fmt.get("quality", "N/A")
        resolution = f"{fmt.get('width', '?')}x{fmt.get('height', '?')}"
        if fmt.get("width") is None and fmt.get("height") is None:
            resolution = "Audio Only" if "audio" in format_id.lower() else "N/A"

        file_size = "N/A"
        if fmt.get("filesize"):
            file_size = f"{fmt['filesize'] / 1024 / 1024:.1f} MB"
        elif fmt.get("filesize_approx"):
            file_size = f"~{fmt['filesize_approx'] / 1024 / 1024:.1f} MB"

        ext = fmt.get("ext", "N/A")
        note = fmt.get("format_note", "")

        formats_table.add_row(format_id, quality, resolution, file_size, ext, note)

    console.print(formats_table)

    # Display audio formats if available
    if "audio_formats" in formats and formats["audio_formats"]:
        console.print("\n")
        audio_table = Table(title="🎵 Audio Formats")
        audio_table.add_column("Format ID", style="cyan")
        audio_table.add_column("Quality", justify="center")
        audio_table.add_column("Resolution", justify="center")
        audio_table.add_column("File Size", justify="right")
        audio_table.add_column("Extension", justify="center")
        audio_table.add_column("Note")

        for fmt in formats["audio_formats"]:
            format_id = fmt.get("format_id", "N/A")
            quality = fmt.get("quality", "N/A")
            resolution = "Audio Only"

            file_size = "N/A"
            if fmt.get("filesize"):
                file_size = f"{fmt['filesize'] / 1024 / 1024:.1f} MB"
            elif fmt.get("filesize_approx"):
                file_size = f"~{fmt['filesize_approx'] / 1024 / 1024:.1f} MB"

            ext = fmt.get("ext", "N/A")
            note = fmt.get("format_note", "")

            audio_table.add_row(format_id, quality, resolution, file_size, ext, note)

        console.print(audio_table)

    # Show recommended qualities
    recommended = ["best", "1080p", "720p", "480p", "360p", "audio"]
    console.print("\n[bold green]💡 Recommended quality options:[/bold green]")
    for quality in recommended:
        console.print(f"  • [cyan]{quality}[/cyan]")
    console.print()


async def _run_system_diagnostics(
    json_output: bool, run_tests: bool, check_config: bool
):
    """Async implementation of comprehensive system diagnostics."""
    try:
        diagnostics_data: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "system_info": {},
            "python_environment": {},
            "ytarchive_config": {},
            "testing_infrastructure": {},
            "directory_structure": {},
            "performance_metrics": {},
            "recommendations": [],
            "overall_status": "healthy",
        }

        # System Information
        diagnostics_data["system_info"] = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture()[0],
            "cpu_count": psutil.cpu_count(),
            "total_memory_gb": psutil.virtual_memory().total / (1024**3),
            "hostname": platform.node(),
        }

        # Python Environment
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
            )
            import json as json_lib

            packages = json_lib.loads(result.stdout)
            key_packages = [
                "httpx",
                "pydantic",
                "click",
                "yt-dlp",
                "rich",
                "psutil",
                "pytest",
            ]
            diagnostics_data["python_environment"] = {
                "pip_packages": {
                    pkg["name"]: pkg["version"]
                    for pkg in packages
                    if pkg["name"].lower() in [p.lower() for p in key_packages]
                },
                "python_path": sys.executable,
                "working_directory": str(Path.cwd()),
            }
        except Exception as e:
            diagnostics_data["python_environment"]["error"] = str(e)

        # YTArchive Configuration Check
        if check_config:
            config_issues = []

            # Check critical directories
            critical_dirs = ["logs", "logs/temp", "services", "cli", "tests"]
            for dir_path in critical_dirs:
                if not Path(dir_path).exists():
                    config_issues.append(f"Missing directory: {dir_path}")

            # Check critical files
            critical_files = ["pyproject.toml", "pytest.ini", "cli/main.py"]
            for file_path in critical_files:
                if not Path(file_path).exists():
                    config_issues.append(f"Missing file: {file_path}")

            diagnostics_data["ytarchive_config"] = {
                "issues": config_issues,
                "status": "valid" if not config_issues else "issues_found",
            }

            if config_issues:
                diagnostics_data["overall_status"] = "degraded"

        # Testing Infrastructure Status
        test_results: Dict[str, Any] = {}
        if run_tests:
            try:
                # Run a quick unit test to verify testing infrastructure
                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "pytest",
                        "tests/common/test_utils.py",
                        "-v",
                        "--tb=no",
                        "-q",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                test_results["unit_tests"] = {
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "status": "passing" if result.returncode == 0 else "failing",
                }

                # Test memory leak detection availability
                memory_test_path = Path("tests/memory/memory_leak_detection.py")
                test_results["memory_leak_detection"] = {
                    "available": memory_test_path.exists(),
                    "status": "available" if memory_test_path.exists() else "missing",
                }

                # Test integration test infrastructure
                integration_test_dir = Path("tests/integration")
                if integration_test_dir.exists():
                    integration_files = list(integration_test_dir.glob("test_*.py"))
                    test_results["integration_tests"] = {
                        "available": len(integration_files) > 0,
                        "test_files_count": len(integration_files),
                        "status": "available" if integration_files else "missing",
                    }

            except subprocess.TimeoutExpired:
                test_results["error"] = "Test execution timed out"
            except Exception as e:
                test_results["error"] = str(e)

        diagnostics_data["testing_infrastructure"] = test_results

        # Directory Structure Analysis
        structure_analysis: Dict[str, Any] = {}
        project_dirs = ["services", "cli", "tests", "logs", "docs", "Planning"]
        for dir_name in project_dirs:
            project_dir_path: Path = Path(dir_name)
            if project_dir_path.exists():
                files = list(project_dir_path.rglob("*"))
                structure_analysis[dir_name] = {
                    "exists": True,
                    "file_count": len([f for f in files if f.is_file()]),
                    "subdirectory_count": len([f for f in files if f.is_dir()]),
                    "total_size_mb": sum(f.stat().st_size for f in files if f.is_file())
                    / (1024 * 1024),
                }
            else:
                structure_analysis[dir_name] = {"exists": False}

        diagnostics_data["directory_structure"] = structure_analysis

        diagnostics_data["performance_metrics"] = _get_performance_metrics()

        # Generate Recommendations
        recommendations = []

        # Memory recommendations
        if diagnostics_data["performance_metrics"]["memory_percent"] > 80:
            recommendations.append(
                "High memory usage detected - consider closing other applications"
            )

        # CPU recommendations
        if diagnostics_data["performance_metrics"]["cpu_percent"] > 90:
            recommendations.append(
                "High CPU usage detected - system may be under heavy load"
            )

        # Disk space recommendations
        if diagnostics_data["performance_metrics"]["disk_usage_percent"] > 90:
            recommendations.append(
                "Low disk space - consider cleaning up logs or temporary files"
            )

        # Testing infrastructure recommendations
        if (
            "testing_infrastructure" in diagnostics_data
            and diagnostics_data["testing_infrastructure"]
        ):
            if "unit_tests" in diagnostics_data["testing_infrastructure"]:
                if (
                    diagnostics_data["testing_infrastructure"]["unit_tests"].get(
                        "status"
                    )
                    == "failing"
                ):
                    recommendations.append(
                        "Unit tests are failing - run 'uv run pytest -m unit' to investigate"
                    )

        # Configuration recommendations
        if check_config and diagnostics_data["ytarchive_config"].get("issues"):
            recommendations.append(
                "Configuration issues detected - check missing files/directories"
            )

        diagnostics_data["recommendations"] = recommendations

        # Update overall status based on findings
        if recommendations:
            diagnostics_data["overall_status"] = "attention_needed"

        # Output results
        if json_output:
            console.print(json.dumps(diagnostics_data, indent=2, default=str))
        else:
            _display_diagnostics_results(diagnostics_data)

    except Exception as e:
        if json_output:
            error_data = {"error": str(e), "overall_status": "error"}
            console.print(json.dumps(error_data, indent=2))
        else:
            console.print(f"[red]Diagnostics failed: {safe_error_message(e)}[/red]")


def _display_diagnostics_results(
    diagnostics_data: Dict[str, Any], console: Optional[Console] = None
):
    """Display diagnostics results in rich format."""
    from rich.table import Table
    from rich.columns import Columns

    if console is None:
        from cli.main import console as default_console

        console = default_console

    # Header
    status_color = {
        "healthy": "green",
        "attention_needed": "yellow",
        "degraded": "red",
        "error": "red",
    }.get(diagnostics_data["overall_status"], "white")

    console.print(
        f"\n[bold {status_color}]🔍 System Diagnostics: {diagnostics_data['overall_status'].replace('_', ' ').upper()}[/bold {status_color}]"
    )

    # System Information Table
    sys_table = Table(title="💻 System Information")
    sys_table.add_column("Metric", style="cyan")
    sys_table.add_column("Value", justify="left")

    system_info = diagnostics_data["system_info"]
    sys_table.add_row("Platform", system_info["platform"])
    sys_table.add_row("Python Version", system_info["python_version"])
    sys_table.add_row("Architecture", system_info["architecture"])
    sys_table.add_row("CPU Cores", str(system_info["cpu_count"]))
    sys_table.add_row("Total Memory", f"{system_info['total_memory_gb']:.1f} GB")

    # Performance Metrics Table
    perf_table = Table(title="📊 Performance Metrics")
    perf_table.add_column("Metric", style="cyan")
    perf_table.add_column("Value", justify="right")
    perf_table.add_column("Status")

    perf = diagnostics_data["performance_metrics"]

    # CPU usage with status
    cpu_status = (
        "🟢 Normal"
        if perf["cpu_percent"] < 70
        else "🟡 High"
        if perf["cpu_percent"] < 90
        else "🔴 Critical"
    )
    perf_table.add_row("CPU Usage", f"{perf['cpu_percent']:.1f}%", cpu_status)

    # Memory usage with status
    mem_status = (
        "🟢 Normal"
        if perf["memory_percent"] < 70
        else "🟡 High"
        if perf["memory_percent"] < 85
        else "🔴 Critical"
    )
    perf_table.add_row("Memory Usage", f"{perf['memory_percent']:.1f}%", mem_status)

    # Disk usage with status
    disk_status = (
        "🟢 Normal"
        if perf["disk_usage_percent"] < 80
        else "🟡 High"
        if perf["disk_usage_percent"] < 95
        else "🔴 Critical"
    )
    perf_table.add_row("Disk Usage", f"{perf['disk_usage_percent']:.1f}%", disk_status)

    # Display tables side by side
    console.print(Columns([sys_table, perf_table]))

    # Testing Infrastructure Status
    if (
        "testing_infrastructure" in diagnostics_data
        and diagnostics_data["testing_infrastructure"]
    ):
        test_table = Table(title="🧪 Testing Infrastructure")
        test_table.add_column("Component", style="cyan")
        test_table.add_column("Status", justify="center")
        test_table.add_column("Details")

        test_infra = diagnostics_data["testing_infrastructure"]

        for component, data in test_infra.items():
            if isinstance(data, dict) and "status" in data:
                status = data["status"]
                status_icon = {
                    "passing": "✅",
                    "failing": "❌",
                    "available": "✅",
                    "missing": "⚠️",
                }.get(status, "❓")
                details = ""
                if component == "integration_tests" and "test_files_count" in data:
                    details = f"{data['test_files_count']} test files"
                elif component == "unit_tests" and "exit_code" in data:
                    details = f"Exit code: {data['exit_code']}"

                test_table.add_row(
                    component.replace("_", " ").title(),
                    f"{status_icon} {status}",
                    details,
                )

        if test_table.row_count > 0:
            console.print(test_table)

    # Directory Structure
    if "directory_structure" in diagnostics_data:
        dir_table = Table(title="📁 Directory Structure")
        dir_table.add_column("Directory", style="cyan")
        dir_table.add_column("Status", justify="center")
        dir_table.add_column("Files", justify="right")
        dir_table.add_column("Size (MB)", justify="right")

        for dir_name, data in diagnostics_data["directory_structure"].items():
            if data.get("exists", False):
                status = "✅ Present"
                files = str(data.get("file_count", 0))
                size = f"{data.get('total_size_mb', 0):.1f}"
            else:
                status = "❌ Missing"
                files = "-"
                size = "-"

            dir_table.add_row(dir_name, status, files, size)

        console.print(dir_table)

    # Recommendations
    if diagnostics_data["recommendations"]:
        console.print("\n[bold yellow]💡 Recommendations:[/bold yellow]")
        for i, recommendation in enumerate(diagnostics_data["recommendations"], 1):
            console.print(f"  {i}. [yellow]{recommendation}[/yellow]")
    else:
        console.print(
            "\n[bold green]✅ No recommendations - system looks good![/bold green]"
        )

    console.print()


def _validate_pyproject_file():
    """Validate pyproject.toml file and dependencies."""
    result = {
        "file_data": {"exists": False, "valid": False},
        "issues": [],
        "warnings": [],
    }

    try:
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            result["issues"].append("Missing pyproject.toml file")
            return result

        result["file_data"]["exists"] = True

        try:
            with open(pyproject_path, "rb") as f:
                p_data = toml.load(f)

            result["file_data"].update(
                {
                    "valid": True,
                    "project_name": p_data.get("project", {}).get("name"),
                    "dependencies_count": len(
                        p_data.get("project", {}).get("dependencies", [])
                    ),
                }
            )

            # Check required dependencies
            deps = p_data.get("project", {}).get("dependencies", [])
            required_deps = ["httpx", "pydantic", "click", "yt-dlp", "rich", "psutil"]
            missing = [d for d in required_deps if not any(d in p for p in deps)]
            if missing:
                result["issues"].append(
                    f"Missing required dependencies: {', '.join(missing)}"
                )

        except toml.TomlDecodeError as e:
            result["issues"].append(f"Invalid pyproject.toml: {e}")
        except TypeError as e:
            # TypeError from TOML library usually indicates filesystem/mocking issues
            # Re-raise to preserve original error message in outer exception handler
            raise Exception("File system error") from e

    except Exception:
        # Re-raise filesystem and system errors to be handled as "error" status
        # rather than treating them as configuration "issues_found"
        raise

    return result


def _validate_pytest_file():
    """Validate pytest.ini file and test markers."""
    result = {
        "file_data": {"exists": False, "valid": False},
        "issues": [],
        "warnings": [],
    }

    pytest_ini_path = Path("pytest.ini")
    if not pytest_ini_path.exists():
        return result  # pytest.ini is optional, no issues

    result["file_data"]["exists"] = True

    with open(pytest_ini_path, "r") as f:
        content = f.read()

    result["file_data"].update(
        {
            "valid": True,
            "has_testpaths": "testpaths" in content,
            "has_markers": "markers" in content,
        }
    )

    # Check required test markers
    required_markers = ["unit", "integration", "e2e", "memory"]
    missing_markers = [m for m in required_markers if m not in content]
    if missing_markers:
        result["warnings"].append(f"Missing test markers: {', '.join(missing_markers)}")

    return result


def _validate_critical_directories(fix: bool):
    """Validate critical directories and optionally create them."""
    result: Dict[str, Any] = {
        "directory_data": {},
        "issues": [],
        "warnings": [],
        "fixes_applied": [],
    }

    critical_dirs = {
        "logs": "Required for centralized logging",
        "logs/temp": "Required for temporary files",
        "services": "Contains service implementations",
        "cli": "Contains CLI implementation",
        "tests": "Contains test suite",
        "tests/integration": "Integration test suite",
        "tests/memory": "Memory leak detection tests",
    }

    missing_dirs = []
    for dir_path, desc in critical_dirs.items():
        path = Path(dir_path)
        exists = path.exists()
        result["directory_data"][dir_path] = {"exists": exists, "description": desc}
        if not exists:
            missing_dirs.append(dir_path)

    if missing_dirs:
        if fix:
            for d in missing_dirs:
                try:
                    Path(d).mkdir(parents=True, exist_ok=True)
                    result["fixes_applied"].append(f"Created directory: {d}")
                    result["directory_data"][d]["exists"] = True
                except Exception as e:
                    result["issues"].append(f"Failed to create directory {d}: {e}")
        else:
            for d in missing_dirs:
                result["issues"].append(f"Missing critical directory: {d}")

    return result


def _validate_environment_variables():
    """Validate required environment variables."""
    result = {"env_data": {}, "issues": [], "warnings": []}

    env_vars = {
        "YOUTUBE_API_KEY": "Required for YouTube API access",
        "PYTHONPATH": "Optional for development",
    }

    for var, desc in env_vars.items():
        val = os.getenv(var)
        result["env_data"][var] = {
            "set": bool(val),
            "masked_value": "***" if val and "KEY" in var else val or "Not set",
        }
        if not val and var == "YOUTUBE_API_KEY":
            result["warnings"].append(f"Environment variable {var} not set")

    return result


def _validate_service_configs():
    """Validate service configuration files."""
    result = {"services_data": {}, "issues": [], "warnings": []}

    for service in ["jobs", "metadata", "storage", "download", "logging"]:
        path = Path(f"services/{service}/config.py")
        exists = path.exists()
        result["services_data"][service] = {"config_exists": exists}
        if not exists:
            result["warnings"].append(
                f"Missing service config: services/{service}/config.py"
            )

    return result


def _determine_overall_status(issues, warnings):
    """Determine overall validation status based on issues and warnings."""
    if issues:
        return "issues_found"
    elif warnings:
        return "warnings_only"
    else:
        return "valid"


async def _validate_configuration(json_output: bool, fix: bool):
    """Async implementation of configuration validation using separated concerns."""
    validation_data: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "valid",
        "issues": [],
        "warnings": [],
        "fixes_applied": [],
        "configuration_files": {},
        "directory_structure": {},
        "environment_variables": {},
        "dependencies": {},
        "services_config": {},
    }

    try:
        # Validate each component separately
        pyproject_result = _validate_pyproject_file()
        pytest_result = _validate_pytest_file()
        directories_result = _validate_critical_directories(fix)
        env_result = _validate_environment_variables()
        services_result = _validate_service_configs()

        # Aggregate results
        validation_data["configuration_files"]["pyproject.toml"] = pyproject_result[
            "file_data"
        ]
        validation_data["configuration_files"]["pytest.ini"] = pytest_result[
            "file_data"
        ]
        validation_data["directory_structure"] = directories_result["directory_data"]
        validation_data["environment_variables"] = env_result["env_data"]
        validation_data["services_config"] = services_result["services_data"]

        # Collect all issues and warnings
        all_issues = (
            pyproject_result["issues"]
            + pytest_result["issues"]
            + directories_result["issues"]
            + env_result["issues"]
            + services_result["issues"]
        )
        all_warnings = (
            pyproject_result["warnings"]
            + pytest_result["warnings"]
            + directories_result["warnings"]
            + env_result["warnings"]
            + services_result["warnings"]
        )

        validation_data["issues"] = all_issues
        validation_data["warnings"] = all_warnings
        validation_data["fixes_applied"] = directories_result["fixes_applied"]

        # Determine overall status
        validation_data["overall_status"] = _determine_overall_status(
            all_issues, all_warnings
        )

    except Exception as e:
        validation_data["overall_status"] = "error"
        validation_data["error"] = str(e)
        # Clear other fields that might have partial data
        validation_data["issues"] = []
        validation_data["warnings"] = []
        validation_data["fixes_applied"] = []

    if json_output:
        try:
            console.print(json.dumps(validation_data, indent=4))
        except (TypeError, ValueError) as json_error:
            # Fallback for JSON serialization issues
            error_data = {
                "timestamp": datetime.now().isoformat(),
                "overall_status": "error",
                "error": f"JSON serialization failed: {str(json_error)}",
                "issues": [],
                "warnings": [],
                "fixes_applied": [],
                "configuration_files": {},
                "directory_structure": {},
                "environment_variables": {},
                "dependencies": {},
                "services_config": {},
            }
            console.print(json.dumps(error_data, indent=4))
    else:
        _display_configuration_validation(validation_data)

    # Return validation_data for testing purposes
    return validation_data


def _display_configuration_validation(validation_data: Dict[str, Any]):
    """Display configuration validation results in rich format."""
    from rich.table import Table
    from rich.columns import Columns

    # Header
    status_color = {
        "valid": "green",
        "warnings_only": "yellow",
        "issues_found": "red",
        "error": "red",
    }.get(validation_data["overall_status"], "white")

    console.print(
        f"\n[bold {status_color}]⚙️ Configuration Validation: {validation_data['overall_status'].replace('_', ' ').upper()}[/bold {status_color}]"
    )

    # Configuration Files Table
    config_table = Table(title="📄 Configuration Files")
    config_table.add_column("File", style="cyan")
    config_table.add_column("Status", justify="center")
    config_table.add_column("Details")

    for file_name, file_data in validation_data["configuration_files"].items():
        if file_data["exists"]:
            if file_data.get("valid", True):
                status = "✅ Valid"
                details = f"Project: {file_data.get('project_name', 'N/A')}"
                if "dependencies_count" in file_data:
                    details += f", Deps: {file_data['dependencies_count']}"
            else:
                status = "❌ Invalid"
                details = file_data.get("error", "Unknown error")
        else:
            status = "❌ Missing"
            details = "File not found"

        config_table.add_row(file_name, status, details)

    # Directory Structure Table
    dir_table = Table(title="📁 Directory Structure")
    dir_table.add_column("Directory", style="cyan")
    dir_table.add_column("Status", justify="center")
    dir_table.add_column("Description")

    for dir_name, dir_data in validation_data["directory_structure"].items():
        status = "✅ Present" if dir_data["exists"] else "❌ Missing"
        dir_table.add_row(dir_name, status, dir_data["description"])

    # Display tables side by side
    console.print(Columns([config_table, dir_table]))

    # Environment Variables
    if validation_data["environment_variables"]:
        env_table = Table(title="🌍 Environment Variables")
        env_table.add_column("Variable", style="cyan")
        env_table.add_column("Status", justify="center")
        env_table.add_column("Value")

        for var_name, var_data in validation_data["environment_variables"].items():
            status = "✅ Set" if var_data["set"] else "❌ Missing"
            value = var_data.get("masked_value", "Not set")
            env_table.add_row(var_name, status, str(value))

        console.print(env_table)

    # Issues
    if validation_data["issues"]:
        console.print("\n[bold red]❌ Issues Found:[/bold red]")
        for i, issue in enumerate(validation_data["issues"], 1):
            console.print(f"  {i}. [red]{issue}[/red]")

    # Warnings
    if validation_data["warnings"]:
        console.print("\n[bold yellow]⚠️  Warnings:[/bold yellow]")
        for i, warning in enumerate(validation_data["warnings"], 1):
            console.print(f"  {i}. [yellow]{warning}[/yellow]")

    # Fixes Applied
    if validation_data["fixes_applied"]:
        console.print("\n[bold green]🔧 Fixes Applied:[/bold green]")
        for i, fix in enumerate(validation_data["fixes_applied"], 1):
            console.print(f"  {i}. [green]{fix}[/green]")

    # Summary
    if validation_data["overall_status"] == "valid":
        console.print(
            "\n[bold green]✅ Configuration is valid - no issues detected![/bold green]"
        )
    elif validation_data["overall_status"] == "warnings_only":
        console.print(
            "\n[bold yellow]💡 Configuration is mostly valid but has some warnings to address[/bold yellow]"
        )
    else:
        console.print(
            "\n[bold red]❌ Configuration has issues that need to be resolved[/bold red]"
        )
        console.print("[dim]Run with --fix flag to automatically fix some issues[/dim]")

    console.print()


def _extract_playlist_id(playlist_url: str) -> str:
    """Extract playlist ID from YouTube playlist URL."""
    import re

    # Pattern to match playlist ID from various YouTube playlist URL formats
    patterns = [
        r"[?&]list=([a-zA-Z0-9_-]+)",  # Standard playlist URL
        r"playlist\?list=([a-zA-Z0-9_-]+)",  # Direct playlist URL
    ]

    for pattern in patterns:
        match = re.search(pattern, playlist_url)
        if match:
            return match.group(1)

    raise ValueError(f"Invalid playlist URL: {playlist_url}")


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

    # Display errors if present
    errors = job_status.get("errors", [])
    if errors:
        status_info += "\n[red]🚨 Errors:[/red]"
        for error in errors:
            status_info += f"\n[red]  • {error}[/red]"

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
