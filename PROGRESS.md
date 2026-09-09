# Progress log

Newest first. Append a dated entry when a decision is locked, a test runs, or the next step changes.

## 2026-09-09 — Console theme

DocCon uses a navy chrome bar, teal Confirm, light cards, and Segoe UI instead of stock tkinter gray. Settings and the calendar use the same look. Console is **0.74**.

## 2026-09-09 — Client Document Number on the pack

Jira **Client Document Number** (`customfield_10279`) is a Now/Next field on packed drawings (free text, not a dropdown). Confirm writes it to Jira. It does not replace Elite Drawing on the Excel log. Console is **0.73**.

## 2026-09-09 — Cover strip at the bottom

Cover (FROM / TO / CC / Project) is a horizontal strip under the drawing list, not a right-hand column. The board keeps full width. Console is **0.72**.

## 2026-09-09 — Drawing vs Title columns left split

Board still shows **Drawing** (summary first token) and **Title** (remainder). Combining them into one Summary column is deferred.

## 2026-09-09 — TO and CC are email addresses only

Console TO/CC (and the Outlook/Excel cover lines) keep email addresses, not names or roles from the PEP. Type more CCs as `name@company.com; other@company.com`. PEP still supplies defaults from D50/D51 and any emails in the PM/PE cells. A saved pack that only had names falls back to those PEP emails. Console is **0.71**.

## 2026-09-09 — Confirm writes the Save draft

**Confirm…** writes `client-pack.json` (TO/CC/project, dates, Pack ticks) before Jira/file/mail. If that write fails, Confirm stops. Saves again when Confirm finishes.

## 2026-09-09 — Save button label

The Dropbox draft control is **Save** (not Save pack). Same `client-pack.json`.

## 2026-09-09 — Version 0.70

Prerelease console is **0.70** (window title and pyproject). Not 0.1.0.

## 2026-09-09 — Batch Next on the list; calendar dates

**Batch Next** at the top of the drawing list: Pack all / none, then dropdowns for Status and the Jira fields. **Apply to Pack** writes those Next values onto Pack-ticked rows only; blank batch boxes are skipped. Date issued and Expected return have **Today** and **Calendar…**. Expected also has **N/A**. Confirm is still the one send click.

## 2026-09-08 — One Confirm button: Jira + file + Outlook draft

Open the console, edit Next, tick Pack, **Confirm…**. That writes changed Jira fields/status on packed drawings, files the CT log and cover PDF, zips the pack, opens Outlook. Operator still clicks Send. Save to Jira is gone. Save pack is only the Dropbox draft (TO/CC).

## 2026-09-08 — One pack action: File and email

Fill, File, and Email draft are one confirm. **File and email…** writes TRANSMITTAL, files the numbered tab + cover PDF, zips `CT-{job}-{n}.zip`, opens Outlook from this PC. Operator still clicks Send. Save to Jira stays its own button. Excel Add Page / File Transmittal still work by hand.

## 2026-09-08 — Status is a Next dropdown; Save uses workflow transitions

Status cannot be PATCHed. Next Status sits under Now. **Save to Jira…** GETs allowed transitions and POSTs the hop whose destination matches the chosen status. Dummy To Do drawings cannot jump to IFI/IFC/OFA (workflow condition); In Progress, Done, Back from Client, etc. can. Does not auto-walk the workflow.

## 2026-09-08 — Jira fields on each drawing row (Now / Next)

No side panel. Each drawing is two rows: **Now** (current Jira, read-only) and **Next** (dropdowns for Outgoing Rev, Purpose, Incoming Rev, Client stamp, Shop/Field IFC). Tick **Pack** for Fill / File / Email. **Save to Jira…** writes only Next values that differ from Now. Pack ticks restore from `client-pack.json`.

## 2026-09-08 — Email draft from this PC’s Outlook

**Email draft…** zips cover PDF (if filed) + matched drawing PDFs to `3.1.1 Out` as `CT-{job}-{n}.zip`, then opens Outlook from the signed-in account on this machine. Does not Send As doc.control. Does not auto-send. Cover FROM on the Excel letter is unchanged.

