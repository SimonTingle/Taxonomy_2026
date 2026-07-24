"""Parse and normalise folder paths from a SharePoint export."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class ParsedPath:
    """Structured view of a single file's path."""

    levels: List[str] = field(default_factory=list)  # ordered folder levels
    filename: str = ""                                # leaf file name (no folders)
    stem: str = ""                                    # file name without extension
    extension: str = ""                               # lower-case, incl. dot (".pdf")

    @property
    def depth(self) -> int:
        return len(self.levels)


def _normalise(raw: str) -> str:
    """Unify separators and strip protocol / host / leading slashes."""
    if raw is None:
        return ""
    text = str(raw).strip().replace("\\", "/")
    # Drop a URL scheme + host if the path is a full ServerUrl (e.g. https://site/...).
    if "://" in text:
        text = text.split("://", 1)[1]
        text = text.split("/", 1)[1] if "/" in text else ""
    text = text.strip("/")
    # Drop a leading SharePoint container segment (/sites/<Site>/... or /personal/...)
    # so the site/library folder becomes level_0.
    parts = text.split("/")
    if parts and parts[0].lower() in ("sites", "personal", "teams"):
        parts = parts[1:]
    return "/".join(parts)


def parse_path(raw_path: str, filename: str | None = None) -> ParsedPath:
    """Split a path into ordered folder levels + leaf filename + extension.

    `filename` may be supplied separately (SharePoint exports usually have both a
    path column and a name column); if the path already ends with the filename it
    is not duplicated.
    """
    text = _normalise(raw_path)
    parts = [p for p in text.split("/") if p]

    leaf = (filename or "").strip()
    if leaf:
        # If the path ends with the given filename, treat that as the leaf.
        if parts and parts[-1].lower() == leaf.lower():
            parts = parts[:-1]
    elif parts:
        # No explicit filename: assume the last segment with an extension is the file.
        if "." in parts[-1]:
            leaf = parts[-1]
            parts = parts[:-1]

    stem, ext = os.path.splitext(leaf)
    return ParsedPath(
        levels=parts,
        filename=leaf,
        stem=stem,
        extension=ext.lower(),
    )
