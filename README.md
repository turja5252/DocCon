# Elite DocCon Suite

Desktop transmittal workstation. Slice 1: Jira settings + load a job’s drawing register.

## Run

Double-click **`Run DocCon (source).bat`** in this folder (same pattern as Databook Engine).

Or from a terminal:

```text
python -m pip install -e ".[dev]"
python -m pytest
python -m doccon
```

1. **Settings** — site, Atlassian email, paste API token (Windows Credential Manager, not Dropbox).
2. **Test connection**.
3. **Job Number** — e.g. `2026-Tanzim` — **Load**. Edit Next on drawings, tick Pack, **Confirm…**. That writes Jira, files the cover PDF, zips the pack, and opens an Outlook draft (Send it in Outlook). Cover FROM/TO/CC and project line come from the PEP in `7.0 Sales` (**Locate PEP…** if it is missing). Shop and Field are on the bar but not wired yet.

Email send from Outlook is still a person clicking Send. Do not run File and email against a live job (075).
