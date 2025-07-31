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

    async def clear_logs(
        self, directories: Optional[list[str]] = None, confirm: bool = False
    ) -> Dict[str, Any]:
        """Clear log directories while preserving structure."""
        params: Dict[str, Any] = {"confirm": str(confirm).lower()}
        if directories:
            # Handle multiple directories properly
            params["directories"] = directories

        response = await self.client.post(
            f"{SERVICES['logging']}/clear-logs", params=params
        )
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
    json_output: bool,
):
    """Async implementation of video download."""
    try:
        async with YTArchiveAPI() as api:
            if format_list:
                formats = await api.get_video_formats(video_id)
                if json_output:
                    console.print(json.dumps(formats, indent=2))
                else:
                    # Display formats in a readable table
                    table = Table(title="Available Video Formats")
                    table.add_column("Format ID", style="cyan")
                    table.add_column("Extension", style="green")
                    table.add_column("Resolution", style="magenta")
                    table.add_column("Note", style="dim")

                    for fmt in formats:
                        table.add_row(
                            fmt.get("format_id", ""),
                            fmt.get("ext", ""),
                            fmt.get("resolution", "N/A"),
                            fmt.get("format_note", ""),
                        )
                    console.print(table)
                return

            job_config = {
                "quality": quality,
                "output_path": output,
                "metadata_only": metadata_only,
                "retry_config": retry_config,
            }
            job = await api.create_job(
                job_type="download", video_id=video_id, config=job_config
            )
            job_id = job.get("job_id")
            if not job_id:
                console.print("[red]Failed to create job.[/red]")
                return

            console.print(f"[green]Job created:[/green] {job_id}")

            # Execute the job
            execution_result = await api.execute_job(job_id)
            task_id = execution_result.get("task_id")
            if not task_id:
                console.print("[red]Failed to start job execution.[/red]")
                return

            console.print(f"[green]Job execution started. Task ID:[/green] {task_id}")

            # Monitor progress
            await _monitor_download_progress(api, task_id)

    except httpx.HTTPError as e:
        console.print(f"[red]HTTP Error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {safe_error_message(e)}[/red]")


