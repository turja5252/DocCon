# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from doccon.paths import settings_path, user_data_dir
from doccon.pep import email_line
from doccon.register import DEFAULT_PROJECT, DEFAULT_SITE

# 1.36: ignore pre-1.31 fat board_col_px (e.g. 564px Description) once, then save again.
# 1.76: PDF column grows for Preview beside Open.
BOARD_LAYOUT_REV = 138

ALLOWED_KEYS = (
    "site",
    "email",
    "project_key",
    "saved_emails",
    "field_to",
    "field_cc",
    "shop_to",
    "shop_cc",
    "last_locate_dir",
    "board_col_px",
    "board_col_names",
    "board_hidden_cols",
    "board_col_order",
    "board_layout_rev",
    "job_folders",
    "shop_ifc_folders",
)


@dataclass
class AppSettings:
    site: str = DEFAULT_SITE
    email: str = ""
    project_key: str = DEFAULT_PROJECT
    saved_emails: tuple[str, ...] = ()
    field_to: tuple[str, ...] = ()
    field_cc: tuple[str, ...] = ()
    shop_to: tuple[str, ...] = ()
    shop_cc: tuple[str, ...] = ()
    last_locate_dir: str = ""
    board_col_px: tuple[int, ...] = ()
    board_col_names: tuple[str, ...] = ()
    board_hidden_cols: tuple[str, ...] = ()
    board_col_order: tuple[str, ...] = ()
    board_layout_rev: int = 0
    job_folders: dict[str, str] = field(default_factory=dict)
    shop_ifc_folders: dict[str, str] = field(default_factory=dict)


def load_settings() -> AppSettings:
    path = settings_path()
    if not path.is_file():
        return AppSettings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return AppSettings()
    if not isinstance(raw, dict):
        return AppSettings()
    leaked = any(key in raw for key in ("token", "api_token", "password"))
    if leaked:
        raw = {k: v for k, v in raw.items() if k in ALLOWED_KEYS}
    site = str(raw.get("site") or DEFAULT_SITE).strip() or DEFAULT_SITE
    email = str(raw.get("email") or "").strip()
    project_key = str(raw.get("project_key") or DEFAULT_PROJECT).strip() or DEFAULT_PROJECT
    settings = AppSettings(
        site=site,
        email=email,
        project_key=project_key,
        saved_emails=normalize_saved_emails(raw.get("saved_emails")),
        field_to=normalize_saved_emails(raw.get("field_to")),
        field_cc=normalize_saved_emails(raw.get("field_cc")),
        shop_to=normalize_saved_emails(raw.get("shop_to")),
        shop_cc=normalize_saved_emails(raw.get("shop_cc")),
        last_locate_dir=str(raw.get("last_locate_dir") or "").strip(),
        board_col_px=_board_col_px(raw.get("board_col_px")),
        board_col_names=_board_col_names(raw.get("board_col_names")),
        board_hidden_cols=_board_col_names(raw.get("board_hidden_cols")),
        board_col_order=_board_col_names(raw.get("board_col_order")),
        board_layout_rev=_board_layout_rev(raw.get("board_layout_rev")),
        job_folders=_job_folders(raw.get("job_folders")),
        shop_ifc_folders=_job_folders(raw.get("shop_ifc_folders")),
    )
    if leaked:
        save_settings(settings)
    return settings


def save_settings(settings: AppSettings) -> None:
    user_data_dir().mkdir(parents=True, exist_ok=True)
    payload = {
        "site": settings.site.strip().rstrip("/"),
        "email": settings.email.strip(),
        "project_key": settings.project_key.strip() or DEFAULT_PROJECT,
        "saved_emails": list(normalize_saved_emails(settings.saved_emails)),
        "field_to": list(normalize_saved_emails(settings.field_to)),
        "field_cc": list(normalize_saved_emails(settings.field_cc)),
        "shop_to": list(normalize_saved_emails(settings.shop_to)),
        "shop_cc": list(normalize_saved_emails(settings.shop_cc)),
        "last_locate_dir": settings.last_locate_dir.strip(),
        "board_col_px": list(settings.board_col_px),
        "board_col_names": list(settings.board_col_names),
        "board_hidden_cols": list(settings.board_hidden_cols),
        "board_col_order": list(settings.board_col_order),
        "board_layout_rev": int(settings.board_layout_rev),
        "job_folders": dict(_job_folders(settings.job_folders)),
        "shop_ifc_folders": dict(_job_folders(settings.shop_ifc_folders)),
    }
    settings_path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def normalize_saved_emails(values: object) -> tuple[str, ...]:
    if isinstance(values, str):
        text = values
    elif isinstance(values, (list, tuple)):
        text = "; ".join(str(item or "") for item in values)
    else:
        return ()
    line = email_line(text)
    if not line:
        return ()
    return tuple(part.strip() for part in line.split(";") if part.strip())


