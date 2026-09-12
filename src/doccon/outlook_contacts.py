# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Import Outlook GAL + Contacts into this-PC Settings saved TO/CC addresses.

Uses desktop Outlook COM (same family as Confirm mail). Prefers the
eliteintegrityservices.com account / doc.control mailbox; otherwise the signed-in
default. Does not send mail. Does not write Dropbox pack JSON.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from doccon.pep import DOC_CONTROL_FROM, email_line
from doccon.settings import load_settings, merge_saved_emails, save_settings

ELITE_MAIL_DOMAIN = "eliteintegrityservices.com"
OPEN_OUTLOOK = "Could not read Outlook addresses. Open Outlook on this PC, then try again."
_LIST_TIMEOUT_S = 120
_NOREPLY_LOCAL = ("noreply", "donotreply")


class OutlookContactsError(Exception):
    """Raised when Outlook is missing, not signed in, or COM fails."""


@dataclass(frozen=True)
class OutlookImportResult:
    saved_emails: tuple[str, ...]
    added: int


def pick_outlook_directory_account(
    addresses: Sequence[str],
    *,
    preferred: str = DOC_CONTROL_FROM,
    domain: str = ELITE_MAIL_DOMAIN,
) -> str:
    """doc.control if present, else any @eliteintegrityservices.com, else default."""
    want = (preferred or "").strip().casefold()
    domain_cf = (domain or "").strip().casefold()
    domain_hit = ""
    for addr in addresses:
        text = (addr or "").strip()
        if not text:
            continue
        key = text.casefold()
        if want and key == want:
            return text
        if not domain_hit and domain_cf and key.endswith("@" + domain_cf):
            domain_hit = text
    return domain_hit


def is_noreply_address(addr: str) -> bool:
    local = (addr or "").strip().split("@", 1)[0].casefold()
    compact = local.replace(".", "").replace("_", "").replace("-", "")
    return any(compact.startswith(token) for token in _NOREPLY_LOCAL)


def filter_import_addresses(values: object) -> tuple[str, ...]:
    """Addresses only. Skip empty, malformed, and noreply."""
    if isinstance(values, str):
        text = values
    elif isinstance(values, (list, tuple)):
        text = "; ".join(str(item or "") for item in values)
    else:
        return ()
    cleaned = tuple(part.strip() for part in email_line(text).split(";") if part.strip())
    return tuple(addr for addr in cleaned if not is_noreply_address(addr))


def list_outlook_addresses() -> tuple[str, ...]:
    """Pull SMTP addresses from that Outlook account’s GAL and Contacts."""
    dump = _read_outlook_directory()
    return filter_import_addresses(dump.get("emails"))


def import_saved_emails_from_outlook(
    *,
    lister: Callable[[], Sequence[str]] | None = None,
) -> OutlookImportResult:
    """Merge Outlook addresses into Settings saved TO/CC. Unique; keeps existing."""
    fetch = lister if lister is not None else list_outlook_addresses
    try:
        raw = fetch()
    except OutlookContactsError:
        raise
    except Exception as exc:
        raise OutlookContactsError(OPEN_OUTLOOK) from exc
    incoming = filter_import_addresses(raw)
    current = load_settings()
    merged = merge_saved_emails(current.saved_emails, incoming)
    added = len(merged) - len(current.saved_emails)
    if merged != current.saved_emails:
        save_settings(replace(current, saved_emails=merged))
    return OutlookImportResult(saved_emails=merged, added=added)


def _read_outlook_directory() -> dict[str, object]:
    if os.name != "nt":
        raise OutlookContactsError("Outlook import needs Windows Outlook. Open Outlook on this PC, then try again.")
    tmp_dir = Path(tempfile.mkdtemp(prefix="elite-doccon-outlook-contacts-"))
    script_path = tmp_dir / "list.ps1"
    payload_path = tmp_dir / "payload.json"
    out_path = tmp_dir / "addresses.json"
    payload = {
        "preferred": DOC_CONTROL_FROM,
        "domain": ELITE_MAIL_DOMAIN,
        "out": str(out_path),
    }
    try:
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        script_path.write_text(_list_script(str(payload_path)), encoding="utf-8")
        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-STA",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                ],
                capture_output=True,
                text=True,
                timeout=_LIST_TIMEOUT_S,
            )
        except FileNotFoundError as vis:
            raise OutlookContactsError(OPEN_OUTLOOK) from vis
        except subprocess.TimeoutExpired as vis:
            raise OutlookContactsError(
                "Outlook took too long to list addresses. Open Outlook, then try again."
            ) from vis
        if completed.returncode != 0 or not out_path.is_file():
            raise OutlookContactsError(OPEN_OUTLOOK)
        try:
            raw = json.loads(out_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, TypeError) as vis:
            raise OutlookContactsError(OPEN_OUTLOOK) from vis
        if not isinstance(raw, dict):
            raise OutlookContactsError(OPEN_OUTLOOK)
        return raw
    finally:
        try:
            for child in tmp_dir.glob("*"):
                child.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except OSError:
            pass


