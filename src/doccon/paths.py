# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import os
from pathlib import Path

APP_FOLDER = "EliteIntegrity"
DOC_CON_FOLDER = "DocCon"


def user_data_dir() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / APP_FOLDER / DOC_CON_FOLDER


def settings_path() -> Path:
    return user_data_dir() / "settings.json"
