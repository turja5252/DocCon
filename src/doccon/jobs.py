# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Dropbox job folders. Same remap as Databook Engine: keep the path after
Elite Integrity Serv Dropbox/<person>/, then replay it on this PC's person folder.
2.0 vs 2.1 Current Jobs does not matter."""

from __future__ import annotations

import json
import os
from pathlib import Path

TEAM_DROPBOX_FOLDER = "elite integrity serv dropbox"
JOB_BUCKETS = ("2.1 Current Jobs", "2.0 Current Jobs", "2.1 Completed Jobs")


def team_dropbox_tail(path: Path) -> Path | None:
    """Shared path after 'Elite Integrity Serv Dropbox/<person>/', or None."""
    parts = Path(path).parts
    for index, part in enumerate(parts):
        if part.casefold() != TEAM_DROPBOX_FOLDER:
            continue
        if index + 2 < len(parts):
            return Path(*parts[index + 2 :])
        return Path()
    return None


def team_dropbox_member_root(path: Path) -> Path | None:
    """The '<Dropbox>/<person>' folder that contains this path."""
    parts = Path(path).parts
    for index, part in enumerate(parts):
        if part.casefold() == TEAM_DROPBOX_FOLDER and index + 1 < len(parts):
            return Path(*parts[: index + 2])
    return None


def _dropbox_info_roots() -> list[Path]:
    info = Path(os.environ.get("LOCALAPPDATA", "")) / "Dropbox" / "info.json"
    if not info.is_file():
        return []
    try:
        raw = json.loads(info.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if not isinstance(raw, dict):
        return []
    roots: list[Path] = []
    for key in ("business", "personal"):
        entry = raw.get(key)
        if not isinstance(entry, dict):
            continue
        token = str(entry.get("path") or "").strip()
        if token:
            roots.append(Path(token))
    return roots


def local_team_dropbox_member_roots(hint: Path | None = None) -> list[Path]:
    """This PC's Elite Integrity Dropbox person-folders (Tanzim Nasir, Sarah Chan, …)."""
    roots: list[Path] = []
    seen: set[str] = set()

    def add(path: Path | None) -> None:
        if path is None or not str(path).strip():
            return
        parent = path.parent
        if parent.name.casefold() != TEAM_DROPBOX_FOLDER:
            return
        try:
            resolved = path.expanduser()
            if resolved.exists():
                resolved = resolved.resolve()
        except OSError:
            resolved = path
        if not resolved.is_dir():
            return
        key = os.path.normcase(str(resolved))
        if key in seen:
            return
        seen.add(key)
        roots.append(resolved)

    if hint is not None and str(hint).strip():
        add(team_dropbox_member_root(Path(hint)))

    for base in (*_dropbox_info_roots(), Path.home() / "Elite Integrity Serv Dropbox"):
        add(team_dropbox_member_root(base))
        try:
            if not base.is_dir():
                continue
            for child in base.iterdir():
                if child.is_dir() and not child.name.startswith("."):
                    add(child)
        except OSError:
            continue
    return roots


def dropbox_local_candidates(stored: Path, *, hint: Path | None = None) -> list[Path]:
    tail = team_dropbox_tail(stored)
    if tail is None:
        return []
    tails = _bucket_swapped_tails(tail)
    candidates: list[Path] = []
    seen: set[str] = set()
    for member_root in local_team_dropbox_member_roots(hint):
        for variant in tails:
            candidate = member_root / variant if str(variant) else member_root
            key = os.path.normcase(str(candidate))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def _bucket_swapped_tails(tail: Path) -> list[Path]:
    """2.0 Current Jobs on Sarah's PC is 2.1 Current Jobs on Tanzim's, same job underneath."""
    parts = tail.parts
    if not parts:
        return [tail]
    swap = {
        "2.0 current jobs": "2.1 Current Jobs",
        "2.1 current jobs": "2.0 Current Jobs",
    }
    other = swap.get(parts[0].casefold())
    variants = [tail]
    if other:
        variants.append(Path(other, *parts[1:]))
    return variants


def localize_dropbox_path(stored: str, *, hint: Path | None = None) -> str:
    """Rewrite another user's path onto this PC when that copy exists."""
    token = (stored or "").strip()
    if not token:
        return stored
    path = Path(token)
    if path.exists():
        try:
            return str(path.resolve())
        except OSError:
            return token
    for candidate in dropbox_local_candidates(path, hint=hint):
        if candidate.exists():
            try:
                return str(candidate.resolve())
            except OSError:
                return str(candidate)
    return token


def _is_job_folder(name: str, job_number: str) -> bool:
    token = name.strip()
    job = job_number.strip()
    if not token or not job:
        return False
    return token == job or token.startswith(job + " ")


def _job_bucket_dirs(member: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.is_dir():
            return
        key = os.path.normcase(str(path))
        if key in seen:
            return
        seen.add(key)
        found.append(path)

    for bucket in JOB_BUCKETS:
        add(member / bucket)
    try:
        for child in member.iterdir():
            if child.is_dir() and "current jobs" in child.name.casefold():
                add(child)
    except OSError:
        pass
    return found


def find_job_folder(job_number: str, *, hint: Path | None = None) -> Path | None:
    job = job_number.strip()
    for member in local_team_dropbox_member_roots(hint):
        for bucket in _job_bucket_dirs(member):
            try:
                children = list(bucket.iterdir())
            except OSError:
                continue
            for child in children:
                if child.is_dir() and _is_job_folder(child.name, job):
                    return child
    return None
