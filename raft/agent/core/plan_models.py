"""Minimal, safe Plan DSL models.

These models define a simple plan specification and perform strict validation
for URLs and filesystem paths, without any I/O side effects.

The DSL is intentionally small for Step 1 and focuses only on modeling and
validation. Execution, networking, and solvers are out of scope here.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, ClassVar, Literal, Optional, TypeAlias
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from pydantic.config import ConfigDict


ARTIFACTS_ROOT: str = "artifacts"

__all__ = [
    "ARTIFACTS_ROOT",
    "Fetch",
    "WriteFile",
    "Run",
    "Step",
    "Plan",
]


def _normalize_and_validate_artifact_path(value: str, *, field_name: str) -> str:
    """Normalize a path and ensure it is strictly contained under artifacts/.

    Rules:
    - Replace backslashes with '/'.
    - Use PurePosixPath for normalization.
    - Reject absolute paths and empty / '.' paths.
    - Path must start with 'artifacts/' and be strictly inside it (at least one
      subcomponent), must not contain any '..' traversal segments, and must not
      be a directory-looking target ending with '/'.
    - Return the normalized posix string.
    """
    # Replace Windows-style backslashes to avoid escape oddities
    value = value.replace("\\", "/").strip()

    # Forbid directory-looking paths that end with '/'
    if value.endswith("/"):
        raise ValueError(f"{field_name} must refer to a file and must not end with '/'")

    path = PurePosixPath(value)

    # Strip any '.' segments to keep paths canonical for audit logs
    if "." in path.parts:
        path = PurePosixPath(*[p for p in path.parts if p != "."])

    # No absolute paths
    if path.is_absolute():
        raise ValueError(f"{field_name} must be a relative path under '{ARTIFACTS_ROOT}/'")

    # No empty or current directory
    if str(path) in {"", "."}:
        raise ValueError(f"{field_name} must not be empty or '.'")

    # Must begin with artifacts and be strictly inside (at least two parts)
    parts = path.parts
    if len(parts) < 2 or parts[0] != ARTIFACTS_ROOT:
        raise ValueError(
            f"{field_name} must start with '{ARTIFACTS_ROOT}/' and be inside it"
        )

    # Reject traversal
    if ".." in parts:
        raise ValueError(f"{field_name} must not contain '..' traversal segments")

    # Return normalized POSIX string
    return str(path)


class _BaseModel(BaseModel):
    """Project-wide base model with strict-ish defaults: reject unknown fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Fetch(_BaseModel):
    """Fetch a remote resource over HTTP/HTTPS.

    Attributes:
        op: Discriminator literal "Fetch".
        url: HTTP/HTTPS URL.
        save_as: Optional relative path under artifacts/ where to save; uses the
            same normalization and containment rules as WriteFile.path. If not
            provided, the content is intended for ephemeral use by later steps.
    """

    op: Literal["Fetch"]
    url: str
    save_as: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        scheme = (parsed.scheme or "").lower()
        if scheme not in {"http", "https"}:
            raise ValueError("url scheme must be http or https")
        if not parsed.netloc:
            raise ValueError("url must include a network location (host)")
        return value

    @field_validator("save_as")
    @classmethod
    def _validate_save_as(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _normalize_and_validate_artifact_path(value, field_name="save_as")


class WriteFile(_BaseModel):
    """Write UTF-8 text to a file strictly contained under artifacts/.

    Attributes:
        op: Discriminator literal "WriteFile".
        path: Normalized relative path under artifacts/.
        content: Text content to write.
    """

    op: Literal["WriteFile"]
    path: str
    content: str

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _normalize_and_validate_artifact_path(value, field_name="path")


class Run(_BaseModel):
    """Run a predefined target.

    Attributes:
        op: Discriminator literal "Run".
        target: Only "governor.one_cycle" is allowed in this step.
    """

    op: Literal["Run"]
    target: Literal["governor.one_cycle"]


# Discriminated union for Step via the 'op' field
Step: TypeAlias = Annotated[Fetch | WriteFile | Run, Field(discriminator="op")]


class Plan(_BaseModel):
    """A plan contains a name, an optional token budget, and a list of steps.

    Validation constraints:
    - name: non-empty string after stripping.
    - tokens: optional int, if provided must be >= 0.
    - steps: non-empty list of valid Step instances.
    """

    name: str
    tokens: Optional[int] = Field(default=None, ge=0)
    steps: list[Step]

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = value.strip()
        if value == "":
            raise ValueError("name must be non-empty")
        return value

    @field_validator("steps")
    @classmethod
    def _validate_steps(cls, value: list[Step]) -> list[Step]:
        if not value:
            raise ValueError("steps must be non-empty")
        return value