from __future__ import annotations

from pathlib import PurePath
from typing import Annotated, List, Literal, Set, Union
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Public constant for allowed run targets so tests or callers can import it
ALLOWED_RUN_TARGETS: Set[str] = {"governor.one_cycle"}

# Optional guardrail for UI-facing flows: cap write content size (in bytes)
MAX_WRITEFILE_CONTENT_BYTES: int = 1_000_000


class PlanBase(BaseModel):
    """Common Pydantic configuration for plan models.

    - Forbid extra/unknown fields for strictness.
    """

    model_config = ConfigDict(extra="forbid")


class Fetch(PlanBase):
    """Fetch a remote resource.

    - url: must be http or https and include a host.
    """

    op: Literal["Fetch"]
    url: str

    @field_validator("url")
    @classmethod
    def _validate_http_https(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be http/https and include a host")
        return value


class WriteFile(PlanBase):
    """Write content to a file within the artifacts/ directory.

    - path: must be a relative path inside artifacts/ (no absolute paths, no '..').
    - content: file contents to write.
    """

    op: Literal["WriteFile"]
    path: str
    content: str

    @field_validator("path")
    @classmethod
    def _validate_artifacts_relative(cls, value: str) -> str:
        # Reject NUL byte explicitly
        if "\x00" in value:
            raise ValueError("path must not contain NUL bytes")
        # Normalize Windows-style separators first to keep behavior consistent across platforms
        normalized = value.replace("\\", "/")
        if "\x00" in normalized:
            raise ValueError("path must not contain NUL bytes")

        path_obj = PurePath(normalized)
        if path_obj.is_absolute():
            raise ValueError("path must be relative")
        if ".." in path_obj.parts:
            raise ValueError("path must not contain '..'")
        parts = path_obj.parts
        if not parts or parts[0] != "artifacts":
            raise ValueError("path must be inside artifacts/")
        if len(parts) == 1:
            # path == "artifacts" is a directory, not a file inside
            raise ValueError("path must reference a file inside artifacts/")
        # Return normalized so stored model consistently uses forward slashes
        return normalized

    @field_validator("content")
    @classmethod
    def _validate_content_size(cls, value: str) -> str:
        # len of utf-8 bytes to approximate payload size; stricter than len(chars)
        if len(value.encode("utf-8")) > MAX_WRITEFILE_CONTENT_BYTES:
            raise ValueError(
                f"content too large; limit is {MAX_WRITEFILE_CONTENT_BYTES} bytes"
            )
        return value


class Run(PlanBase):
    """Run an allowed target.

    - target: must be one of the allowed values.
    """

    op: Literal["Run"]
    target: str

    @field_validator("target")
    @classmethod
    def _validate_target(cls, value: str) -> str:
        if value not in ALLOWED_RUN_TARGETS:
            allowed_list = ", ".join(sorted(ALLOWED_RUN_TARGETS))
            raise ValueError(f"target must be one of: [{allowed_list}]")
        return value


# Discriminated union over 'op'
Step = Annotated[Union[Fetch, WriteFile, Run], Field(discriminator="op")]


class Plan(PlanBase):
    """A plan consisting of a sequence of steps."""

    steps: List[Step]


__all__ = [
    "ALLOWED_RUN_TARGETS",
    "MAX_WRITEFILE_CONTENT_BYTES",
    "PlanBase",
    "Fetch",
    "WriteFile",
    "Run",
    "Step",
    "Plan",
]