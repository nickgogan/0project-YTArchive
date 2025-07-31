# Test Structure and Organization Guide

This guide defines the standards for organizing the test suite in the YTArchive project. A well-organized test suite is easier to navigate, maintain, and run, which is critical for ensuring code quality.

## 1. Test Directory Hierarchy

The `tests/` directory mirrors the structure of the main `services/` directory. This co-location principle makes it easy to find tests related to a specific piece of code.

```
YTArchive/
├── services/                 # Source code
│   ├── download/
│   └── ...
└── tests/                    # Test code
    ├── common/               # Shared test utilities
    ├── download/             # Tests for the Download service
    └── ...
```

### Key Directories

*   **`tests/`**: The root directory for all tests. `pytest` is configured to discover tests starting from here.
*   **`tests/common/`**: Contains shared utilities and fixtures used across multiple test files. Examples include `temp_utils.py` for managing temporary directories and `memory_leak_detection.py` for the memory profiling framework.
*   **`tests/<service_name>/`**: Each service has a corresponding test directory (e.g., `tests/download/`, `tests/jobs/`). This directory holds all tests primarily related to that service.
*   **`tests/integration/`**: This directory is special. It contains tests that verify the interaction and coordination between *two or more* services.
*   **`tests/memory/`**: Contains all memory leak detection tests, which are resource-intensive and have a specific focus.

## 2. Test Categories and Markers

We use `pytest` markers to categorize tests based on their scope and purpose. These markers are defined in `pytest.ini` and are essential for running specific subsets of the test suite.

| Marker | Directory | Description |
| :--- | :--- | :--- |
| `@pytest.mark.unit` | `tests/<service>/` | Tests a single function or class in complete isolation. No network, I/O, or other services are involved. All dependencies are mocked. |
| `@pytest.mark.service` | `tests/<service>/` | Tests a single service's API endpoints. External dependencies (other services, YouTube API) are mocked. Focuses on the service's contract. |
| `@pytest.mark.integration`| `tests/integration/` | Tests the interaction between two or more services. Uses real service instances with minimal, targeted mocking (e.g., external APIs). |
| `@pytest.mark.e2e` | `tests/integration/` | Tests a complete user workflow from start to finish, often starting from the CLI. Mocks only the outermost boundaries (e.g., YouTube API). |
| `@pytest.mark.cli` | `tests/cli/` | Tests the command-line interface, including argument parsing, command execution, and user output. |
| `@pytest.mark.memory` | `tests/memory/` | Specifically designed to detect memory leaks. These tests are often long-running and resource-intensive. |
| `@pytest.mark.performance`| `tests/` (various) | Benchmarks the performance (e.g., response time, throughput) of specific components or workflows. |

## 3. Where to Place New Tests: A Decision Guide

When adding a new test, follow these steps to determine its location and markers:

1.  **What is the primary subject of the test?**
    *   If it's a single, isolated function/class -> **Unit Test**.
    *   If it's a single service's API -> **Service Test**.
    *   If it's the interaction between multiple services -> **Integration Test**.
    *   If it's a full user story (e.g., "download a video") -> **E2E Test**.
    *   If it's the command-line tool itself -> **CLI Test**.
    *   If it's checking for memory leaks -> **Memory Test**.

2.  **Determine the Directory:**
    *   For **Unit** and **Service** tests, place the test file in the directory corresponding to the service under test (e.g., a test for `JobsService` goes in `tests/jobs/`).
    *   For **Integration** and **E2E** tests, place the file in `tests/integration/`.
    *   For **CLI** tests, place the file in `tests/cli/`.
    *   For **Memory** tests, place the file in `tests/memory/`.

3.  **Add the Correct Marker(s):**
    *   Apply the primary marker (e.g., `@pytest.mark.unit`).
    *   You can apply multiple markers if applicable (e.g., a service test that is also a performance benchmark could have both `@pytest.mark.service` and `@pytest.mark.performance`).

### Examples

*   **Scenario**: You wrote a new helper function in `services/storage/main.py` to calculate directory sizes.
    *   **Decision**: This is a single, isolatable function.
    *   **Location**: `tests/storage/test_storage_service.py` (or a new `test_utils.py`).
    *   **Marker**: `@pytest.mark.unit`

*   **Scenario**: You want to verify that the `JobsService` correctly creates a job when its `/api/v1/jobs/create` endpoint is called.
    *   **Decision**: This tests a single service's API contract.
    *   **Location**: `tests/jobs/test_jobs_service.py`
    *   **Marker**: `@pytest.mark.service`

*   **Scenario**: You need to test that when `JobsService` creates a download job, the `DownloadService` correctly starts the download and the `StorageService` creates the right directory.
    *   **Decision**: This tests the coordination of three services.
    *   **Location**: `tests/integration/test_archival_workflow.py`
    *   **Marker**: `@pytest.mark.integration`

## 4. Running Specific Test Categories

Using markers allows you to efficiently run only the tests you need.

```bash
# Run only the fast unit tests
pytest -m unit

# Run all tests for a specific service (service and unit tests)
pytest tests/download/

# Run only the integration tests
pytest -m integration

# Run all tests EXCEPT memory tests
pytest -m "not memory"

# Run all cli and unit tests
pytest -m "cli or unit"
```

## 5. Test Naming and Structure Conventions

*   **File Names**: Must start with `test_` (e.g., `test_jobs_service.py`).
*   **Class Names**: Must start with `Test` (e.g., `TestJobsService`). Tests do not have to be in classes, but it's a good way to group related tests.
*   **Function Names**: Must start with `test_` (e.g., `test_create_job_successfully`).

## 6. Test Auditing

To ensure these standards are followed, the project includes a test audit script:

*   **`scripts/test_audit.py`**

This script statically analyzes the test suite to verify that all tests are correctly categorized with a marker. It can be integrated into CI/CD pipelines to enforce organizational standards and prevent uncategorized tests from being added to the codebase. Always make sure your new tests are discoverable by this script.
