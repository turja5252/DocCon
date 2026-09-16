# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Test-suite guards. Nothing here may touch a live job folder or the real log."""
from __future__ import annotations

import pytest

from doccon.diag import LOG_DIR_ENV


@pytest.fixture(autouse=True)
def _doccon_log_to_tmp(tmp_path, monkeypatch):
    """Keep pytest out of %LOCALAPPDATA%\\EliteIntegrity\\DocCon\\doccon.log.

    Test lines were interleaving with the operator's live session, which buried
    the run he was asking about. The env var is inherited, so the paste and
    drop_host children a test spawns land in the same tmp folder.
    """
    folder = tmp_path / "log" / "EliteIntegrity" / "DocCon"
    monkeypatch.setenv(LOG_DIR_ENV, str(folder))
    return folder