def append_email(current: str, added: str) -> str:
    """Join cover TO/CC with extra addresses. Unique, semicolon separated."""
    return email_line("; ".join(part for part in (current, added) if (part or "").strip()))


def merge_saved_emails(existing: object, incoming: object) -> tuple[str, ...]:
    """Keep saved TO/CC addresses; append unique incoming. Does not wipe."""
    return normalize_saved_emails([*normalize_saved_emails(existing), *normalize_saved_emails(incoming)])


def _board_col_px(values: object) -> tuple[int, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    out: list[int] = []
    for item in values:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            return ()
    return tuple(out)


def _board_col_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _board_layout_rev(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def hidden_column_names() -> set[str]:
    """Column headings this PC has turned off. Empty means show every column."""
    return {name for name in load_settings().board_hidden_cols if name}


def column_order() -> list[str]:
    """Heading order on this PC. Empty means the built-in order."""
    return [name for name in load_settings().board_col_order if name]


def remember_board_order(names: list[str]) -> None:
    """Remember the heading order on this PC, for every job."""
    stored = tuple(dict.fromkeys(str(name) for name in names if str(name).strip()))
    settings = load_settings()
    if settings.board_col_order == stored:
        return
    save_settings(replace(settings, board_col_order=stored))


def remember_board_hidden(names: list[str]) -> None:
    """Remember which headings are hidden on this PC, for every job."""
    stored = tuple(dict.fromkeys(str(name) for name in names if str(name).strip()))
    settings = load_settings()
    if settings.board_hidden_cols == stored:
        return
    save_settings(replace(settings, board_hidden_cols=stored))


def remember_board_col_px(values: list[int], names: list[str] | None = None) -> None:
    """Remember sash widths on this PC, tied to the column headings."""
    stored = tuple(int(v) for v in values)
    stored_names = tuple(str(name) for name in (names or []))
    if stored_names and len(stored_names) != len(stored):
        stored_names = ()
    settings = load_settings()
    if (
        settings.board_col_px == stored
        and settings.board_col_names == stored_names
        and settings.board_layout_rev == BOARD_LAYOUT_REV
    ):
        return
    save_settings(
        replace(
            settings,
            board_col_px=stored,
            board_col_names=stored_names,
            board_layout_rev=BOARD_LAYOUT_REV,
        )
    )


def locate_start_dir(fallback: str = "") -> str:
    token = load_settings().last_locate_dir.strip()
    if token and Path(token).is_dir():
        return token
    return fallback


def _job_folders(values: object) -> dict[str, str]:
    if not isinstance(values, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in values.items():
        job = str(key or "").strip()
        token = str(value or "").strip()
        if job and token:
            out[job] = token
    return out


def remembered_job_folder(job_number: str) -> Path | None:
    job = job_number.strip()
    if not job:
        return None
    token = load_settings().job_folders.get(job, "").strip()
    if not token:
        return None
    path = Path(token)
    return path if path.is_dir() else None


def remembered_shop_folder(job_number: str) -> Path | None:
    job = job_number.strip()
    if not job:
        return None
    token = load_settings().shop_ifc_folders.get(job, "").strip()
    if not token:
        return None
    path = Path(token)
    return path if path.is_dir() else None


def remember_shop_folder(job_number: str, folder: Path) -> None:
    job = job_number.strip()
    path = Path(folder)
    if not job or not path.is_dir():
        return
    try:
        token = str(path.resolve())
    except OSError:
        token = str(path)
    settings = load_settings()
    mapped = dict(settings.shop_ifc_folders)
    if mapped.get(job) == token:
        return
    mapped[job] = token
    save_settings(replace(settings, shop_ifc_folders=mapped))


def remember_job_folder(job_number: str, folder: Path) -> None:
    job = job_number.strip()
    path = Path(folder)
    if not job or not path.is_dir():
        return
    try:
        token = str(path.resolve())
    except OSError:
        token = str(path)
    settings = load_settings()
    mapped = dict(settings.job_folders)
    if mapped.get(job) == token:
        return
    mapped[job] = token
    save_settings(replace(settings, job_folders=mapped))


def remember_locate_dir(path: Path) -> None:
    folder = Path(path)
    if folder.is_file():
        folder = folder.parent
    if not folder.is_dir():
        return
    settings = load_settings()
    token = str(folder)
    if settings.last_locate_dir == token:
        return
    save_settings(replace(settings, last_locate_dir=token))