## 2026-09-08 — Last-record fields edit on the console, Save to Jira

Select drawing row(s). Right pane **Jira**: Outgoing Rev, Purpose, Incoming Rev, Client stamp, Shop/Field IFC Rev. **Save to Jira…** confirms then PATCHes those option fields. Blank values are skipped (not cleared). Status is not transitioned. Does not send mail.

## 2026-09-08 — Cover TO/CC/project on the console

Right-hand Cover pane: FROM is read-only (`doc.control@…`). TO, CC, and project description are editable. Defaults come from the PEP; **Save pack** (and leaving a field) writes `{job}/3.0 Doc Con/DocCon/client-pack.json`. Fill/File uses the console lines, not a second Jira file.

## 2026-09-08 — Console TO/CC/project; pack file in the job folder

PEP still fills the defaults. Operator can change TO, CC, and project description on the console for this send (FROM stays doc.control). Those edits do not rewrite `7.0 Sales`. Draft progress lives at `{job}/3.0 Doc Con/DocCon/client-pack.json` so Dropbox shares it with Sarah. Jira site/token stay in LOCALAPPDATA / Credential Manager, not in that file.

## 2026-09-08 — Mail is Sarah’s Outlook, not Tanzim’s

`doc.control@…` lives on Sarah’s PC. DocCon will not Send As from Tanzim’s mailbox and will not open Outlook by itself. Confirm send (later, on her machine) writes the zip in `3.1.1 Out` and opens a draft in the DocCon Outlook profile for her to send. Fill/File/Jira can be tested here without mail.

## 2026-09-08 — Excel Unprotect must not prompt

Fill/File was calling `Unprotect()` with no password. Excel COM shows the password box for that; DisplayAlerts does not hide it. Unlock now uses only the template lock (same as the CT VBA). Do not Unprotect from the Review tab.

## 2026-09-08 — Client pack: folder zip and Outlook attach

Same bundle both places. Cover PDF (`CT-{job}-{n}.pdf`) plus the matched Current PDF files for the selected rows. Zip lands in `3.1.1 Out` as `CT-{job}-{n}.zip`. Outlook FROM the DocCon mailbox, TO/CC from PEP, those files attached. Confirm still required; does not auto-send. Shop/Field stay folder-copy (IFC), not this zip. Email body/subject wording not locked.

## 2026-09-08 — Edit on the console, confirm writes Jira

Document controller updates last-record fields in DocCon, not in the Jira Excel export. Typing is local until they confirm; that confirm PATCHes the drawing sub-tasks. Does not send mail. Outlook stays a later confirm. Do not auto-bump rev.

## 2026-09-08 — Controller update columns are Jira fields

The spreadsheet a document controller uses to update transmittal data points is a Jira download/export. Those columns are the drawing custom fields (Outgoing Rev, purpose, Incoming Rev, approval, Shop/Field IFC, etc.). DocCon writes them back through Jira REST, not by round-tripping that export. The CT/ST/FT `.xlsm` books stay the transmittal log; they are not that export.

## 2026-09-01 — Original Excel workflow stays

The CT/ST/FT `.xlsm` books remain the log. DocCon does not replace them. **Fill TRANSMITTAL…** writes cover + rows on the working sheet only (no numbered tab, n stays put, Add Page / File Transmittal stay in Excel). **File Client Transmittal…** is the optional shortcut (archive tab + PDF). Close the CT book before either write.

## 2026-09-01 — File Client uses Excel for .xlsm

openpyxl save was dropping the Elite logo and Add Page / File Transmittal buttons (the “1” in the corner is the page-count cell under the missing logo). File Client now copies TRANSMITTAL through Excel, like the book’s own File Transmittal. Load no longer stamps a real .xlsm with openpyxl. If the logo/buttons are already gone, File restores them from the jobs-template CT book.

## 2026-09-01 — Locate PEP / File after Load

Locate PEP and File Client use the Job Number box plus the loaded job, and look up the Dropbox folder again if it was missed. They no longer treat “folder not found” as “you never loaded.”

