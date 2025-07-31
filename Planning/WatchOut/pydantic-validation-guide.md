# Pydantic Model Validation and Serialization Guide

This guide provides standards and solutions for common Pydantic validation and serialization issues encountered in the YTArchive project, particularly concerning non-standard data types like `pathlib.Path` and `datetime`.

## 1. Core Problem: Non-JSON-Serializable Types

Pydantic, and the underlying FastAPI framework, rely on data types that can be easily converted to and from JSON. When we use complex Python objects like `pathlib.Path` or `datetime.datetime` in our Pydantic models, we often encounter two types of errors:

1.  **`pydantic.ValidationError`**: Occurs during model creation or validation if the input data cannot be coerced into the specified type.
2.  **`TypeError: Object of type X is not JSON serializable`**: Occurs during the serialization phase when trying to convert the Pydantic model into a JSON response for an API endpoint.

## 2. Solution for `pathlib.Path` Objects

**Problem**: `pathlib.Path` objects are used for filesystem operations but are not valid JSON types. Passing them directly into Pydantic models that will be part of an API request or response will cause a `ValidationError`.

**Context**: This issue was frequently observed in our E2E and integration tests, where temporary directories (which are `Path` objects) were passed into a `DownloadRequest` model.

**Solution**: Always convert `pathlib.Path` objects to strings before passing them to a Pydantic model.

### Incorrect Pattern
```python
# ❌ WRONG: This will raise a pydantic.ValidationError
from pathlib import Path
from pydantic import BaseModel

class DownloadRequest(BaseModel):
    video_id: str
    output_path: Path # Pydantic will try to validate this as a Path object

temp_dir = Path("/tmp/my_test_dir")

# This line will fail because the model is used in an API context
# that expects JSON-compatible types.
request = DownloadRequest(video_id="test_video", output_path=temp_dir)
```

### Correct Pattern
```python
# ✅ CORRECT: Convert the Path object to a string
from pathlib import Path
from pydantic import BaseModel

class DownloadRequest(BaseModel):
    video_id: str
    # The model can still expect a string that represents a path
    output_path: str

temp_dir = Path("/tmp/my_test_dir")

# Convert to string before creating the model instance
request = DownloadRequest(video_id="test_video", output_path=str(temp_dir))

# The string path is JSON-serializable and works correctly in API calls.
```

**Best Practice**: Your services' internal logic should be responsible for converting the string path back into a `Path` object for filesystem operations:

```python
# Inside a service method
async def _process_download(request: DownloadRequest):
    # Convert string back to Path object for internal use
    output_directory = Path(request.output_path)

    if not output_directory.exists():
        output_directory.mkdir(parents=True)
    # ... proceed with filesystem operations
```

## 3. Solution for `datetime` Objects

**Problem**: Standard `datetime.datetime` objects are not inherently JSON serializable. When a Pydantic model containing a `datetime` field is returned from a FastAPI endpoint, it can cause a `TypeError`.

**Context**: This issue was identified in the `StorageService` when returning metadata that included timestamps.

**Solution**: Use Pydantic's built-in serialization logic by calling `.model_dump(mode="json")` before sending the data as a response. FastAPI often handles this automatically for response models, but for manual serialization or nested models, this is the explicit solution.

### Incorrect Pattern
```python
# ❌ WRONG: This can lead to a TypeError in some contexts
import json
from datetime import datetime
from pydantic import BaseModel

class VideoMetadata(BaseModel):
    video_id: str
    saved_at: datetime

metadata = VideoMetadata(video_id="test_video", saved_at=datetime.now())

# This manual conversion will fail
try:
    json_response = json.dumps(metadata.model_dump())
except TypeError as e:
    print(f"Error: {e}") # Will print "Object of type datetime is not JSON serializable"
```

### Correct Pattern
```python
# ✅ CORRECT: Use Pydantic's built-in JSON-mode serialization
import json
from datetime import datetime
from pydantic import BaseModel

class VideoMetadata(BaseModel):
    video_id: str
    saved_at: datetime

metadata = VideoMetadata(video_id="test_video", saved_at=datetime.now())

# .model_dump(mode="json") converts datetime to its ISO 8601 string representation
json_compatible_dict = metadata.model_dump(mode="json")

# This now works perfectly
json_response = json.dumps(json_compatible_dict)

# Output: '{"video_id": "test_video", "saved_at": "2025-07-30T12:30:00.123456"}'
```

**Best Practice**: When returning Pydantic models directly from FastAPI endpoints, the framework typically handles this correctly. However, if you are constructing a response manually or nesting Pydantic models within a dictionary, always use `.model_dump(mode="json")` to ensure all fields are properly serialized.

## 4. Advanced Validation with `@model_validator`

For more complex scenarios where fields depend on each other, use Pydantic's validators.

**Example**: In our `RetryConfig`, we need to ensure that `max_delay` is always greater than or equal to `base_delay`.

```python
# From services/error_recovery/types.py
from pydantic import BaseModel, Field, model_validator

class RetryConfig(BaseModel):
    max_attempts: int = Field(default=3)
    base_delay: float = Field(default=1.0)
    max_delay: float = Field(default=300.0)

    @model_validator(mode="after")
    def validate_delay_relationship(self):
        """Ensure max_delay is not smaller than base_delay."""
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be greater than or equal to base_delay")
        return self

# This will now raise a ValidationError:
# RetryConfig(base_delay=10.0, max_delay=5.0)
```

This pattern is excellent for enforcing internal consistency within your data models.

## Summary of Recommendations

1.  **For `pathlib.Path`**: Always convert to `str` **before** creating the Pydantic model instance. The model itself should be defined with `output_path: str`.
2.  **For `datetime`**: When manually serializing, always use `.model_dump(mode="json")` to convert the model to a JSON-compatible dictionary. Rely on FastAPI's automatic conversion when returning models as a `response_model`.
3.  **For Inter-field Logic**: Use the `@model_validator` decorator to enforce complex validation rules between fields within a single model.
