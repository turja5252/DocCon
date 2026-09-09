# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import json
from dataclasses import dataclass

from doccon.paths import settings_path, user_data_dir
from doccon.register import DEFAULT_PROJECT, DEFAULT_SITE

ALLOWED_KEYS = ("site", "email", "project_key")


@dataclass
class AppSettings:
    site: str = DEFAULT_SITE
    email: str = ""
    project_key: str = DEFAULT_PROJECT


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
    settings = AppSettings(site=site, email=email, project_key=project_key)
    if leaked:
        save_settings(settings)
    return settings


def save_settings(settings: AppSettings) -> None:
    user_data_dir().mkdir(parents=True, exist_ok=True)
    payload = {
        "site": settings.site.strip().rstrip("/"),
        "email": settings.email.strip(),
        "project_key": settings.project_key.strip() or DEFAULT_PROJECT,
    }
    settings_path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