## 2026-09-01 — CT cover fills from PEP; dates on the console

File Client writes FROM (`doc.control@…`), TO (PEP D50), CC (PEP D51 + Elite PM/PE names), and the project line (client / site / tank / PO / WO) from `7.0 Sales`. Date issued and Expected document return are console fields (return can be a date or text like N/A). If no usable PEP is in Sales, Locate PEP…. Blank C-109.5 and leftover template PEP PDFs are not auto-picked. Tanzim may use a copied 075 PEP.

## 2026-09-01 — PEP in 7.0 Sales is the cover source

Project Execution Plan lives in `7.0 Sales`. Same form as `C-109.5` Excel, issued as PDF (075 has Rev0–Rev2). Transmittal Recipients Main (`D50`) is the CT **TO** line; CC's (`D51`) plus Elite EM/PM/PE is **CC**. Also on that sheet: client, site, tank tag, PO — the project description line. On a real job: highest Rev whose filename is this Job Number. **`2026-Tanzim` has no real PEP** — a copied live PEP in that folder is the sandbox stand-in (do not require the filename to be 2026-Tanzim).

## 2026-09-01 — Auto-name CT/ST/FT books on Load

Load a job: if the books are still `CT-202X-XXX.xlsm` / `ST-20XX-XXX.xlsm` / `FT-20XX-XXX.xlsm`, DocCon renames them to `CT-{job}.xlsm` (and ST/FT) and stamps the Job Number into the placeholder cell. Already-named live books (`CT-2026-075.xlsm`) are left alone.

## 2026-09-01 — Client transmittal from the console

Radios: Client / Shop / Field. Only Client writes. Select drawing rows → File Client Transmittal… fills `TRANSMITTAL`, copies a numbered tab, bumps n, prints `CT-{job}-{n}.pdf` beside the book. Template `CT-202X-XXX.xlsm` is renamed to `CT-{job}.xlsm` on first file. Refuses a book whose A12 is another job (will not file Tanzim into 075). 27 tests passed. Shop/Field later.

## 2026-09-01 — Sandbox job `2026-Tanzim`

User created `2.1 Current Jobs\2026-Tanzim` from the jobs template. Live jobs stay untouched. Blank books still named `CT-202X-XXX.xlsm` / `ST-20XX-XXX.xlsm` / `FT-20XX-XXX.xlsm`; job cell still `202X-XXX`; Current PDF empty. Do not File Transmittal on 075.

## 2026-09-01 — Transmittal log is the Excel books

Live books on 2026-075 plus Document Control Templates QRG. Three independent counters:

- Client `3.1.1 Out/CT-{job}.xlsm` → `CT-{job}-{n}` (075 next is 11)
- Shop `3.2/ST-{job}.xlsm` → `ST-{job}-{n}` (075 next is 5)
- Field `3.3/FT-{job}.xlsm` → `FT-{job}-{n}` (075 next is 4)

Working sheet is always **TRANSMITTAL**. **Add Page** (`INSERT_PG`) only unhides overflow rows (max 3 print pages). **File Transmittal** (`counter`) copies that sheet to a tab named with the current number, clears the list, bumps n+1. Then print that tab to `{CT|ST|FT}-{job}-{n}.pdf`. Client also zips attachments into 3.1.1 Out; shop/field copy IFC files. Unused filed tab: `FILED IN ERROR, NOT USED YET` in the date cell so the number is reused.

## 2026-09-01 — Dropbox path remaps like Databook

Same rule as the Engine: keep everything after `Elite Integrity Serv Dropbox/<person>/`, attach it to this PC’s person folder. `2.0` vs `2.1 Current Jobs` both tried. Sarah’s path works on Tanzim’s PC and the other way around.

## 2026-09-01 — Manual Match PDF adopts filename on Jira

Select a row → Match PDF… → confirm. Summary first token becomes the PDF drawing ID (title kept). Local row turns High. Close and relaunch DocCon to use it.

## 2026-09-01 — PDF match from Current PDF folders

