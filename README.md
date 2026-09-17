# Elite DocCon Suite

Desktop transmittal workstation. Slice 1: Jira settings + load a job’s drawing register.

## Run

Double-click **`Elite DocCon.exe`** in this folder (Sarah’s copy too). Rebuild with **`Build DocCon.exe.bat`**.

Or double-click **`Run DocCon (source).bat`** to run from source.

Or from a terminal:

```text
python -m pip install -e ".[dev]"
python -m pytest
python -m doccon
```

1. **Settings** — site, Atlassian email, paste API token (Windows Credential Manager, not Dropbox). Save TO/CC addresses here; **Pick…** on the cover adds one.
2. **Test connection**.
3. **Job Number** — e.g. `2026-Tanzim` — **Load**. The navy bar shows the Jira Project name (blue) and the Dropbox job folder (teal). Several Job Numbers may share one folder; **Locate job folder…** if the hunt cannot pick. Edit Next on drawings, tick Pack, **Create transmittal**. Missing PDF: **Locate…**, or **Paste PDF** / Ctrl+V after Outlook Copy (copied into `DocCon/dropped`; the address reads `scan0042.pdf — email dropped` in yellow, hover for the staged path; that copy is deleted after a real job PDF is paired or Confirm succeeds). The watched folder (Downloads / Desktop / inbox) is the fallback. There is no **PDF from Outlook** button. **Open** beside it opens the matched PDF. Cover TO/CC/project come from the existing CT/ST/FT letter when those cells are filled; PEP is the fallback (**Locate PEP…** overwrites). **Create EDDI** (and Create transmittal) copy the job’s EDDI form to a dated snapshot in `3.0 Doc Con` and print a PDF of items that have a matched PDF (not attached to Outlook). Next edits auto-save in `client-pack.json`. Outlook gets the transmittal PDF plus a zip of the drawings (the form PDF is not in the zip).

Email send from Outlook is still a person clicking Send. Do not run File and email against a live job (075).
