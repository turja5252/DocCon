# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Jira API token in Windows Credential Manager. Never Dropbox, never settings.json."""

from __future__ import annotations

import keyring

SERVICE = "EliteDocCon-Jira"


def load_token(email: str) -> str:
    account = (email or "").strip()
    if not account:
        return ""
    try:
        return keyring.get_password(SERVICE, account) or ""
    except keyring.errors.KeyringError:
        return ""


def save_token(email: str, token: str) -> None:
    account = (email or "").strip()
    secret = (token or "").strip()
    if not account:
        raise ValueError("Email is required to store a Jira token.")
    if not secret:
        raise ValueError("Token is empty.")
    keyring.set_password(SERVICE, account, secret)


def delete_token(email: str) -> None:
    account = (email or "").strip()
    if not account:
        return
    try:
        keyring.delete_password(SERVICE, account)
    except keyring.errors.PasswordDeleteError:
        pass