DocCon finds `{Job Number} …` under Current Jobs, scans `2.0 Drafting/**/Current PDF`, skips Void. Live: 2026-096 folder found (SK1 PDFs; Jira 1-1/1-2 still Missing). 2026-075 has 17 current PDFs. 15 tests passed.

## 2026-09-01 — Slice 1 live: job 2026-096

Sarah-path works. Loaded `2026-096` → 2 Drafting sub-tasks (`P2024-15630` `2026-096-1-1 Drawing-1`, `P2024-15631` `2026-096-1-2 Drawing-2`). Parent was `2026-096 Manway Package Drawing` (not always named “Drawing Package”). Outgoing Rev / purpose empty on those rows. No send yet.

## 2026-09-01 — Slice 1 running

Python tkinter console: Settings (Jira site/email/token in Credential Manager) + Load Job Number → drawing table. Run `python -m doccon`. Tests: 8 passed. No Outlook, PDFs, or writeback yet.

## 2026-09-01 — Develop in thin slices; settings only when needed

Do not build a giant Settings dump first. Slice 1 (when asked): Jira token in Settings + load one job’s drawings. Outlook account, PDF root, log, writeback UI wait for those slices.

## 2026-09-01 — Mobile is a later companion, not slice 1

Full match/OCR/Outlook-COM console on iPhone is a poor fit. A later thin app (pick job, see Jira rows, maybe confirm send via Graph) is possible after desktop + Graph mail. Do not start mobile now.

## 2026-09-01 — No extra Jira status; engineer emails Sarah

Engineer sends Sarah the list with details. Sarah runs DocCon. No custom status or include-field. Next process fact: where issued PDFs live. First code (when asked): Settings + Jira pull.

## 2026-09-01 — Outlook owns email login

DocCon does not collect the DocCon mailbox password. The workstation Outlook profile is already signed in (MFA/Modern Auth). Settings chooses that account. If Outlook is logged out, DocCon refuses send and asks to sign in there.

## 2026-09-01 — Send from DocCon mailbox

Outlook on the PC sends as the existing DocCon email account (shared mailbox / Send As), not the operator’s personal address. Confirm send still required.

## 2026-09-01 — DocCon is the trigger

Open DocCon → fetch Jira for that job → pick the bundle → Confirm send → update those Jira issues. Jira is not the start button. Include-checkbox optional as a hint only.

## 2026-09-01 — Bundles in DocCon, not Jira

Engineers send different subsets on different transmittals. Jira does not get a pack-ID or a new parent per combo. Checkbox = eligible. Each DocCon Confirm send is one bundle; only those ticks are cleared.

## 2026-09-01 — Token in Settings, not in code

DocCon Settings: operator pastes a new Jira API token (and email/site). Saved to Windows Credential Manager. Replace when it expires. Never Dropbox, git, or a coded constant.

## 2026-09-01 — DocCon is notified by pull, not webhook

Jira cannot reach the operator PC. DocCon tray/on-open JQL-polls drawings with Include in next transmittal set. Optional Jira Automation emails the person a `doccon://` link. No public webhook.

## 2026-09-01 — Mark drawings in place (field, not reparent)

User rejected moving drawings under Document Transmittals. Parent stays Drawing Package. Prefer custom field on the drawing: Include in next transmittal. Not a new IFC-style status. DocCon queues by Job Number + field. After send, clear the field.

## 2026-09-01 — Controller path (plain)

Engineer transitions drawing sub-tasks when those sheets should go out. That is the “include these” signal, not the send. Document controller opens the job’s Document Transmittals task and clicks into DocCon. DocCon loads that Job Number, shows last record, and highlights what the engineers just moved. Controller matches PDFs and confirms. Email does not leave on the Jira transition.

## 2026-09-01 — No custom field for Jira trigger

Do not create a new Jira field to start a transmittal. The Document Transmittals task is the button. Use a click, workflow transition, or Automation manual rule plus `doccon://job/<Job Number>`. Drawing custom fields stay last-record data.

## 2026-08-21 — Trigger flow mapped on canvas

Architecture canvas updated: Trigger tab (Jira start vs field data vs confirm send), dummy job tree, live field IDs.

## 2026-08-21 — Trigger from Jira is wanted