async def _monitor_job_progress(api: YTArchiveAPI, job_id: str):
    """Monitor job progress with status updates."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=100)

        while not progress.finished:
            job_status = await api.get_job(job_id)
            status = job_status.get("status", "UNKNOWN")
            progress_val = job_status.get("progress", 0)

            progress.update(task, completed=progress_val, description=status)

            if status in ["COMPLETED", "FAILED"]:
                break

            await asyncio.sleep(2)


async def _monitor_download_progress(api: YTArchiveAPI, task_id: str):
    """Monitor download progress with a progress bar."""
    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        "•",
        DownloadColumn(),
        "•",
        TransferSpeedColumn(),
        "•",
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_progress = progress.add_task("download", filename="Starting...", total=100)

        while not progress.finished:
            try:
                status = await api.get_download_progress(task_id)
                state = status.get("state", "PENDING")

                if state == "SUCCESS":
                    progress.update(
                        task_progress,
                        completed=100,
                        description="[green]Completed[/green]",
                    )
                    console.print(
                        f"[green]Download complete! Saved to:[/green] {status.get('result', {}).get('output_path')}"
                    )
                    break
                elif state == "FAILURE":
                    progress.update(task_progress, description="[red]Failed[/red]")
                    console.print(f"[red]Download failed:[/red] {status.get('info')}")
                    break
                elif state == "PROGRESS":
                    info = status.get("info", {})
                    progress.update(
                        task_progress,
                        total=info.get("total_bytes", 100),
                        completed=info.get("downloaded_bytes", 0),
                        filename=info.get("filename", "downloading..."),
                    )
                else:
                    progress.update(task_progress, description=state)

                await asyncio.sleep(1)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    console.print("[yellow]Waiting for download to start...[/yellow]")
                    await asyncio.sleep(3)
                else:
                    raise


@cli.command()
@click.argument("video_id")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def metadata(video_id: str, json_output: bool):
    """Fetch and display metadata for a YouTube video."""
    asyncio.run(_get_metadata(video_id, json_output))


async def _get_metadata(video_id: str, json_output: bool):
    """Async implementation of metadata fetching."""
    try:
        async with YTArchiveAPI() as api:
            metadata = await api.get_video_metadata(video_id)
            if json_output:
                console.print(json.dumps(metadata, indent=2))
            else:
                table = Table(title=f"Metadata for {video_id}", box=None)
                table.add_column("Field", style="cyan")
                table.add_column("Value")

                for key, value in metadata.items():
                    if isinstance(value, list):
                        value = ", ".join(map(str, value))
                    elif isinstance(value, dict):
                        value = json.dumps(value, indent=2)
                    elif key == "duration":
                        value = format_duration(value)
                    elif key == "filesize":
                        value = format_file_size(value)

                    table.add_row(key.replace("_", " ").title(), str(value))
                console.print(table)
    except httpx.HTTPError as e:
        console.print(f"[red]HTTP Error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {safe_error_message(e)}[/red]")


async def _clear_logs(
    directories: tuple[str], clear_all: bool, confirm: bool, json_output: bool
):
    """Async implementation of log clearing."""
    if not clear_all and not directories:
        console.print(
            "[bold red]Error:[/bold red] You must specify directories to clear with `-d` or use the `--all` flag."
        )
        return

    target_dirs: Optional[list[str]] = list(directories) if directories else None
    if clear_all:
        target_dirs = None  # Service will clear all if this is None

    if not confirm:
        scope = "ALL log" if clear_all or not target_dirs else "the specified"
        warning_message = (
            f"[bold yellow]WARNING[/bold yellow]: You are about to permanently delete files in {scope} directories.\n"
            "This action cannot be undone."
        )
        console.print(
            Panel(
                warning_message,
                title="[bold red]Confirmation Required[/bold red]",
                border_style="red",
            )
        )

        if not click.confirm("Are you sure you want to proceed?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    try:
        async with YTArchiveAPI() as api:
            with console.status(
                "[bold green]Clearing log directories...[/bold green]", spinner="dots"
            ) as status:
                result = await api.clear_logs(directories=target_dirs, confirm=True)

                if json_output:
                    console.print(json.dumps(result, indent=2))
                    return

                status.stop()
                details = result.get("details", {})
                total_removed = details.get("total_files_removed", 0)

                console.print(
                    Panel(
                        f"[bold green]Success![/bold green] Total files removed: [bold]{total_removed}[/bold]",
                        title="[bold green]Clear Logs Summary[/bold green]",
                        border_style="green",
                    )
                )

                if processed := details.get("directories_processed"):
                    table = Table(title="Processed Directories", box=None)
                    table.add_column("Directory", style="cyan")
                    table.add_column("Files Removed", style="magenta")
                    for item in processed:
                        table.add_row(item["directory"], str(item["files_removed"]))
                    console.print(table)

                if skipped := details.get("directories_skipped"):
                    table = Table(title="Skipped Directories", box=None)
                    table.add_column("Directory", style="yellow")
                    table.add_column("Reason", style="dim")
                    for item in skipped:
                        table.add_row(item["directory"], item["reason"])
                    console.print(table)

                if errors := details.get("errors"):
                    table = Table(title="Errors Encountered", box=None)
                    table.add_column("Directory", style="red")
                    table.add_column("Error", style="bold red")
                    for item in errors:
                        table.add_row(item["directory"], item["error"])
                    console.print(table)

    except httpx.HTTPStatusError as e:
        try:
            error_data = e.response.json()
            console.print(f"[red]API Error: {error_data.get('detail', str(e))}[/red]")
        except json.JSONDecodeError:
            console.print(
                f"[red]HTTP Error {e.response.status_code}: {e.response.reason_phrase}[/red]"
            )
    except Exception as e:
        console.print(
            f"[red]An unexpected error occurred: {safe_error_message(e)}[/red]"
        )


@cli.command()
@click.argument("job_id")
@click.option("--watch", "-w", is_flag=True, help="Watch job status in real-time")
def status(job_id: str, watch: bool):
    """Check the status of a job."""
    asyncio.run(_get_job_status(job_id, watch))


async def _get_job_status(job_id: str, watch: bool):
    """Async implementation of job status checking."""
    while True:
        try:
            async with YTArchiveAPI() as api:
                job_data = await api.get_job(job_id)

                table = Table(title=f"Job Status for {job_id}", box=None)
                table.add_column("Field", style="cyan")
                table.add_column("Value")

                for key, value in job_data.items():
                    if key == "progress":
                        value = f"{value}%"
                    table.add_row(key.replace("_", " ").title(), str(value))

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


@cli.command("clear-logs")
@click.option(
    "--directories",
    "-d",
    multiple=True,
    help="Specific directories to clear (can be used multiple times)",
)
@click.option(
    "--all",
    "clear_all",
    is_flag=True,
    help="Clear all log directories",
)
@click.option(
    "--confirm",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt (dangerous!)",
)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def clear_logs(
    directories: tuple[str], clear_all: bool, confirm: bool, json_output: bool
):
    """Clear log directories while preserving directory structure.

    This command removes all files from specified log directories but keeps
    the directory structure intact. This action cannot be undone!

    Examples:

        # Clear specific directories (with confirmation)
        ytarchive clear-logs -d runtime -d jobs

        # Clear all directories (with confirmation)
        ytarchive clear-logs --all

        # Skip confirmation (dangerous!)
        ytarchive clear-logs --all -y
    """
    asyncio.run(_clear_logs(directories, clear_all, confirm, json_output))


@cli.group()
def recovery() -> None:
    """Manage recovery plans for failed and unavailable videos."""
    pass


@recovery.command("list")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def list_plans(json_output: bool) -> None:
    """List all recovery plans."""
    # TODO: Implement recovery plan listing functionality
    console.print("[yellow]Recovery plan listing not yet implemented.[/yellow]")


@recovery.command()
@click.argument("plan_id")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def show(plan_id: str, json_output: bool) -> None:
    """Show details of a specific recovery plan."""
    # TODO: Implement recovery plan details functionality
    console.print(
        f"[yellow]Recovery plan details for '{plan_id}' not yet implemented.[/yellow]"
    )


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
    # TODO: Implement recovery plan creation functionality
    console.print("[yellow]Recovery plan creation not yet implemented.[/yellow]")
    if unavailable_videos_file:
        console.print(
            f"[dim]Would process unavailable videos from: {unavailable_videos_file}[/dim]"
        )
    if failed_downloads_file:
        console.print(
            f"[dim]Would process failed downloads from: {failed_downloads_file}[/dim]"
        )


async def _view_logs(
    service: Optional[str], level: Optional[str], lines: int, follow: bool
):
    """Async implementation of log viewing."""
    try:
        async with YTArchiveAPI() as api:
            while True:
                logs_data = await api.get_logs(service=service, level=level)
                logs = logs_data.get("logs", [])

                if not logs:
                    console.print("[yellow]No logs found.[/yellow]")
                    if not follow:
                        break

                table = Table(
                    title=f"Logs (last {lines} lines)",
                    box=None,
                    show_header=True,
                    header_style="bold magenta",
                )
                table.add_column("Timestamp", style="dim", width=20)
                table.add_column("Service", style="cyan")
                table.add_column("Level", style="green")
                table.add_column("Message")

                for log in logs[-lines:]:
                    table.add_row(
                        log.get("timestamp"),
                        log.get("service"),
                        log.get("level"),
                        log.get("message"),
                    )

                console.clear()
                console.print(table)

                if not follow:
                    break

                await asyncio.sleep(5)  # Poll every 5 seconds

    except httpx.HTTPError as e:
        console.print(f"[red]HTTP Error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {safe_error_message(e)}[/red]")