def _ps_lit(value: str) -> str:
    return json.dumps(str(value))


def _list_script(payload_path: str) -> str:
    return (
        "$ErrorActionPreference = 'Stop'\n"
        f"$payloadPath = {_ps_lit(payload_path)}\n"
        "$p = Get-Content -Raw -Encoding UTF8 $payloadPath | ConvertFrom-Json\n"
        "$outPath = [string]$p.out\n"
        "$preferred = ([string]$p.preferred).ToLower()\n"
        "$domain = ([string]$p.domain).ToLower()\n"
        "$outlook = $null\n"
        "try {\n"
        "  $outlook = [Runtime.InteropServices.Marshal]::GetActiveObject('Outlook.Application')\n"
        "} catch {\n"
        "  try {\n"
        "    $outlook = New-Object -ComObject Outlook.Application\n"
        "  } catch {\n"
        "    throw 'Open Outlook on this PC, then try Import from Outlook again.'\n"
        "  }\n"
        "}\n"
        "if ($outlook -eq $null) { throw 'Open Outlook on this PC, then try Import from Outlook again.' }\n"
        "$script:session = $outlook.Session\n"
        "$chosen = $null\n"
        "$domainAcc = $null\n"
        "foreach ($acc in @($script:session.Accounts)) {\n"
        "  $smtp = ''\n"
        "  try { $smtp = [string]$acc.SmtpAddress } catch { $smtp = '' }\n"
        "  if (-not $smtp) { try { $smtp = [string]$acc.UserName } catch { $smtp = '' } }\n"
        "  $key = $smtp.ToLower()\n"
        "  if ($preferred -and $key -eq $preferred) { $chosen = $acc; break }\n"
        "  if ($domainAcc -eq $null -and $domain -and $key.EndsWith('@' + $domain)) { $domainAcc = $acc }\n"
        "}\n"
        "if ($chosen -eq $null) { $chosen = $domainAcc }\n"
        "$store = $null\n"
        "if ($chosen -ne $null) { try { $store = $chosen.DeliveryStore } catch { $store = $null } }\n"
        "$storeId = ''\n"
        "if ($store -ne $null) { try { $storeId = [string]$store.StoreID } catch { $storeId = '' } }\n"
        "$script:seen = New-Object 'System.Collections.Generic.HashSet[string]'\n"
        "$script:found = New-Object 'System.Collections.Generic.List[string]'\n"
        "$script:lists = New-Object 'System.Collections.Generic.List[string]'\n"
        "function Add-Smtp([string]$raw) {\n"
        "  if (-not $raw) { return }\n"
        "  $matches = [regex]::Matches($raw, '[A-Z0-9._%+\\-]+@[A-Z0-9.\\-]+\\.[A-Z]{2,}', 'IgnoreCase')\n"
        "  foreach ($m in $matches) {\n"
        "    $addr = $m.Value.Trim().TrimEnd('>')\n"
        "    $local = (($addr -split '@')[0]).ToLower()\n"
        "    $compact = $local.Replace('.','').Replace('_','').Replace('-','')\n"
        "    if ($compact.StartsWith('noreply') -or $compact.StartsWith('donotreply')) { continue }\n"
        "    $key = $addr.ToLower()\n"
        "    if ($script:seen.Add($key)) { [void]$script:found.Add($addr) }\n"
        "  }\n"
        "}\n"
        "function Read-OneEntry($e) {\n"
        "  if ($e -eq $null) { return }\n"
        "  $got = $false\n"
        "  foreach ($tag in @(\n"
        "    'http://schemas.microsoft.com/mapi/proptag/0x39FE001F',\n"
        "    'http://schemas.microsoft.com/mapi/proptag/0x39FE001E'\n"
        "  )) {\n"
        "    try {\n"
        "      $pa = $e.PropertyAccessor.GetProperty($tag)\n"
        "      if ($pa) { Add-Smtp([string]$pa); $got = $true; break }\n"
        "    } catch {}\n"
        "  }\n"
        "  if (-not $got) {\n"
        "    try {\n"
        "      $eu = $e.GetExchangeUser()\n"
        "      if ($eu -ne $null) { Add-Smtp([string]$eu.PrimarySmtpAddress); $got = $true }\n"
        "    } catch {}\n"
        "  }\n"
        "  if (-not $got) {\n"
        "    try {\n"
        "      $dl = $e.GetExchangeDistributionList()\n"
        "      if ($dl -ne $null) { Add-Smtp([string]$dl.PrimarySmtpAddress); $got = $true }\n"
        "    } catch {}\n"
        "  }\n"
        "  if (-not $got) { try { Add-Smtp([string]$e.Address) } catch {} }\n"
        "}\n"
        "function Read-AddressList($list, [string]$label, [int]$cap) {\n"
        "  if ($list -eq $null) { return }\n"
        "  try { $entries = $list.AddressEntries } catch { return }\n"
        "  $n = 0\n"
        "  try { $n = [int]$entries.Count } catch { return }\n"
        "  if ($cap -gt 0 -and $n -gt $cap) { $n = $cap }\n"
        "  for ($i = 1; $i -le $n; $i++) {\n"
        "    try { Read-OneEntry ($entries.Item($i)) } catch {}\n"
        "  }\n"
        "  if ($label) { [void]$script:lists.Add($label) }\n"
        "}\n"
        "function Read-ContactsFolder($folder) {\n"
        "  if ($folder -eq $null) { return }\n"
        "  try { $items = $folder.Items } catch { return }\n"
        "  $n = 0\n"
        "  try { $n = [int]$items.Count } catch { return }\n"
        "  for ($i = 1; $i -le $n; $i++) {\n"
        "    try {\n"
        "      $it = $items.Item($i)\n"
        "      $class = 0\n"
        "      try { $class = [int]$it.Class } catch { $class = 0 }\n"
        "      if ($class -eq 7) { continue }\n"
        "      foreach ($num in @('1','2','3')) {\n"
        "        $addr = ''\n"
        "        $typ = ''\n"
        "        $addrProp = 'Email' + $num + 'Address'\n"
        "        $typeProp = 'Email' + $num + 'AddressType'\n"
        "        $idProp = 'Email' + $num + 'EntryID'\n"
        "        try { $addr = [string]$it.$($addrProp) } catch {}\n"
        "        try { $typ = [string]$it.$($typeProp) } catch {}\n"
        "        if ($typ -and $typ.ToUpper() -eq 'SMTP') { Add-Smtp $addr; continue }\n"
        "        if ($addr -and $addr.Contains('@')) { Add-Smtp $addr; continue }\n"
        "        try {\n"
        "          $eid = [string]$it.$($idProp)\n"
        "          if ($eid) { Read-OneEntry ($script:session.GetAddressEntryFromID($eid)) }\n"
        "        } catch {}\n"
        "      }\n"
        "    } catch {}\n"
        "  }\n"
        "  try {\n"
        "    foreach ($sub in @($folder.Folders)) { Read-ContactsFolder $sub }\n"
        "  } catch {}\n"
        "}\n"
        "try {\n"
        "  Read-AddressList ($script:session.GetGlobalAddressList()) 'Global Address List' 8000\n"
        "} catch {}\n"
        "try {\n"
        "  foreach ($al in @($script:session.AddressLists)) {\n"
        "    $typ = -1\n"
        "    $name = ''\n"
        "    try { $typ = [int]$al.AddressListType } catch {}\n"
        "    try { $name = [string]$al.Name } catch {}\n"
        "    if ($typ -eq 0 -or $name -match 'Global Address List') {\n"
        "      if (@($script:lists) -notcontains 'Global Address List') {\n"
        "        Read-AddressList $al 'Global Address List' 8000\n"
        "      }\n"
        "    }\n"
        "    if ($typ -eq 2) {\n"
        "      if ($storeId) {\n"
        "        $folder = $null\n"
        "        try { $folder = $al.GetContactsFolder() } catch { $folder = $null }\n"
        "        if ($folder -ne $null) {\n"
        "          $fid = ''\n"
        "          try { $fid = [string]$folder.StoreID } catch { $fid = '' }\n"
        "          if ($fid -and $fid -ne $storeId) { continue }\n"
        "        }\n"
        "      }\n"
        "      Read-AddressList $al ($(if ($name) { $name } else { 'Contacts' })) 0\n"
        "    }\n"
        "  }\n"
        "} catch {}\n"
        "$olFolderContacts = 10\n"
        "$contacts = $null\n"
        "if ($store -ne $null) {\n"
        "  try { $contacts = $store.GetDefaultFolder($olFolderContacts) } catch { $contacts = $null }\n"
        "}\n"
        "if ($contacts -eq $null) {\n"
        "  try { $contacts = $script:session.GetDefaultFolder($olFolderContacts) } catch { $contacts = $null }\n"
        "}\n"
        "if ($contacts -ne $null) {\n"
        "  Read-ContactsFolder $contacts\n"
        "  if (@($script:lists) -notcontains 'Contacts') { [void]$script:lists.Add('Contacts') }\n"
        "}\n"
        "$emailParts = New-Object System.Collections.Generic.List[string]\n"
        "foreach ($addr in $script:found) {\n"
        "  $esc = ([string]$addr).Replace('\\','\\\\').Replace('\"','\\\"')\n"
        "  [void]$emailParts.Add('\"' + $esc + '\"')\n"
        "}\n"
        "$listParts = New-Object System.Collections.Generic.List[string]\n"
        "foreach ($name in $script:lists) {\n"
        "  $esc = ([string]$name).Replace('\\','\\\\').Replace('\"','\\\"')\n"
        "  [void]$listParts.Add('\"' + $esc + '\"')\n"
        "}\n"
        "$json = '{\"emails\":[' + ($emailParts -join ',') + '],\"lists\":[' + ($listParts -join ',') + ']}'\n"
        "[System.IO.File]::WriteAllText($outPath, $json, [System.Text.UTF8Encoding]::new($false))\n"
    )