Start the pack from the job’s Document Transmittals task. Deep link (`doccon://job/<Job Number>`) and/or Dropbox inbox to the desktop app. Confirm send stays in DocCon. Jira field edits still do not email the client.

## 2026-08-21 — Jira changes do not trigger send

Register updates (Outgoing Rev, purpose, etc.) are data, not a start button. DocCon pulls on job open and diffs vs last pack. Person confirms. No webhook-to-email.

## 2026-08-21 — Remaining process details parked

User will explain later: PDF folder layout, log template, transmittal numbering, post-send writeback. Do not keep asking. Jira contract + last-record rule are enough to hold.

## 2026-08-21 — Ready-to-send is last record + engineer

Not a Jira status gate. DocCon fills Outgoing Rev / Submitted to Client For (and related stamps) **as the engineer says**, using the drawing’s **last record** (Outgoing Rev, Incoming Rev, Client Approval Status, Shop/Field IFC Rev).

DocCon should surface that last record on the register so the operator is not hunting history. Do not auto-pick the next rev.

**Next:** issued PDF folder layout, then log template / transmittal numbering.

## 2026-08-21 — Live Jira read succeeded

Read-only REST to `https://eliteintegrityservices.atlassian.net` as Tanzim Nasir. No writes. Token was not saved in this folder — revoke the chat-pasted token.

- Dummy Project `P2024-15553` (`2026-Tanzim Test`, Job Number `2026-Tanzim`) spawned the Elite template: Drawing Package, Document Transmittals (label DocCon), Databook, QC, etc.
- Drawing rows: Sub-tasks `P2024-15578` / `P2024-15579` under Drawing Package `P2024-15577`.
- Field map locked: Job Number `customfield_10300`, Outgoing Rev `customfield_10280`, Submitted to Client For `customfield_10281`, Incoming Rev `customfield_10283`, Client Approval Status `customfield_10284`, Shop/Field IFC revs, EDDI Status.
- Live drawing shape confirmed on job `2026-075` (status IFC, Outgoing Rev 0, purpose Info).

**Next:** decide what “ready to transmit” looks like on a drawing sub-task, then PDF folder + log.

## 2026-08-21 — Dummy issue identified

- `P2024-15553` — summary `2026-Tanzim Test`
- Connectivity test only; summary is not the production pattern (`2026-075-1-1 Drawing 1`).

**Still waiting:** Atlassian email + API token for `GET /rest/api/3/issue/P2024-15553`.

## 2026-08-21 — Jira site identified

- Cloud: https://eliteintegrityservices.atlassian.net
- Project key from board URL: `P2024` ([project list](https://eliteintegrityservices.atlassian.net/jira/core/projects/P2024/l))

**Still waiting:** dummy issue key + Atlassian email + API token for a read-only GET.

## 2026-08-21 — Project memory created

Put standing context in this folder so new Cursor chats load the DocCon plan:

- `.cursor/rules/doccon-project.mdc`
- `.cursor/rules/jira-register.mdc`
- `.cursor/rules/architecture.mdc`
- `AGENTS.md`

**Still waiting:** dummy Jira job + site URL + issue key + read-only token (or local env var) so we can `GET` one issue.

## 2026-08-21 — Planning session (morning chat)

Started automated transmittal design. Architecture canvas lives outside Dropbox:

`C:\Users\TanzimNasir\.cursor\projects\c-Users-TanzimNasir-Elite-Integrity-Serv-Dropbox-Tanzim-Nasir-2-7-Engineering-2-7-5-Software-Elite-DocCon-Suite\canvases\doccon-transmittal-architecture.canvas.tsx`

Locked:

- Jira stays the register; DocCon is match / log / send / audit
- One issue = one drawing (task or sub-task)
- Summary holds drawing number + title (`2026-075-1-1 Drawing 1`)
- Talk to Jira over REST, not the webpage
- No application code and no Dropbox job-file edits during planning
- User wants a live Jira read on a dummy ticket before more design

Not locked: revision field, document type field, ready-status, site URL, PDF folder layout, log format, transmittal numbering.
