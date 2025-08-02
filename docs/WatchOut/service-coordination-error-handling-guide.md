# Service Coordination Error Handling Guide

This guide provides standards for handling and testing errors that occur during multi-service workflows in YTArchive. Proper error handling in a distributed system is critical for ensuring that a failure in one service does not leave the entire system in an inconsistent state.

## 1. The Orchestration Pattern

In YTArchive, the `JobsService` acts as the primary orchestrator for complex workflows like video archival. It does this by making a sequence of API calls to other services (e.g., `DownloadService`, `MetadataService`, `StorageService`).

**The core challenge**: If a downstream service (e.g., `DownloadService`) fails, the orchestrator (`JobsService`) must catch this failure and take appropriate action, such as marking the job as `FAILED` and logging the error.

## 2. The Error Handling Mechanism

Our services use standard HTTP status codes and exceptions to communicate failures.

*   **Downstream Service (e.g., `DownloadService`)**: If an operation fails, it returns an `HTTPException` with a `4xx` or `5xx` status code.
*   **Orchestrator (`JobsService`)**: It makes API calls using an HTTP client. It must wrap these calls in a `try...except` block to catch the `HTTPException` from the downstream service.

```python
# Inside JobsService (conceptual example)

async def _orchestrate_archival(self, job: Job):
    try:
        # Step 1: Call Download Service
        await self.http_client.post(f"{DOWNLOAD_SERVICE_URL}/download", ...)

        # Step 2: Call Metadata Service
        await self.http_client.post(f"{METADATA_SERVICE_URL}/fetch", ...)

        # Step 3: Mark job as COMPLETED
        await self._update_job_status(job.id, JobStatus.COMPLETED)

    except httpx.HTTPStatusError as e:
        # If any downstream service returns an error, catch it
        error_detail = e.response.json().get("detail", str(e))

        # Mark the job as FAILED and log the reason
        await self._update_job_status(job.id, JobStatus.FAILED, error_message=error_detail)

        # Log the failure to the central LoggingService
        await self.log_error(f"Job {job.id} failed: {error_detail}")
```

## 3. How to Test Service Coordination Failures

Testing these failure modes is critical. The standard pattern is to use `unittest.mock.patch` to simulate an `HTTPException` from a downstream service and then verify that the orchestrator (`JobsService`) behaves as expected.

### Standard Testing Pattern

This pattern demonstrates how to test that the `JobsService` correctly handles a failure from the `DownloadService`.

```python
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException

@pytest.mark.integration
@pytest.mark.asyncio
async def test_job_fails_when_download_service_fails(self, jobs_service):
    """Verify that a job is marked as FAILED if the DownloadService returns an error."""

    # 1. Create a job that is ready to be executed
    job = await jobs_service.create_job(...)
    await jobs_service.update_job_status(job.id, JobStatus.PENDING)

    # 2. Patch the HTTP client used by JobsService to simulate a failure
    #    from the DownloadService.
    mock_failed_response = AsyncMock()
    mock_failed_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Download failed",
        request=AsyncMock(),
        response=AsyncMock(status_code=500, json=lambda: {"detail": "Internal Server Error"})
    )

    # Patch the 'post' method of the client instance within JobsService
    with patch.object(jobs_service.http_client, "post", side_effect=mock_failed_response) as mock_post:

        # 3. Execute the job. We expect it to fail gracefully.
        await jobs_service.execute_job(job.id)

        # 4. Verify the job's final status
        final_job_state = await jobs_service.get_job(job.id)
        assert final_job_state.status == JobStatus.FAILED
        assert "Internal Server Error" in final_job_state.error_message

        # 5. Verify that the call to the download service was attempted
        mock_post.assert_called_once()
```

## 4. Best Practices for Coordinated Error Handling

1.  **Idempotency**: Downstream services should be designed to be idempotent where possible. If an orchestrator retries a call after a transient failure, the downstream service should not perform the same operation twice (e.g., don't download the same file twice).

2.  **Clear Error Messages**: Downstream services must return clear, structured error messages in their `HTTPException` detail. The orchestrator should log this detail directly.

3.  **State Management**: The orchestrator is responsible for managing the state of the overall job. If a step fails, the job's status must be updated to `FAILED` to prevent it from being re-processed incorrectly.

4.  **No Nested Retries (in most cases)**: As a general rule, the orchestrator (`JobsService`) should handle the retries for the *entire workflow*. The downstream services (`DownloadService`, etc.) should fail fast and report the error, rather than implementing their own complex retry logic. This centralizes the retry policy and prevents cascading, unpredictable retry storms. The `ErrorRecoveryManager` should primarily be used by the orchestrating service.

By following these patterns, we can build a resilient, multi-service application that handles failures gracefully and provides clear, debuggable logs when things go wrong.
