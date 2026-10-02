# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_FOLDER = "EliteIntegrity"
DOC_CON_FOLDER = "DocCon"


def user_data_dir() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / APP_FOLDER / DOC_CON_FOLDER


def settings_path() -> Path:
    return user_data_dir() / "settings.json"


def install_dir() -> Path:
    """Folder that holds Elite DocCon.exe, or the suite folder when running from source.

    Dropbox syncs this folder between PCs. It is not LOCALAPPDATA.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def mail_formats_path() -> Path:
    return install_dir() / "mail-formats.json"
